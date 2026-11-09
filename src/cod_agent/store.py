"""PostgreSQL access for orders and the call audit log."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row


@dataclass(frozen=True)
class Order:
    id: str
    customer_name: str
    phone: str
    city: str
    address: str
    items: list[dict[str, Any]]
    total_mad: Decimal
    status: str
    delivery_date: date | None


class OrderStore:
    def __init__(self, dsn: str):
        self.dsn = dsn

    async def _conn(self) -> psycopg.AsyncConnection:
        return await psycopg.AsyncConnection.connect(self.dsn, row_factory=dict_row, autocommit=False)

    async def get(self, order_id: str) -> Order | None:
        async with await self._conn() as conn:
            row = await (await conn.execute("SELECT * FROM orders WHERE id = %s", (order_id,))).fetchone()
        return _to_order(row) if row else None

    async def start_call(self, order_id: str | None = None) -> Order | None:
        """Pick the order to call (a given id, or the oldest pending one) and count the attempt."""
        async with await self._conn() as conn:
            if order_id:
                cur = await conn.execute("SELECT * FROM orders WHERE id = %s FOR UPDATE", (order_id,))
            else:
                cur = await conn.execute(
                    "SELECT * FROM orders WHERE status IN ('pending', 'no_answer') "
                    "ORDER BY updated_at, id LIMIT 1 FOR UPDATE SKIP LOCKED"
                )
            row = await cur.fetchone()
            if not row:
                return None
            await conn.execute(
                "UPDATE orders SET attempts = attempts + 1, updated_at = now() WHERE id = %s", (row["id"],)
            )
            await _log(conn, row["id"], "call_started", {"attempt": row["attempts"] + 1})
            await conn.commit()
        return _to_order(row)

    async def confirm(self, order_id: str, delivery_date: date) -> None:
        await self._set(order_id, "confirmed", {"delivery_date": delivery_date, "cancel_reason": None},
                        {"delivery_date": delivery_date.isoformat()})

    async def reschedule(self, order_id: str, delivery_date: date) -> None:
        await self._set(order_id, "rescheduled", {"delivery_date": delivery_date},
                        {"delivery_date": delivery_date.isoformat()})

    async def cancel(self, order_id: str, reason: str) -> None:
        await self._set(order_id, "cancelled", {"cancel_reason": reason, "delivery_date": None}, {"reason": reason})

    async def update_address(self, order_id: str, address: str) -> None:
        async with await self._conn() as conn:
            old = await (await conn.execute(
                "UPDATE orders o SET address = %s, updated_at = now() FROM orders prev "
                "WHERE o.id = %s AND prev.id = o.id RETURNING prev.address", (address, order_id)
            )).fetchone()
            if not old:
                raise LookupError(order_id)
            await _log(conn, order_id, "address_updated", {"from": old["address"], "to": address})
            await conn.commit()

    async def log(self, order_id: str, action: str, detail: dict[str, Any] | None = None) -> None:
        async with await self._conn() as conn:
            await _log(conn, order_id, action, detail or {})
            await conn.commit()

    async def _set(self, order_id: str, status: str, fields: dict[str, Any], detail: dict[str, Any]) -> None:
        assignments = ", ".join(f"{name} = %s" for name in fields)
        async with await self._conn() as conn:
            cur = await conn.execute(
                f"UPDATE orders SET status = %s, {assignments}, updated_at = now() WHERE id = %s",
                (status, *fields.values(), order_id),
            )
            if cur.rowcount != 1:
                raise LookupError(order_id)
            await _log(conn, order_id, status, detail)
            await conn.commit()


async def _log(conn: psycopg.AsyncConnection, order_id: str, action: str, detail: dict[str, Any]) -> None:
    await conn.execute(
        "INSERT INTO call_events (order_id, action, detail) VALUES (%s, %s, %s::jsonb)",
        (order_id, action, json.dumps(detail, default=str)),
    )


def _to_order(row: dict[str, Any]) -> Order:
    return Order(
        id=row["id"],
        customer_name=row["customer_name"],
        phone=row["phone"],
        city=row["city"],
        address=row["address"],
        items=row["items"],
        total_mad=row["total_mad"],
        status=row["status"],
        delivery_date=row["delivery_date"],
    )
