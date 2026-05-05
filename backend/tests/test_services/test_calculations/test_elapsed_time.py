"""Phase 1 dual-view orchestrators: Elapsed Hours/Days, Business Hours, Days Early/Late."""

from datetime import datetime, timezone
from decimal import Decimal

from backend.services.calculations.elapsed_time import (
    BusinessHoursInputs,
    DaysEarlyOrLateInputs,
    ElapsedDaysInputs,
    ElapsedHoursInputs,
    calculate_business_hours,
    calculate_days_early_or_late,
    calculate_elapsed_days,
    calculate_elapsed_hours,
)


class TestElapsedHours:
    def test_standard_mode_textbook(self):
        from_dt = datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc)
        to_dt = datetime(2026, 4, 1, 18, 30, tzinfo=timezone.utc)
        result = calculate_elapsed_hours(ElapsedHoursInputs(from_datetime=from_dt, to_datetime=to_dt))
        assert result.value == 10  # 10.5 hours, int truncates

    def test_naive_datetime_treated_as_utc(self):
        from_dt = datetime(2026, 4, 1, 8, 0)  # naive
        to_dt = datetime(2026, 4, 1, 18, 0, tzinfo=timezone.utc)
        result = calculate_elapsed_hours(ElapsedHoursInputs(from_datetime=from_dt, to_datetime=to_dt))
        assert result.value == 10


class TestElapsedDays:
    def test_standard_mode_textbook(self):
        from_dt = datetime(2026, 4, 1, tzinfo=timezone.utc)
        to_dt = datetime(2026, 4, 11, tzinfo=timezone.utc)
        result = calculate_elapsed_days(ElapsedDaysInputs(from_datetime=from_dt, to_datetime=to_dt))
        assert result.value == Decimal("10.0")


class TestBusinessHours:
    def test_standard_mode_mon_to_fri(self):
        # Mon Apr 6 2026 → Fri Apr 10 2026 inclusive = 5 weekdays × 8 = 40
        from_dt = datetime(2026, 4, 6, tzinfo=timezone.utc)
        to_dt = datetime(2026, 4, 10, tzinfo=timezone.utc)
        result = calculate_business_hours(BusinessHoursInputs(from_datetime=from_dt, to_datetime=to_dt))
        assert result.value == 40

    def test_weekend_skipped(self):
        # Sat Apr 4 → Sun Apr 5 2026 = 0 weekdays
        from_dt = datetime(2026, 4, 4, tzinfo=timezone.utc)
        to_dt = datetime(2026, 4, 5, tzinfo=timezone.utc)
        result = calculate_business_hours(BusinessHoursInputs(from_datetime=from_dt, to_datetime=to_dt))
        assert result.value == 0


class TestDaysEarlyOrLate:
    def test_late(self):
        # actual is 3 days after expected → -3
        expected = datetime(2026, 4, 1, tzinfo=timezone.utc)
        actual = datetime(2026, 4, 4, tzinfo=timezone.utc)
        result = calculate_days_early_or_late(DaysEarlyOrLateInputs(expected_date=expected, actual_date=actual))
        assert result.value == -3

    def test_early(self):
        # actual is 2 days before expected → +2
        expected = datetime(2026, 4, 5, tzinfo=timezone.utc)
        actual = datetime(2026, 4, 3, tzinfo=timezone.utc)
        result = calculate_days_early_or_late(DaysEarlyOrLateInputs(expected_date=expected, actual_date=actual))
        assert result.value == 2

    def test_on_time(self):
        d = datetime(2026, 4, 1, tzinfo=timezone.utc)
        result = calculate_days_early_or_late(DaysEarlyOrLateInputs(expected_date=d, actual_date=d))
        assert result.value == 0
