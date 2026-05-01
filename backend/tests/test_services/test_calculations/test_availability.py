"""Phase 1 dual-view orchestrators: Availability, MTBF, MTTR."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.services.calculations.availability import (
    AvailabilityInputs,
    MTBFInputs,
    MTTRInputs,
    calculate_availability,
    calculate_mtbf,
    calculate_mttr,
)


class TestAvailability:
    def test_standard_mode_textbook(self):
        inputs = AvailabilityInputs(
            scheduled_hours=Decimal("8"),
            downtime_hours=Decimal("1"),
        )
        result = calculate_availability(inputs)
        assert result.metric_name == "availability"
        assert result.value == Decimal("87.50")  # 7/8 = 87.5%
        assert result.mode == "standard"

    def test_site_adjusted_equals_standard_in_phase_1(self):
        inputs = AvailabilityInputs(scheduled_hours=Decimal("8"), downtime_hours=Decimal("2"))
        std = calculate_availability(inputs, mode="standard")
        adj = calculate_availability(inputs, mode="site_adjusted")
        assert std.value == adj.value
        assert adj.assumptions_applied == []

    def test_zero_downtime_yields_100(self):
        inputs = AvailabilityInputs(scheduled_hours=Decimal("8"), downtime_hours=Decimal("0"))
        assert calculate_availability(inputs).value == Decimal("100.00")

    def test_downtime_exceeds_scheduled_clamps_to_zero(self):
        inputs = AvailabilityInputs(scheduled_hours=Decimal("8"), downtime_hours=Decimal("10"))
        assert calculate_availability(inputs).value == Decimal("0.00")

    def test_zero_scheduled_yields_zero(self):
        inputs = AvailabilityInputs(scheduled_hours=Decimal("0"), downtime_hours=Decimal("0"))
        assert calculate_availability(inputs).value == Decimal("0")

    def test_negative_input_rejected(self):
        with pytest.raises(ValidationError):
            AvailabilityInputs(scheduled_hours=Decimal("-1"), downtime_hours=Decimal("0"))


class TestMTBF:
    def test_standard_mode_textbook(self):
        inputs = MTBFInputs(operating_hours=Decimal("100"), failure_count=4)
        result = calculate_mtbf(inputs)
        assert result.metric_name == "mtbf"
        assert result.value == Decimal("25.00")

    def test_zero_failures_returns_none(self):
        inputs = MTBFInputs(operating_hours=Decimal("100"), failure_count=0)
        assert calculate_mtbf(inputs).value is None

    def test_site_adjusted_equals_standard_in_phase_1(self):
        inputs = MTBFInputs(operating_hours=Decimal("100"), failure_count=4)
        assert calculate_mtbf(inputs, "standard").value == calculate_mtbf(inputs, "site_adjusted").value


class TestMTTR:
    def test_standard_mode_textbook(self):
        inputs = MTTRInputs(total_repair_hours=Decimal("10"), repair_count=4)
        result = calculate_mttr(inputs)
        assert result.metric_name == "mttr"
        assert result.value == Decimal("2.50")

    def test_zero_repairs_returns_none(self):
        inputs = MTTRInputs(total_repair_hours=Decimal("10"), repair_count=0)
        assert calculate_mttr(inputs).value is None
