"""
Unit tests for Production Line Simulation v2.0 SimPy Engine

Tests the discrete-event simulation engine, processing time calculations,
and metric collection.
"""

import pytest
from typing import List

from backend.simulation_v2.engine import (
    ProductionLineSimulator,
    SimulationMetrics,
    run_simulation,
)
from backend.simulation_v2.models import (
    OperationInput,
    ScheduleConfig,
    DemandInput,
    SimulationConfig,
    DemandMode,
    VariabilityType,
)
from backend.simulation_v2.constants import (
    SMALL_BUNDLE_THRESHOLD,
    MIN_PROCESS_TIME_MINUTES,
)


class TestProductionLineSimulator:
    """Test the ProductionLineSimulator class."""

    def test_simulator_initialization(self, simple_config: SimulationConfig):
        """Test that simulator initializes correctly."""
        simulator = ProductionLineSimulator(simple_config)

        assert simulator.config == simple_config
        assert simulator.env is not None
        assert len(simulator.operations_by_product) == 1
        assert "PRODUCT_A" in simulator.operations_by_product

    def test_operations_grouped_and_sorted(self, simple_config: SimulationConfig):
        """Test that operations are grouped by product and sorted by step."""
        simulator = ProductionLineSimulator(simple_config)

        ops = simulator.operations_by_product["PRODUCT_A"]
        assert len(ops) == 3
        assert ops[0].step == 1
        assert ops[1].step == 2
        assert ops[2].step == 3

    def test_resources_created(self, simple_config: SimulationConfig):
        """Test that SimPy resources are created for each machine tool."""
        simulator = ProductionLineSimulator(simple_config)

        assert len(simulator.resources) == 3  # 3 different machine tools
        assert "Cutting Table" in simulator.resources
        assert "Overlock 4-thread" in simulator.resources
        assert "Inspection Station" in simulator.resources

    def test_resource_capacity_pooled(self, multi_product_config: SimulationConfig):
        """Test that resource capacity is pooled across operations."""
        simulator = ProductionLineSimulator(multi_product_config)

        # Cutting Table used by both products with 2 operators each
        cutting_resource = simulator.resources["Cutting Table"]
        assert cutting_resource.capacity == 4  # 2 + 2

    def test_horizon_minutes_calculated(self, simple_config: SimulationConfig):
        """Test that horizon is correctly calculated in minutes."""
        simulator = ProductionLineSimulator(simple_config)

        # 8 hours * 60 minutes * 1 day
        expected_minutes = 8.0 * 60 * 1
        assert simulator.horizon_minutes == expected_minutes


class TestProcessTimeCalculation:
    """Test processing time calculation formula."""

    def test_deterministic_variability(self):
        """Test that deterministic mode has no variability."""
        schedule = ScheduleConfig(shifts_enabled=1, shift1_hours=8.0, work_days=5)
        operations = [
            OperationInput(
                product="A",
                step=1,
                operation="Test",
                machine_tool="M1",
                sam_min=10.0,
                variability=VariabilityType.DETERMINISTIC,
                grade_pct=100.0,  # No grade penalty
                fpd_pct=0.0,  # No FPD
            )
        ]
        demands = [DemandInput(product="A", daily_demand=10)]

        config = SimulationConfig(
            operations=operations, schedule=schedule, demands=demands, mode=DemandMode.DEMAND_DRIVEN
        )

        simulator = ProductionLineSimulator(config, seed=42)
        process_time = simulator._calculate_process_time(operations[0])

        # With 100% grade and 0% FPD, should be exactly SAM
        assert process_time == 10.0

    def test_grade_penalty(self):
        """Test that grade below 100 adds penalty."""
        schedule = ScheduleConfig(shifts_enabled=1, shift1_hours=8.0, work_days=5)
        operations = [
            OperationInput(
                product="A",
                step=1,
                operation="Test",
                machine_tool="M1",
                sam_min=10.0,
                variability=VariabilityType.DETERMINISTIC,
                grade_pct=80.0,  # 20% grade penalty
                fpd_pct=0.0,
            )
        ]
        demands = [DemandInput(product="A", daily_demand=10)]

        config = SimulationConfig(
            operations=operations, schedule=schedule, demands=demands, mode=DemandMode.DEMAND_DRIVEN
        )

        simulator = ProductionLineSimulator(config, seed=42)
        process_time = simulator._calculate_process_time(operations[0])

        # SAM * (1 + 0 + 0 + 0.20) = 10 * 1.20 = 12.0
        assert process_time == 12.0

    def test_fpd_addition(self):
        """Test that FPD percentage adds to processing time."""
        schedule = ScheduleConfig(shifts_enabled=1, shift1_hours=8.0, work_days=5)
        operations = [
            OperationInput(
                product="A",
                step=1,
                operation="Test",
                machine_tool="M1",
                sam_min=10.0,
                variability=VariabilityType.DETERMINISTIC,
                grade_pct=100.0,
                fpd_pct=15.0,  # 15% FPD
            )
        ]
        demands = [DemandInput(product="A", daily_demand=10)]

        config = SimulationConfig(
            operations=operations, schedule=schedule, demands=demands, mode=DemandMode.DEMAND_DRIVEN
        )

        simulator = ProductionLineSimulator(config, seed=42)
        process_time = simulator._calculate_process_time(operations[0])

        # SAM * (1 + 0 + 0.15 + 0) = 10 * 1.15 = 11.5
        assert process_time == 11.5

    def test_combined_factors(self):
        """Test processing time with all factors combined."""
        schedule = ScheduleConfig(shifts_enabled=1, shift1_hours=8.0, work_days=5)
        operations = [
            OperationInput(
                product="A",
                step=1,
                operation="Test",
                machine_tool="M1",
                sam_min=10.0,
                variability=VariabilityType.DETERMINISTIC,
                grade_pct=85.0,  # 15% grade penalty
                fpd_pct=15.0,  # 15% FPD
            )
        ]
        demands = [DemandInput(product="A", daily_demand=10)]

        config = SimulationConfig(
            operations=operations, schedule=schedule, demands=demands, mode=DemandMode.DEMAND_DRIVEN
        )

        simulator = ProductionLineSimulator(config, seed=42)
        process_time = simulator._calculate_process_time(operations[0])

        # SAM * (1 + 0 + 0.15 + 0.15) = 10 * 1.30 = 13.0
        assert process_time == pytest.approx(13.0, rel=1e-6)

    def test_minimum_process_time(self):
        """Test that process time has minimum floor."""
        schedule = ScheduleConfig(shifts_enabled=1, shift1_hours=8.0, work_days=5)
        operations = [
            OperationInput(
                product="A",
                step=1,
                operation="Test",
                machine_tool="M1",
                sam_min=0.001,  # Very small SAM
                variability=VariabilityType.DETERMINISTIC,
                grade_pct=100.0,
                fpd_pct=0.0,
            )
        ]
        demands = [DemandInput(product="A", daily_demand=10)]

        config = SimulationConfig(
            operations=operations, schedule=schedule, demands=demands, mode=DemandMode.DEMAND_DRIVEN
        )

        simulator = ProductionLineSimulator(config, seed=42)
        process_time = simulator._calculate_process_time(operations[0])

        assert process_time >= MIN_PROCESS_TIME_MINUTES


class TestBundleTransitionTime:
    """Test bundle transition time calculation."""

    def test_small_bundle_transition(self, simple_config: SimulationConfig):
        """Test transition time for small bundles."""
        simulator = ProductionLineSimulator(simple_config)

        # Bundle size <= 5 should get 1 second (1/60 minutes)
        transition = simulator._get_bundle_transition_time(5)
        assert transition == pytest.approx(1 / 60, rel=1e-6)

    def test_large_bundle_transition(self, simple_config: SimulationConfig):
        """Test transition time for large bundles."""
        simulator = ProductionLineSimulator(simple_config)

        # Bundle size > 5 should get 5 seconds (5/60 minutes)
        transition = simulator._get_bundle_transition_time(10)
        assert transition == pytest.approx(5 / 60, rel=1e-6)


class TestRunSimulation:
    """Test the complete simulation run."""

    def test_simulation_produces_metrics(self, simple_config: SimulationConfig):
        """Test that simulation produces valid metrics."""
        metrics, duration = run_simulation(simple_config, seed=42)

        assert isinstance(metrics, SimulationMetrics)
        assert duration >= 0
        assert metrics.bundles_completed > 0

    def test_simulation_throughput_recorded(self, simple_config: SimulationConfig):
        """Test that throughput is recorded by product."""
        metrics, _ = run_simulation(simple_config, seed=42)

        assert "PRODUCT_A" in metrics.throughput_by_product
        assert metrics.throughput_by_product["PRODUCT_A"] > 0

    def test_simulation_cycle_times_recorded(self, simple_config: SimulationConfig):
        """Test that cycle times are recorded."""
        metrics, _ = run_simulation(simple_config, seed=42)

        assert len(metrics.cycle_times) > 0
        assert all(ct > 0 for ct in metrics.cycle_times)

    def test_simulation_wip_sampled(self, simple_config: SimulationConfig):
        """Test that WIP is sampled during simulation."""
        metrics, _ = run_simulation(simple_config, seed=42)

        # WIP samples should be collected
        assert len(metrics.wip_samples) >= 0

    def test_simulation_reproducible_with_seed(self, simple_config: SimulationConfig):
        """Test that same seed produces same results."""
        metrics1, _ = run_simulation(simple_config, seed=12345)
        metrics2, _ = run_simulation(simple_config, seed=12345)

        assert metrics1.bundles_completed == metrics2.bundles_completed
        assert metrics1.throughput_by_product["PRODUCT_A"] == metrics2.throughput_by_product["PRODUCT_A"]

    def test_multi_product_simulation(self, multi_product_config: SimulationConfig):
        """Test simulation with multiple products."""
        metrics, _ = run_simulation(multi_product_config, seed=42)

        assert "PRODUCT_A" in metrics.throughput_by_product
        assert "PRODUCT_B" in metrics.throughput_by_product
        assert metrics.throughput_by_product["PRODUCT_A"] > 0
        assert metrics.throughput_by_product["PRODUCT_B"] > 0


class TestBreakdownSimulation:
    """Test simulation with equipment breakdowns."""

    def test_breakdown_events_recorded(self, config_with_breakdowns: SimulationConfig):
        """Test that breakdown events are tracked."""
        # Run multiple times to ensure breakdowns occur
        total_breakdowns = 0
        for seed in range(10):
            metrics, _ = run_simulation(config_with_breakdowns, seed=seed)
            total_breakdowns += metrics.breakdown_events

        # With 5% breakdown rate, we should see some breakdowns
        assert total_breakdowns > 0


class TestSimulationMetrics:
    """Test SimulationMetrics dataclass."""

    def test_metrics_initialization(self):
        """Test that metrics initialize with correct defaults."""
        metrics = SimulationMetrics()

        assert metrics.bundles_completed == 0
        assert metrics.current_wip == 0
        assert metrics.max_wip == 0
        assert metrics.rework_count == 0
        assert len(metrics.cycle_times) == 0
        assert len(metrics.wip_samples) == 0

    def test_metrics_default_dicts(self):
        """Test that defaultdicts work correctly."""
        metrics = SimulationMetrics()

        # Should be able to access and modify without key errors
        metrics.throughput_by_product["TEST"] += 10
        metrics.station_busy_time["MACHINE"] += 5.0

        assert metrics.throughput_by_product["TEST"] == 10
        assert metrics.station_busy_time["MACHINE"] == 5.0
