"""
Unit tests for Production Line Simulation v2.0 Pydantic Models

Tests input validation, output model construction, and edge cases.
"""

import pytest
from pydantic import ValidationError

from backend.simulation_v2.models import (
    OperationInput,
    ScheduleConfig,
    DemandInput,
    BreakdownInput,
    SimulationConfig,
    ValidationIssue,
    ValidationReport,
    DemandMode,
    VariabilityType,
    ValidationSeverity,
    CoverageStatus,
    WeeklyDemandCapacityRow,
    DailySummary,
    StationPerformanceRow,
)


class TestOperationInput:
    """Test OperationInput model validation."""

    def test_valid_operation(self):
        """Test creating a valid operation."""
        op = OperationInput(
            product="TEST_PRODUCT",
            step=1,
            operation="Test operation",
            machine_tool="Test Machine",
            sam_min=2.5
        )
        assert op.product == "TEST_PRODUCT"
        assert op.step == 1
        assert op.sam_min == 2.5
        # Check defaults
        assert op.operators == 1
        assert op.grade_pct == 85.0
        assert op.fpd_pct == 15.0
        assert op.rework_pct == 0.0
        assert op.variability == VariabilityType.TRIANGULAR

    def test_operation_missing_required_fields(self):
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError) as exc_info:
            OperationInput(
                product="TEST",
                step=1
                # Missing operation, machine_tool, sam_min
            )
        errors = exc_info.value.errors()
        assert len(errors) >= 3

    def test_operation_invalid_step(self):
        """Test that step must be positive."""
        with pytest.raises(ValidationError):
            OperationInput(
                product="TEST",
                step=0,  # Must be > 0
                operation="Test",
                machine_tool="Machine",
                sam_min=1.0
            )

    def test_operation_invalid_sam(self):
        """Test that SAM must be positive."""
        with pytest.raises(ValidationError):
            OperationInput(
                product="TEST",
                step=1,
                operation="Test",
                machine_tool="Machine",
                sam_min=-1.0  # Must be > 0
            )

    def test_operation_invalid_percentages(self):
        """Test that percentages must be in valid range."""
        with pytest.raises(ValidationError):
            OperationInput(
                product="TEST",
                step=1,
                operation="Test",
                machine_tool="Machine",
                sam_min=1.0,
                grade_pct=150  # Must be <= 100
            )


class TestScheduleConfig:
    """Test ScheduleConfig model validation."""

    def test_valid_single_shift(self):
        """Test valid single shift configuration."""
        schedule = ScheduleConfig(
            shifts_enabled=1,
            shift1_hours=8.0,
            work_days=5
        )
        assert schedule.daily_planned_hours == 8.0
        assert schedule.weekly_base_hours == 40.0

    def test_valid_two_shift(self):
        """Test valid two shift configuration."""
        schedule = ScheduleConfig(
            shifts_enabled=2,
            shift1_hours=8.0,
            shift2_hours=8.0,
            work_days=5
        )
        assert schedule.daily_planned_hours == 16.0
        assert schedule.weekly_base_hours == 80.0

    def test_invalid_shifts_enabled(self):
        """Test that shifts_enabled must be 1-3."""
        with pytest.raises(ValidationError):
            ScheduleConfig(
                shifts_enabled=0,
                shift1_hours=8.0,
                work_days=5
            )

    def test_total_hours_exceed_24(self):
        """Test that total shift hours cannot exceed 24."""
        with pytest.raises(ValidationError):
            ScheduleConfig(
                shifts_enabled=3,
                shift1_hours=9.0,
                shift2_hours=9.0,
                shift3_hours=9.0,  # Total = 27 > 24
                work_days=5
            )

    def test_overtime_configuration(self):
        """Test overtime calculations."""
        schedule = ScheduleConfig(
            shifts_enabled=1,
            shift1_hours=8.0,
            work_days=5,
            ot_enabled=True,
            weekday_ot_hours=2.0,
            weekend_ot_days=1,
            weekend_ot_hours=8.0
        )
        # Base: 8*5 = 40, Weekday OT: 2*5 = 10, Weekend: 8*1 = 8
        assert schedule.weekly_total_hours == 58.0


class TestDemandInput:
    """Test DemandInput model validation."""

    def test_valid_demand_driven(self):
        """Test valid demand-driven demand."""
        demand = DemandInput(
            product="TEST",
            daily_demand=100,
            weekly_demand=500
        )
        assert demand.product == "TEST"
        assert demand.bundle_size == 1  # Default

    def test_valid_mix_driven(self):
        """Test valid mix-driven demand."""
        demand = DemandInput(
            product="TEST",
            mix_share_pct=50.0,
            bundle_size=10
        )
        assert demand.mix_share_pct == 50.0

    def test_invalid_bundle_size(self):
        """Test that bundle_size must be positive."""
        with pytest.raises(ValidationError):
            DemandInput(
                product="TEST",
                bundle_size=0  # Must be >= 1
            )


class TestSimulationConfig:
    """Test SimulationConfig model validation."""

    def test_mix_mode_requires_total_demand(self):
        """Test that mix-driven mode requires total_demand."""
        with pytest.raises(ValidationError) as exc_info:
            SimulationConfig(
                operations=[
                    OperationInput(
                        product="A",
                        step=1,
                        operation="Op",
                        machine_tool="M",
                        sam_min=1.0
                    )
                ],
                schedule=ScheduleConfig(
                    shifts_enabled=1,
                    shift1_hours=8.0,
                    work_days=5
                ),
                demands=[
                    DemandInput(product="A", mix_share_pct=100)
                ],
                mode=DemandMode.MIX_DRIVEN
                # Missing total_demand
            )
        assert "total_demand" in str(exc_info.value)


class TestValidationModels:
    """Test validation-related models."""

    def test_validation_issue(self):
        """Test ValidationIssue creation."""
        issue = ValidationIssue(
            severity=ValidationSeverity.ERROR,
            category="test",
            message="Test error message",
            recommendation="Fix it"
        )
        assert issue.severity == ValidationSeverity.ERROR
        assert issue.product is None

    def test_validation_report(self):
        """Test ValidationReport properties."""
        report = ValidationReport()
        assert report.is_valid is True
        assert report.has_errors is False

        report.errors.append(
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                category="test",
                message="Error"
            )
        )
        assert report.has_errors is True


class TestOutputModels:
    """Test output block models."""

    def test_weekly_demand_capacity_row(self):
        """Test WeeklyDemandCapacityRow creation."""
        row = WeeklyDemandCapacityRow(
            product="TEST",
            weekly_demand_pcs=1000,
            max_weekly_capacity_pcs=1100,
            demand_coverage_pct=110.0,
            status=CoverageStatus.OK
        )
        assert row.status == CoverageStatus.OK

    def test_daily_summary(self):
        """Test DailySummary creation."""
        summary = DailySummary(
            total_shifts_per_day=2,
            daily_planned_hours=16.0,
            daily_throughput_pcs=500,
            daily_demand_pcs=480,
            daily_coverage_pct=104.2,
            avg_cycle_time_min=32.5,
            avg_wip_pcs=45,
            bundles_processed_per_day=50,
            bundle_size_pcs="10"
        )
        assert summary.daily_coverage_pct == 104.2

    def test_station_performance_row(self):
        """Test StationPerformanceRow creation."""
        row = StationPerformanceRow(
            product="TEST",
            step=1,
            operation="Cut",
            machine_tool="Cutter",
            sequence="Prep",
            grouping="CUT",
            operators=2,
            total_pieces_processed=1000,
            total_busy_time_min=480.0,
            avg_processing_time_min=0.48,
            util_pct=60.0,
            queue_wait_time_min=2.5,
            is_bottleneck=False,
            is_donor=False
        )
        assert row.util_pct == 60.0
