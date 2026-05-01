"""Phase 1 dual-view orchestrators: Performance, Quality Rate, Throughput, Lead Time, Cycle Time."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.services.calculations.performance import (
    CycleTimeInputs,
    ExpectedOutputInputs,
    LeadTimeInputs,
    PerformanceInputs,
    QualityRateInputs,
    ThroughputInputs,
    calculate_cycle_time,
    calculate_expected_output,
    calculate_lead_time,
    calculate_performance,
    calculate_quality_rate,
    calculate_throughput,
)


class TestPerformance:
    def test_standard_mode_textbook(self):
        # (0.1 × 100) / 8 × 100 = 125%
        inputs = PerformanceInputs(
            units_produced=100,
            run_time_hours=Decimal("8"),
            ideal_cycle_time_hours=Decimal("0.1"),
        )
        result = calculate_performance(inputs)
        assert result.metric_name == "performance"
        assert result.value.performance_pct == Decimal("125.00")
        assert result.value.actual_rate_units_per_hour == Decimal("12.50")

    def test_site_adjusted_equals_standard_in_phase_1(self):
        inputs = PerformanceInputs(
            units_produced=100,
            run_time_hours=Decimal("8"),
            ideal_cycle_time_hours=Decimal("0.1"),
        )
        assert (
            calculate_performance(inputs, "standard").value.performance_pct
            == calculate_performance(inputs, "site_adjusted").value.performance_pct
        )

    def test_zero_runtime_yields_zero(self):
        inputs = PerformanceInputs(
            units_produced=0,
            run_time_hours=Decimal("0"),
            ideal_cycle_time_hours=Decimal("0.1"),
        )
        assert calculate_performance(inputs).value.performance_pct == Decimal("0")


class TestQualityRate:
    def test_standard_mode_textbook(self):
        inputs = QualityRateInputs(units_produced=100, defect_count=5, scrap_count=3)
        result = calculate_quality_rate(inputs)
        assert result.value.quality_rate_pct == Decimal("92.00")
        assert result.value.good_units == 92

    def test_zero_units_yields_zero(self):
        inputs = QualityRateInputs(units_produced=0, defect_count=0, scrap_count=0)
        assert calculate_quality_rate(inputs).value.quality_rate_pct == Decimal("0")


class TestThroughput:
    def test_standard_mode_textbook(self):
        inputs = ThroughputInputs(units_produced=400, run_time_hours=Decimal("8"))
        assert calculate_throughput(inputs).value == Decimal("50.00")

    def test_zero_runtime_yields_zero(self):
        inputs = ThroughputInputs(units_produced=400, run_time_hours=Decimal("0"))
        assert calculate_throughput(inputs).value == Decimal("0")


class TestLeadTime:
    def test_standard_mode_textbook(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 11, tzinfo=timezone.utc)
        inputs = LeadTimeInputs(start_date=start, end_date=end)
        # (10 days difference) + 1 = 11 days inclusive
        assert calculate_lead_time(inputs).value == 11

    def test_negative_range_returns_none(self):
        start = datetime(2026, 1, 11, tzinfo=timezone.utc)
        end = datetime(2026, 1, 1, tzinfo=timezone.utc)
        inputs = LeadTimeInputs(start_date=start, end_date=end)
        assert calculate_lead_time(inputs).value is None


class TestCycleTime:
    def test_standard_mode_textbook(self):
        inputs = CycleTimeInputs(total_run_time_hours=Decimal("12.5"))
        assert calculate_cycle_time(inputs).value == Decimal("12.50")

    def test_negative_input_rejected(self):
        with pytest.raises(ValidationError):
            CycleTimeInputs(total_run_time_hours=Decimal("-1"))


class TestExpectedOutput:
    def test_standard_mode_textbook(self):
        # 80 actual at 80% efficiency → 100 expected
        inputs = ExpectedOutputInputs(actual_output=80, efficiency_pct=Decimal("80"))
        assert calculate_expected_output(inputs).value == 100

    def test_perfect_efficiency_yields_actual(self):
        inputs = ExpectedOutputInputs(actual_output=100, efficiency_pct=Decimal("100"))
        assert calculate_expected_output(inputs).value == 100

    def test_zero_efficiency_rejected(self):
        with pytest.raises(ValidationError):
            ExpectedOutputInputs(actual_output=80, efficiency_pct=Decimal("0"))
