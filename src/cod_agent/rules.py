"""Pure business rules, kept separate from I/O so they are easy to test."""

from __future__ import annotations

from datetime import date, timedelta

MAX_DAYS_AHEAD = 7
MIN_ADDRESS_LENGTH = 10
CANCEL_REASONS = {
    "changed_mind",
    "ordered_by_mistake",
    "found_cheaper",
    "too_slow",
    "did_not_order",
    "other",
}


class RuleError(ValueError):
    """Input the agent should ask the customer about again."""


def parse_delivery_date(value: str, today: date) -> date:
    """Validate a delivery date the customer agreed to.

    Deliveries can be booked from tomorrow up to MAX_DAYS_AHEAD days out,
    never on a Sunday (couriers do not deliver).
    """
    try:
        day = date.fromisoformat(value.strip())
    except (AttributeError, ValueError) as exc:
        raise RuleError(f"'{value}' is not a date in YYYY-MM-DD format.") from exc
    if day <= today:
        raise RuleError("The delivery date must be tomorrow or later.")
    if day > today + timedelta(days=MAX_DAYS_AHEAD):
        raise RuleError(f"We can only book deliveries up to {MAX_DAYS_AHEAD} days ahead.")
    if day.weekday() == 6:
        raise RuleError("There are no deliveries on Sunday. Ask for another day.")
    return day


def clean_address(value: str) -> str:
    address = " ".join((value or "").split())
    if len(address) < MIN_ADDRESS_LENGTH:
        raise RuleError("That address is too short. Ask for street, building and neighborhood.")
    return address


def clean_cancel_reason(value: str) -> str:
    reason = (value or "").strip().lower().replace(" ", "_")
    return reason if reason in CANCEL_REASONS else "other"
