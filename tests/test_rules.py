import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from cod_agent import rules  # noqa: E402

MONDAY = date(2026, 11, 9)


def test_accepts_tomorrow():
    assert rules.parse_delivery_date("2026-11-10", MONDAY) == date(2026, 11, 10)


@pytest.mark.parametrize(
    "value, message",
    [
        ("2026-11-09", "tomorrow or later"),
        ("2026-11-01", "tomorrow or later"),
        ("2026-11-17", "7 days ahead"),
        ("2026-11-15", "Sunday"),
        ("next friday", "YYYY-MM-DD"),
        ("", "YYYY-MM-DD"),
    ],
)
def test_rejects_bad_dates(value, message):
    with pytest.raises(rules.RuleError, match=message):
        rules.parse_delivery_date(value, MONDAY)


def test_address_is_normalised_and_checked():
    assert rules.clean_address("  12 Rue   Atlas,\n Maarif ") == "12 Rue Atlas, Maarif"
    with pytest.raises(rules.RuleError):
        rules.clean_address("Maarif")


@pytest.mark.parametrize(
    "value, expected",
    [("changed mind", "changed_mind"), ("Did_Not_Order", "did_not_order"), ("too expensive", "other"), ("", "other")],
)
def test_cancel_reason_maps_to_known_values(value, expected):
    assert rules.clean_cancel_reason(value) == expected
