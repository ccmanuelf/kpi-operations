"""Phase 1 dual-view orchestrators: WIP Aging, WIP Aging Adjusted, Hold Resolution Rate."""

from datetime import date
from decimal import Decimal

import pytest

from backend.services.calculations.wip import (
    HoldResolutionInputs,
    WIPAgingAdjustedInputs,
    WIPAgingInputs,
    calculate_hold_resolution_rate,
    calculate_wip_aging,
    calculate_wip_aging_adjusted,
)


class TestWIPAging:
    def test_standard_mode_textbook(self):
        inputs = WIPAgingInputs(
            hold_date=date(2026, 4, 1),
            as_of_date=date(2026, 4, 15),
        )
        assert calculate_wip_aging(inputs).value == 14

    def test_negative_range_clamps_to_zero(self):
        inputs = WIPAgingInputs(
            hold_date=date(2026, 4, 15),
            as_of_date=date(2026, 4, 1),
        )
        assert calculate_wip_aging(inputs).value == 0

    def test_same_day_zero(self):
        d = date(2026, 4, 15)
        assert calculate_wip_aging(WIPAgingInputs(hold_date=d, as_of_date=d)).value == 0


class TestWIPAgingAdjusted:
    def test_standard_mode_textbook(self):
        # 240 raw - 48 hold = 192 hours
        inputs = WIPAgingAdjustedInputs(
            raw_age_hours=Decimal("240"),
            total_hold_duration_hours=Decimal("48"),
        )
        assert calculate_wip_aging_adjusted(inputs).value == Decimal("192.00")

    def test_hold_exceeds_raw_clamps_to_zero(self):
        inputs = WIPAgingAdjustedInputs(
            raw_age_hours=Decimal("48"),
            total_hold_duration_hours=Decimal("100"),
        )
        assert calculate_wip_aging_adjusted(inputs).value == Decimal("0.00")


class TestHoldResolutionRate:
    def test_standard_mode_textbook(self):
        # 8 / 10 = 80%
        result = calculate_hold_resolution_rate(HoldResolutionInputs(resolved_on_time=8, total_resolved=10))
        assert result.value == Decimal("80.00")

    def test_zero_resolved_yields_zero(self):
        assert calculate_hold_resolution_rate(
            HoldResolutionInputs(resolved_on_time=0, total_resolved=0)
        ).value == Decimal("0")

    def test_on_time_exceeds_total_raises(self):
        with pytest.raises(ValueError):
            calculate_hold_resolution_rate(HoldResolutionInputs(resolved_on_time=15, total_resolved=10))
