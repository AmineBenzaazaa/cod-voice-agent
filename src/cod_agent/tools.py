"""Tools the LLM can call during a confirmation call.

Each tool validates input with the pure rules, writes to Postgres, and returns
a short result the LLM turns into speech. Validation errors are returned (not
raised) so the agent can ask the customer again.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date

from loguru import logger
from pipecat.frames.frames import EndFrame, FunctionCallResultProperties
from pipecat.services.llm_service import FunctionCallParams

from . import rules
from .store import OrderStore

GOODBYE_GRACE_SECS = 4.0


def build_tools(store: OrderStore, order_id: str, today: Callable[[], date] = date.today) -> list:
    async def _reply(params: FunctionCallParams, ok: bool, message: str) -> None:
        await params.result_callback({"ok": ok, "message": message})

    async def confirm_order(params: FunctionCallParams, delivery_date: str):
        """Confirm the order after the customer agreed to it and to a delivery day.

        Args:
            delivery_date: Agreed delivery day in YYYY-MM-DD format.
        """
        try:
            day = rules.parse_delivery_date(delivery_date, today())
        except rules.RuleError as err:
            return await _reply(params, False, str(err))
        await store.confirm(order_id, day)
        logger.info(f"{order_id} confirmed for {day}")
        await _reply(params, True, f"Order confirmed for delivery on {day:%A %d %B}.")

    async def update_address(params: FunctionCallParams, new_address: str):
        """Replace the delivery address after the customer gave a new one and you repeated it back.

        Args:
            new_address: Full new address: street, building or apartment, neighborhood.
        """
        try:
            address = rules.clean_address(new_address)
        except rules.RuleError as err:
            return await _reply(params, False, str(err))
        await store.update_address(order_id, address)
        await _reply(params, True, "Address updated.")

    async def reschedule_order(params: FunctionCallParams, delivery_date: str):
        """Keep the order but move it to a later delivery day the customer prefers.

        Args:
            delivery_date: Preferred delivery day in YYYY-MM-DD format.
        """
        try:
            day = rules.parse_delivery_date(delivery_date, today())
        except rules.RuleError as err:
            return await _reply(params, False, str(err))
        await store.reschedule(order_id, day)
        await _reply(params, True, f"Delivery moved to {day:%A %d %B}.")

    async def cancel_order(params: FunctionCallParams, reason: str):
        """Cancel the order when the customer clearly does not want it.

        Args:
            reason: One of changed_mind, ordered_by_mistake, found_cheaper, too_slow, did_not_order, other.
        """
        clean = rules.clean_cancel_reason(reason)
        await store.cancel(order_id, clean)
        await _reply(params, True, "Order cancelled.")

    async def end_call(params: FunctionCallParams):
        """Hang up. Call this right after your one-sentence goodbye."""
        await store.log(order_id, "call_ended")
        await params.result_callback({"ok": True}, properties=FunctionCallResultProperties(run_llm=False))

        async def _hang_up():
            await asyncio.sleep(GOODBYE_GRACE_SECS)  # let the goodbye finish playing
            await params.pipeline_worker.queue_frame(EndFrame())

        asyncio.create_task(_hang_up())

    return [confirm_order, update_address, reschedule_order, cancel_order, end_call]
