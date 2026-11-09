"""Tool handlers against a real Postgres (the docker one from the README).

Skipped when DATABASE_URL is not reachable.
"""

import asyncio
import os
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from cod_agent.store import OrderStore  # noqa: E402
from cod_agent.tools import build_tools  # noqa: E402

DSN = os.getenv("DATABASE_URL", "")
MONDAY = date(2026, 11, 9)


def _db_up() -> bool:
    try:
        psycopg.connect(DSN, connect_timeout=2).close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not DSN or not _db_up(), reason="Postgres not available")


@pytest.fixture(autouse=True)
def fresh_db():
    with psycopg.connect(DSN) as conn:
        conn.execute((ROOT / "db/schema.sql").read_text())
        conn.execute((ROOT / "db/seed.sql").read_text())
    yield


class FakeParams(SimpleNamespace):
    """Stands in for FunctionCallParams: records what the tool returned."""

    def __init__(self):
        super().__init__(result=None, properties=None)

    async def result_callback(self, result, *, properties=None):
        self.result, self.properties = result, properties


def tools_for(order_id: str) -> dict:
    store = OrderStore(DSN)
    return {fn.__name__: fn for fn in build_tools(store, order_id, today=lambda: MONDAY)}


def row(order_id: str) -> dict:
    with psycopg.connect(DSN) as conn:
        cur = conn.execute("SELECT status, delivery_date, address, cancel_reason FROM orders WHERE id = %s", (order_id,))
        status, day, address, reason = cur.fetchone()
        actions = [a for (a,) in conn.execute(
            "SELECT action FROM call_events WHERE order_id = %s ORDER BY id", (order_id,))]
    return {"status": status, "delivery_date": day, "address": address, "reason": reason, "actions": actions}


def run(coro):
    return asyncio.run(coro)


def test_start_call_picks_oldest_pending_and_counts_attempt():
    order = run(OrderStore(DSN).start_call())
    assert order.id == "CMD-1042"
    with psycopg.connect(DSN) as conn:
        assert conn.execute("SELECT attempts FROM orders WHERE id = 'CMD-1042'").fetchone()[0] == 1
    assert row("CMD-1042")["actions"] == ["call_started"]


def test_confirm_writes_status_date_and_event():
    p = FakeParams()
    run(tools_for("CMD-1043")["confirm_order"](p, delivery_date="2026-11-11"))
    assert p.result["ok"] is True
    r = row("CMD-1043")
    assert (r["status"], r["delivery_date"], r["actions"]) == ("confirmed", date(2026, 11, 11), ["confirmed"])


def test_invalid_date_is_reported_not_saved():
    p = FakeParams()
    run(tools_for("CMD-1043")["confirm_order"](p, delivery_date="2026-11-15"))  # Sunday
    assert p.result["ok"] is False and "Sunday" in p.result["message"]
    assert row("CMD-1043")["status"] == "pending"


def test_update_address_keeps_old_value_in_log():
    p = FakeParams()
    run(tools_for("CMD-1044")["update_address"](p, new_address="Residence Al Andalous, apt 9, Gueliz"))
    r = row("CMD-1044")
    assert r["address"] == "Residence Al Andalous, apt 9, Gueliz"
    with psycopg.connect(DSN) as conn:
        detail = conn.execute("SELECT detail FROM call_events WHERE order_id = 'CMD-1044'").fetchone()[0]
    assert detail == {"from": "Lot Massira 1, villa 112", "to": "Residence Al Andalous, apt 9, Gueliz"}


def test_cancel_and_reschedule():
    p = FakeParams()
    run(tools_for("CMD-1045")["cancel_order"](p, reason="found cheaper"))
    assert row("CMD-1045")["status"] == "cancelled" and row("CMD-1045")["reason"] == "found_cheaper"
    run(tools_for("CMD-1046")["reschedule_order"](p, delivery_date="2026-11-14"))
    assert row("CMD-1046")["status"] == "rescheduled"
