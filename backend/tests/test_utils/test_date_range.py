"""
Tests for the date-range validator.

Backs Run-6 finding R6-D-001: reversed date ranges silently returning
empty was a UX trap. The validator rejects with 400; these tests pin
that behavior.
"""

from datetime import date

import pytest
from fastapi import HTTPException

from backend.utils.date_range import validate_date_range


def test_normal_range_passes():
    validate_date_range(date(2026, 1, 1), date(2026, 12, 31))


def test_equal_dates_pass_one_day_window():
    """Equal dates are a valid one-day window; no error."""
    validate_date_range(date(2026, 5, 4), date(2026, 5, 4))


def test_reversed_range_raises_400():
    with pytest.raises(HTTPException) as exc:
        validate_date_range(date(2026, 12, 31), date(2026, 1, 1))
    assert exc.value.status_code == 400
    assert "after" in exc.value.detail.lower()


def test_none_start_skips_validation():
    """One-sided ranges are allowed; the validator is no-op when either is None."""
    validate_date_range(None, date(2026, 5, 4))


def test_none_end_skips_validation():
    validate_date_range(date(2026, 5, 4), None)


def test_both_none_skips_validation():
    validate_date_range(None, None)


def test_custom_field_names_in_error():
    """Field names appear verbatim in the error so the message names the
    actual UI parameters (e.g. 'received_after', 'shipped_before')."""
    with pytest.raises(HTTPException) as exc:
        validate_date_range(
            date(2026, 12, 31),
            date(2026, 1, 1),
            start_field="received_after",
            end_field="received_before",
        )
    msg = exc.value.detail
    assert "received_after" in msg
    assert "received_before" in msg
