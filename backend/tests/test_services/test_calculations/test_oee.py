"""Phase 1 dual-view orchestrator: OEE."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.services.calculations.oee import METRIC_NAME, OEEInputs, calculate_oee
from backend.services.calculations.result import CalculationResult


class TestOEEOrchestrator:
    def test_standard_mode_textbook_value(self):
        inputs = OEEInputs(
            availability_pct=Decimal("90"),
            performance_pct=Decimal("90"),
            quality_pct=Decimal("90"),
        )

        result = calculate_oee(inputs, mode="standard")

        assert isinstance(result, CalculationResult)
        assert result.metric_name == METRIC_NAME
        assert result.mode == "standard"
        assert result.value == Decimal("72.90")

    def test_site_adjusted_equals_standard_in_phase_1(self):
        """Phase 3 will allow these to diverge once the assumption registry is wired."""
        inputs = OEEInputs(
            availability_pct=Decimal("85"),
            performance_pct=Decimal("95"),
            quality_pct=Decimal("98"),
        )

        std = calculate_oee(inputs, mode="standard")
        adj = calculate_oee(inputs, mode="site_adjusted")

        assert std.value == adj.value
        assert adj.mode == "site_adjusted"
        assert adj.assumptions_applied == []

    def test_perfect_oee(self):
        inputs = OEEInputs(
            availability_pct=Decimal("100"),
            performance_pct=Decimal("100"),
            quality_pct=Decimal("100"),
        )

        assert calculate_oee(inputs).value == Decimal("100.00")

    def test_zero_availability_yields_zero(self):
        inputs = OEEInputs(
            availability_pct=Decimal("0"),
            performance_pct=Decimal("100"),
            quality_pct=Decimal("100"),
        )

        assert calculate_oee(inputs).value == Decimal("0.00")

    def test_default_mode_is_standard(self):
        inputs = OEEInputs(
            availability_pct=Decimal("80"),
            performance_pct=Decimal("80"),
            quality_pct=Decimal("80"),
        )

        assert calculate_oee(inputs).mode == "standard"

    def test_inputs_consumed_captures_all_three_components(self):
        inputs = OEEInputs(
            availability_pct=Decimal("80"),
            performance_pct=Decimal("90"),
            quality_pct=Decimal("95"),
        )

        result = calculate_oee(inputs)

        assert set(result.inputs_consumed.keys()) == {
            "availability_pct",
            "performance_pct",
            "quality_pct",
        }

    def test_calculated_at_is_timezone_aware_and_recent(self):
        before = datetime.now(timezone.utc) - timedelta(seconds=1)
        inputs = OEEInputs(
            availability_pct=Decimal("90"),
            performance_pct=Decimal("90"),
            quality_pct=Decimal("90"),
        )

        result = calculate_oee(inputs)

        after = datetime.now(timezone.utc) + timedelta(seconds=1)
        assert result.calculated_at.tzinfo is not None
        assert before <= result.calculated_at <= after

    def test_negative_input_rejected_by_inputs_model(self):
        with pytest.raises(ValidationError):
            OEEInputs(
                availability_pct=Decimal("-1"),
                performance_pct=Decimal("90"),
                quality_pct=Decimal("90"),
            )

    def test_input_above_cap_rejected_by_inputs_model(self):
        with pytest.raises(ValidationError):
            OEEInputs(
                availability_pct=Decimal("151"),
                performance_pct=Decimal("90"),
                quality_pct=Decimal("90"),
            )
