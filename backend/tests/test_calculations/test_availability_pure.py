"""Unit tests for the pure availability formula (honest-surface PR)."""

from decimal import Decimal

from backend.calculations.availability import calculate_availability_pure


class TestCalculateAvailabilityPure:
    def test_normal_case(self):
        # 8h scheduled, 1h downtime -> 87.5%
        result = calculate_availability_pure(Decimal("8"), Decimal("1"))
        assert result == Decimal("87.5")

    def test_zero_downtime_is_100(self):
        assert calculate_availability_pure(Decimal("9.5"), Decimal("0")) == Decimal("100")

    def test_zero_scheduled_is_0(self):
        assert calculate_availability_pure(Decimal("0"), Decimal("0")) == Decimal("0")

    def test_negative_scheduled_is_0(self):
        assert calculate_availability_pure(Decimal("-1"), Decimal("0")) == Decimal("0")

    def test_downtime_exceeding_scheduled_clamps_to_0(self):
        assert calculate_availability_pure(Decimal("4"), Decimal("5")) == Decimal("0")

    def test_matches_canonical_formula(self):
        # Same math as calculate_availability(): (scheduled - downtime) / scheduled * 100
        scheduled, downtime = Decimal("8.0"), Decimal("2.5")
        expected = (scheduled - downtime) / scheduled * 100
        assert calculate_availability_pure(scheduled, downtime) == expected
