"""
Unit tests for Production Line Simulation v2.0 Validation Module

Tests domain validation rules, error detection, and warning generation.
"""

import pytest
from typing import List

from backend.simulation_v2.validation import validate_simulation_config
from backend.simulation_v2.models import (
    OperationInput,
    ScheduleConfig,
    DemandInput,
    BreakdownInput,
    SimulationConfig,
    DemandMode,
    ValidationSeverity,
)


class TestValidateSimulationConfig:
    """Test the main validate_simulation_config function."""

    def test_valid_config_returns_valid_report(self, simple_config: SimulationConfig):
        """Test that a valid config passes validation."""
        report = validate_simulation_config(simple_config)

        assert report.is_valid is True
        assert report.can_proceed is True
        assert len(report.errors) == 0
        assert report.products_count == 1
        assert report.operations_count == 3

    def test_valid_multi_product_config(self, multi_product_config: SimulationConfig):
        """Test validation of multi-product configuration."""
        report = validate_simulation_config(multi_product_config)

        assert report.is_valid is True
        assert report.products_count == 2

    def test_valid_mix_driven_config(self, mix_driven_config: SimulationConfig):
        """Test validation of mix-driven configuration."""
        report = validate_simulation_config(mix_driven_config)

        assert report.is_valid is True


class TestOperationSequenceValidation:
    """Test operation sequence validation rules."""

    def test_duplicate_steps_error(self, simple_schedule, simple_demand):
        """Test that duplicate step numbers cause an error."""
        operations = [
            OperationInput(product="A", step=1, operation="Op1", machine_tool="M1", sam_min=1.0),
            OperationInput(product="A", step=1, operation="Op2", machine_tool="M2", sam_min=1.0),  # Duplicate step
        ]

        config = SimulationConfig(
            operations=operations, schedule=simple_schedule, demands=simple_demand, mode=DemandMode.DEMAND_DRIVEN
        )

        # Update demand to match operations
        config.demands[0].product = "A"

        report = validate_simulation_config(config)

        assert report.is_valid is False
        assert any("duplicate" in e.message.lower() for e in report.errors)

    def test_gap_in_steps_error(self, simple_schedule):
        """Test that gaps in step sequence cause an error."""
        operations = [
            OperationInput(product="A", step=1, operation="Op1", machine_tool="M1", sam_min=1.0),
            OperationInput(
                product="A", step=3, operation="Op3", machine_tool="M2", sam_min=1.0  # Gap - step 2 missing
            ),
        ]

        demand = [DemandInput(product="A", daily_demand=100)]

        config = SimulationConfig(
            operations=operations, schedule=simple_schedule, demands=demand, mode=DemandMode.DEMAND_DRIVEN
        )

        report = validate_simulation_config(config)

        assert report.is_valid is False
        assert any("gap" in e.message.lower() for e in report.errors)


class TestProductConsistencyValidation:
    """Test product consistency validation rules."""

    def test_demand_without_operations_error(self, simple_schedule):
        """Test that demand for non-existent product causes error."""
        operations = [
            OperationInput(product="A", step=1, operation="Op1", machine_tool="M1", sam_min=1.0),
        ]

        demand = [
            DemandInput(product="A", daily_demand=100),
            DemandInput(product="B", daily_demand=50),  # No operations for B
        ]

        config = SimulationConfig(
            operations=operations, schedule=simple_schedule, demands=demand, mode=DemandMode.DEMAND_DRIVEN
        )

        report = validate_simulation_config(config)

        assert report.is_valid is False
        assert any("B" in e.product for e in report.errors if e.product)

    def test_operations_without_demand_warning(self, simple_schedule):
        """Test that operations without demand cause warning."""
        operations = [
            OperationInput(product="A", step=1, operation="Op1", machine_tool="M1", sam_min=1.0),
            OperationInput(product="B", step=1, operation="Op1", machine_tool="M2", sam_min=1.0),  # No demand for B
        ]

        demand = [DemandInput(product="A", daily_demand=100)]

        config = SimulationConfig(
            operations=operations, schedule=simple_schedule, demands=demand, mode=DemandMode.DEMAND_DRIVEN
        )

        report = validate_simulation_config(config)

        # Should pass but with warning
        assert report.is_valid is True
        assert any("B" in w.product for w in report.warnings if w.product)


class TestDemandValidation:
    """Test demand configuration validation."""

    def test_mix_driven_percentages_not_100_error(self, simple_schedule):
        """Test that mix percentages not summing to 100 causes error."""
        operations = [
            OperationInput(product="A", step=1, operation="Op1", machine_tool="M1", sam_min=1.0),
            OperationInput(product="B", step=1, operation="Op1", machine_tool="M2", sam_min=1.0),
        ]

        demand = [
            DemandInput(product="A", mix_share_pct=50.0),
            DemandInput(product="B", mix_share_pct=40.0),  # Total = 90, not 100
        ]

        config = SimulationConfig(
            operations=operations,
            schedule=simple_schedule,
            demands=demand,
            mode=DemandMode.MIX_DRIVEN,
            total_demand=500,
        )

        report = validate_simulation_config(config)

        assert report.is_valid is False
        assert any("100%" in e.message or "mix" in e.message.lower() for e in report.errors)

    def test_demand_driven_no_demand_warning(self, simple_schedule):
        """Test that products without demand in demand-driven mode get warning."""
        operations = [
            OperationInput(product="A", step=1, operation="Op1", machine_tool="M1", sam_min=1.0),
        ]

        demand = [DemandInput(product="A")]  # No daily or weekly demand

        config = SimulationConfig(
            operations=operations, schedule=simple_schedule, demands=demand, mode=DemandMode.DEMAND_DRIVEN
        )

        report = validate_simulation_config(config)

        # Should pass but with warning
        assert len(report.warnings) > 0


class TestMachineToolValidation:
    """Test machine tool consistency validation."""

    def test_similar_tool_names_warning(self, simple_schedule):
        """Test that similar tool names generate warning."""
        operations = [
            OperationInput(product="A", step=1, operation="Op1", machine_tool="Overlock 4-thread", sam_min=1.0),
            OperationInput(
                product="A",
                step=2,
                operation="Op2",
                machine_tool="Overlock 4 thread",  # Very similar, likely typo
                sam_min=1.0,
            ),
        ]

        demand = [DemandInput(product="A", daily_demand=100)]

        config = SimulationConfig(
            operations=operations, schedule=simple_schedule, demands=demand, mode=DemandMode.DEMAND_DRIVEN
        )

        report = validate_simulation_config(config)

        # Should have similarity warning
        assert any("similar" in w.message.lower() for w in report.warnings)


class TestBreakdownValidation:
    """Test breakdown configuration validation."""

    def test_breakdown_for_nonexistent_machine_warning(self, simple_config):
        """Test that breakdown for unused machine generates warning."""
        simple_config.breakdowns = [BreakdownInput(machine_tool="Nonexistent Machine", breakdown_pct=5.0)]

        report = validate_simulation_config(simple_config)

        assert any("Nonexistent Machine" in w.message for w in report.warnings)


class TestScheduleValidation:
    """Test schedule configuration validation."""

    def test_unused_shift_info(self):
        """Test that unused shifts generate info message."""
        schedule = ScheduleConfig(
            shifts_enabled=2, shift1_hours=8.0, shift2_hours=0.0, work_days=5  # Enabled but 0 hours
        )

        operations = [
            OperationInput(product="A", step=1, operation="Op1", machine_tool="M1", sam_min=1.0),
        ]

        demand = [DemandInput(product="A", daily_demand=100)]

        config = SimulationConfig(
            operations=operations, schedule=schedule, demands=demand, mode=DemandMode.DEMAND_DRIVEN
        )

        report = validate_simulation_config(config)

        assert any("shift2" in i.message.lower() for i in report.info)


class TestConfigurationLimits:
    """Test configuration limit validation."""

    def test_too_many_products_error(self, simple_schedule):
        """Test that exceeding max products causes error."""
        # Create 6 products (max is 5)
        operations = []
        demands = []
        for i in range(6):
            operations.append(
                OperationInput(product=f"PRODUCT_{i}", step=1, operation="Op1", machine_tool="M1", sam_min=1.0)
            )
            demands.append(DemandInput(product=f"PRODUCT_{i}", daily_demand=100))

        config = SimulationConfig(
            operations=operations, schedule=simple_schedule, demands=demands, mode=DemandMode.DEMAND_DRIVEN
        )

        report = validate_simulation_config(config)

        assert report.is_valid is False
        assert any("too many products" in e.message.lower() for e in report.errors)
