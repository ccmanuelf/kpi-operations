"""Bucket assignment is pure Python (date.weekday()/month math) so week/month/
quarter/year grouping cannot diverge between SQLite and MariaDB — the dialect
split is where past prod bugs (julianday class) hid."""

from datetime import date

import pytest

from backend.pivot.buckets import VALID_BUCKETS, bucket_start


def test_valid_buckets_tuple():
    assert VALID_BUCKETS == ("week", "month", "quarter", "year")


def test_week_monday_maps_to_itself():
    assert bucket_start(date(2026, 8, 3), "week") == date(2026, 8, 3)  # a Monday


def test_week_sunday_maps_to_previous_monday():
    assert bucket_start(date(2026, 8, 9), "week") == date(2026, 8, 3)


def test_week_year_boundary():
    # 2026-01-01 is a Thursday; its ISO week starts Monday 2025-12-29.
    assert bucket_start(date(2026, 1, 1), "week") == date(2025, 12, 29)


def test_month_start():
    assert bucket_start(date(2026, 2, 28), "month") == date(2026, 2, 1)


def test_quarter_starts():
    assert bucket_start(date(2026, 1, 15), "quarter") == date(2026, 1, 1)
    assert bucket_start(date(2026, 3, 31), "quarter") == date(2026, 1, 1)
    assert bucket_start(date(2026, 4, 1), "quarter") == date(2026, 4, 1)
    assert bucket_start(date(2026, 12, 31), "quarter") == date(2026, 10, 1)


def test_year_start():
    assert bucket_start(date(2026, 7, 4), "year") == date(2026, 1, 1)


def test_unknown_bucket_raises():
    with pytest.raises(ValueError):
        bucket_start(date(2026, 1, 1), "day")
