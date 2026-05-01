"""Phase 1 dual-view orchestrator: Efficiency."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.services.calculations.efficiency import (
    EfficiencyInputs,
    calculate_efficiency,
)


class TestEfficiency:
    def test_standard_mode_textbook(self):
        # (100 × 0.1) / (5 × 8) × 100 = 25%
        inputs = EfficiencyInputs(
            units_produced=100,
            ideal_cycle_time_hours=Decimal("0.1"),
            employees_count=5,
            scheduled_hours=Decimal("8"),
        )
        result = calculate_efficiency(inputs)
        assert result.metric_name == "efficiency"
        assert result.value == Decimal("25.00")

    def test_site_adjusted_equals_standard_in_phase_1(self):
        inputs = EfficiencyInputs(
            units_produced=100,
            ideal_cycle_time_hours=Decimal("0.1"),
            employees_count=5,
            scheduled_hours=Decimal("8"),
        )
        std = calculate_efficiency(inputs, "standard")
        adj = calculate_efficiency(inputs, "site_adjusted")
        assert std.value == adj.value

    def test_capped_at_150_percent(self):
        # very generous inputs — would be 1000% uncapped
        inputs = EfficiencyInputs(
            units_produced=10000,
            ideal_cycle_time_hours=Decimal("1"),
            employees_count=5,
            scheduled_hours=Decimal("8"),
        )
        assert calculate_efficiency(inputs).value == Decimal("150")

    def test_zero_employees_yields_zero(self):
        inputs = EfficiencyInputs(
            units_produced=100,
            ideal_cycle_time_hours=Decimal("0.1"),
            employees_count=0,
            scheduled_hours=Decimal("8"),
        )
        assert calculate_efficiency(inputs).value == Decimal("0")

    def test_zero_cycle_time_rejected(self):
        with pytest.raises(ValidationError):
            EfficiencyInputs(
                units_produced=100,
                ideal_cycle_time_hours=Decimal("0"),
                employees_count=5,
                scheduled_hours=Decimal("8"),
            )
