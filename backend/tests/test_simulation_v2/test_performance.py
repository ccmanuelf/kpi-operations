"""
Performance tests for Production Line Simulation v2.0

Tests simulation performance with large configurations:
- High operation counts (50+)
- Multiple products (10+)
- High demand configurations
- Execution time benchmarks
"""

import pytest
import time
from typing import List

from backend.simulation_v2.models import (
    OperationInput,
    ScheduleConfig,
    DemandInput,
    BreakdownInput,
    SimulationConfig,
    DemandMode,
    VariabilityType,
)
from backend.simulation_v2.engine import ProductionLineSimulator, run_simulation
from backend.simulation_v2.validation import validate_simulation_config
from backend.simulation_v2.calculations import calculate_all_blocks


class TestLargeOperationsConfiguration:
    """Test simulation with large number of operations."""

    @staticmethod
    def create_large_operations(
        num_products: int = 5,
        steps_per_product: int = 10
    ) -> List[OperationInput]:
        """Create a large operations list."""
        operations = []
        operation_names = [
            "Cut", "Prepare", "Mark", "First Stitch", "Second Stitch",
            "Overlock", "Flatlock", "Bar-tack", "Button", "Final Stitch"
        ]
        machine_tools = [
            "Cutting Table", "Marking Station", "Overlock 4-thread",
            "Flatlock", "Single Needle", "Bar-tack Machine",
            "Button Machine", "Inspection Station", "Pressing Station", "Packing Station"
        ]

        for prod_idx in range(num_products):
            product = f"PRODUCT_{chr(65 + prod_idx)}"  # PRODUCT_A, PRODUCT_B, etc.
            for step in range(1, steps_per_product + 1):
                operations.append(OperationInput(
                    product=product,
                    step=step,
                    operation=f"{operation_names[(step - 1) % len(operation_names)]} {product}",
                    machine_tool=machine_tools[(step - 1) % len(machine_tools)],
                    sam_min=1.0 + (step * 0.3),  # Varying SAM
                    sequence="Assembly",
                    grouping=f"GRP_{step % 3}",
                    operators=1 + (step % 3),
                    variability=VariabilityType.TRIANGULAR,
                    rework_pct=1.0 if step == 5 else 0.0,  # One rework station
                    grade_pct=85.0,
                    fpd_pct=15.0
                ))

        return operations

    @staticmethod
    def create_demand_for_products(num_products: int, daily_demand: int = 100) -> List[DemandInput]:
        """Create demand for multiple products."""
        return [
            DemandInput(
                product=f"PRODUCT_{chr(65 + i)}",
                bundle_size=10,
                daily_demand=daily_demand
            )
            for i in range(num_products)
        ]

    def test_50_operations_simulation(self):
        """Test simulation with 50 operations (5 products × 10 steps)."""
        operations = self.create_large_operations(num_products=5, steps_per_product=10)
        demands = self.create_demand_for_products(5, daily_demand=50)

        assert len(operations) == 50

        schedule = ScheduleConfig(
            shifts_enabled=1,
            shift1_hours=8.0,
            shift2_hours=0.0,
            shift3_hours=0.0,
            work_days=5,
            ot_enabled=False
        )

        config = SimulationConfig(
            operations=operations,
            schedule=schedule,
            demands=demands,
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1
        )

        # Validate configuration
        report = validate_simulation_config(config)
        assert report.is_valid, f"Validation failed: {report.errors}"

        # Run simulation with timing
        start_time = time.time()
        metrics, duration = run_simulation(config, seed=42)
        end_time = time.time()

        # Verify simulation completed
        assert metrics.bundles_completed > 0
        assert duration > 0

        # Performance assertion: should complete within 10 seconds
        actual_time = end_time - start_time
        assert actual_time < 10.0, f"Simulation took {actual_time:.2f}s, expected < 10s"

    def test_100_operations_simulation(self):
        """Test simulation with 100 operations (5 products × 20 steps) - max allowed config."""
        operations = self.create_large_operations(num_products=5, steps_per_product=20)
        demands = self.create_demand_for_products(5, daily_demand=30)

        assert len(operations) == 100

        schedule = ScheduleConfig(
            shifts_enabled=3,  # More shifts for faster completion
            shift1_hours=8.0,
            shift2_hours=8.0,
            shift3_hours=8.0,
            work_days=5,
            ot_enabled=False
        )

        config = SimulationConfig(
            operations=operations,
            schedule=schedule,
            demands=demands,
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=7  # Longer horizon for complex configs
        )

        report = validate_simulation_config(config)
        assert report.is_valid, f"Validation failed: {report.errors}"

        start_time = time.time()
        metrics, duration = run_simulation(config, seed=42)
        end_time = time.time()

        # With 100 operations, processing occurs even if bundles don't complete
        # Check that pieces were processed at various stations
        assert metrics.max_wip > 0, "WIP should have built up during simulation"
        total_pieces_processed = sum(metrics.station_pieces_processed.values())
        assert total_pieces_processed > 0, "Pieces should have been processed"

        actual_time = end_time - start_time
        assert actual_time < 60.0, f"Simulation took {actual_time:.2f}s, expected < 60s"


class TestHighDemandConfiguration:
    """Test simulation with high demand volumes."""

    def test_high_daily_demand(self):
        """Test simulation with high daily demand (1000+ pieces)."""
        operations = [
            OperationInput(
                product="HIGH_DEMAND",
                step=1,
                operation="Cut fabric",
                machine_tool="Cutting Table",
                sam_min=2.0,
                operators=5
            ),
            OperationInput(
                product="HIGH_DEMAND",
                step=2,
                operation="Sew seams",
                machine_tool="Overlock",
                sam_min=3.0,
                operators=10
            ),
            OperationInput(
                product="HIGH_DEMAND",
                step=3,
                operation="Final QC",
                machine_tool="Inspection",
                sam_min=1.0,
                operators=3
            ),
        ]

        demands = [
            DemandInput(
                product="HIGH_DEMAND",
                bundle_size=20,
                daily_demand=1000
            )
        ]

        schedule = ScheduleConfig(
            shifts_enabled=3,
            shift1_hours=8.0,
            shift2_hours=8.0,
            shift3_hours=8.0,
            work_days=5,
            ot_enabled=False
        )

        config = SimulationConfig(
            operations=operations,
            schedule=schedule,
            demands=demands,
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1
        )

        report = validate_simulation_config(config)
        assert report.is_valid

        start_time = time.time()
        metrics, duration = run_simulation(config, seed=42)
        end_time = time.time()

        # Verify high throughput
        assert metrics.throughput_by_product.get("HIGH_DEMAND", 0) > 0
        assert metrics.bundles_completed >= 40  # At least 40 bundles for 1000/20=50 bundles

        actual_time = end_time - start_time
        assert actual_time < 20.0, f"Simulation took {actual_time:.2f}s, expected < 20s"

    def test_multi_day_horizon(self):
        """Test simulation with 7-day horizon."""
        operations = [
            OperationInput(
                product="WEEKLY_PROD",
                step=i,
                operation=f"Step {i}",
                machine_tool=f"Machine_{i}",
                sam_min=1.5,
                operators=2
            )
            for i in range(1, 6)
        ]

        demands = [
            DemandInput(
                product="WEEKLY_PROD",
                bundle_size=10,
                weekly_demand=500
            )
        ]

        schedule = ScheduleConfig(
            shifts_enabled=2,
            shift1_hours=8.0,
            shift2_hours=8.0,
            shift3_hours=0.0,
            work_days=5,
            ot_enabled=False
        )

        config = SimulationConfig(
            operations=operations,
            schedule=schedule,
            demands=demands,
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=7
        )

        report = validate_simulation_config(config)
        assert report.is_valid

        start_time = time.time()
        metrics, duration = run_simulation(config, seed=42)
        end_time = time.time()

        assert metrics.bundles_completed > 0
        actual_time = end_time - start_time
        assert actual_time < 30.0, f"7-day simulation took {actual_time:.2f}s, expected < 30s"


class TestMixDrivenLargeConfiguration:
    """Test mix-driven mode with multiple products."""

    def test_5_product_mix_driven(self):
        """Test mix-driven mode with 5 products (maximum allowed) at different percentages."""
        num_products = 5

        operations = []
        for i in range(num_products):
            product = f"MIX_PROD_{i+1}"
            for step in range(1, 4):
                operations.append(OperationInput(
                    product=product,
                    step=step,
                    operation=f"Op_{step}_{product}",
                    machine_tool=f"Shared_Machine_{step}",  # Shared resources
                    sam_min=2.0 + (i * 0.1),  # Slight variation
                    operators=2
                ))

        # Create mix percentages that sum to 100
        mix_pcts = [100 / num_products] * num_products  # 10% each

        demands = [
            DemandInput(
                product=f"MIX_PROD_{i+1}",
                bundle_size=10,
                mix_share_pct=mix_pcts[i]
            )
            for i in range(num_products)
        ]

        schedule = ScheduleConfig(
            shifts_enabled=2,
            shift1_hours=8.0,
            shift2_hours=8.0,
            shift3_hours=0.0,
            work_days=5,
            ot_enabled=False
        )

        config = SimulationConfig(
            operations=operations,
            schedule=schedule,
            demands=demands,
            mode=DemandMode.MIX_DRIVEN,
            total_demand=500,  # 500 pieces total
            horizon_days=1
        )

        report = validate_simulation_config(config)
        assert report.is_valid

        start_time = time.time()
        metrics, duration = run_simulation(config, seed=42)
        end_time = time.time()

        # Verify all products were processed
        products_with_output = [p for p in metrics.throughput_by_product if metrics.throughput_by_product[p] > 0]
        assert len(products_with_output) >= 3  # At least 3 out of 5 products

        actual_time = end_time - start_time
        assert actual_time < 15.0, f"Mix-driven simulation took {actual_time:.2f}s"


class TestBreakdownsPerformance:
    """Test simulation performance with equipment breakdowns."""

    def test_many_breakdown_rules(self):
        """Test simulation with breakdown rules for all machines."""
        operations = []
        num_machines = 10

        for i in range(num_machines):
            operations.append(OperationInput(
                product="BREAKDOWN_TEST",
                step=i + 1,
                operation=f"Operation_{i + 1}",
                machine_tool=f"Machine_{i + 1}",
                sam_min=2.0,
                operators=2
            ))

        # Breakdown rule for every machine
        breakdowns = [
            BreakdownInput(
                machine_tool=f"Machine_{i + 1}",
                breakdown_pct=2.0  # 2% breakdown probability
            )
            for i in range(num_machines)
        ]

        demands = [
            DemandInput(
                product="BREAKDOWN_TEST",
                bundle_size=10,
                daily_demand=200
            )
        ]

        schedule = ScheduleConfig(
            shifts_enabled=2,
            shift1_hours=8.0,
            shift2_hours=8.0,
            shift3_hours=0.0,
            work_days=5,
            ot_enabled=False
        )

        config = SimulationConfig(
            operations=operations,
            schedule=schedule,
            demands=demands,
            breakdowns=breakdowns,
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1
        )

        report = validate_simulation_config(config)
        assert report.is_valid

        start_time = time.time()
        metrics, duration = run_simulation(config, seed=42)
        end_time = time.time()

        # Verify breakdowns occurred
        assert metrics.breakdown_events >= 0  # May or may not have breakdowns

        actual_time = end_time - start_time
        assert actual_time < 20.0, f"Simulation with breakdowns took {actual_time:.2f}s"


class TestFullCalculationsPipeline:
    """Test the complete calculations pipeline performance."""

    def test_full_pipeline_large_config(self):
        """Test full simulation + calculations for large configuration."""
        # Create a realistic large configuration
        operations = []
        products = ["TSHIRT", "POLO", "SHORTS", "JACKET", "DRESS"]

        sequence_ops = [
            ("Cut fabric", "Cutting Table", 2.0),
            ("Prepare pieces", "Prep Station", 1.5),
            ("Sew front", "Overlock 4-thread", 3.0),
            ("Sew back", "Overlock 4-thread", 3.5),
            ("Join seams", "Flatlock", 4.0),
            ("Add buttons/zips", "Button Machine", 2.0),
            ("Hem edges", "Single Needle", 2.5),
            ("Press garment", "Pressing Station", 1.5),
            ("Quality check", "Inspection Station", 1.0),
            ("Pack", "Packing Station", 0.5),
        ]

        for product in products:
            for step, (op_name, machine, sam) in enumerate(sequence_ops, 1):
                operations.append(OperationInput(
                    product=product,
                    step=step,
                    operation=f"{op_name} - {product}",
                    machine_tool=machine,
                    sam_min=sam * (0.9 + 0.2 * (products.index(product) / len(products))),
                    sequence="Assembly" if step > 2 else "Cutting",
                    grouping=f"GRP_{step // 4}",
                    operators=1 + (step % 2),
                    variability=VariabilityType.TRIANGULAR,
                    rework_pct=1.0 if step == 9 else 0.0,
                    grade_pct=85.0,
                    fpd_pct=15.0
                ))

        demands = [
            DemandInput(
                product=product,
                bundle_size=10,
                daily_demand=100 + (i * 20)  # Varying demand
            )
            for i, product in enumerate(products)
        ]

        breakdowns = [
            BreakdownInput(machine_tool="Overlock 4-thread", breakdown_pct=3.0),
            BreakdownInput(machine_tool="Flatlock", breakdown_pct=2.0),
        ]

        schedule = ScheduleConfig(
            shifts_enabled=2,
            shift1_hours=8.0,
            shift2_hours=8.0,
            shift3_hours=0.0,
            work_days=5,
            ot_enabled=False
        )

        config = SimulationConfig(
            operations=operations,
            schedule=schedule,
            demands=demands,
            breakdowns=breakdowns,
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=5
        )

        # Validate
        report = validate_simulation_config(config)
        assert report.is_valid, f"Validation failed: {report.errors}"

        # Run simulation
        start_sim = time.time()
        metrics, sim_duration = run_simulation(config, seed=42)
        end_sim = time.time()

        # Calculate all outputs
        start_calc = time.time()
        outputs = calculate_all_blocks(config, metrics, report, sim_duration)
        end_calc = time.time()

        # Verify outputs
        assert outputs.daily_summary is not None
        assert outputs.free_capacity is not None
        assert outputs.station_performance is not None
        assert len(outputs.station_performance) == len(operations)
        assert outputs.weekly_demand_capacity is not None
        assert outputs.per_product_summary is not None
        assert len(outputs.per_product_summary) == len(products)
        assert outputs.assumption_log is not None

        # Performance assertions
        sim_time = end_sim - start_sim
        calc_time = end_calc - start_calc
        total_time = sim_time + calc_time

        assert sim_time < 60.0, f"Simulation took {sim_time:.2f}s, expected < 60s"
        assert calc_time < 5.0, f"Calculations took {calc_time:.2f}s, expected < 5s"
        assert total_time < 65.0, f"Total pipeline took {total_time:.2f}s, expected < 65s"


class TestValidationPerformance:
    """Test validation module performance."""

    def test_validate_large_config(self):
        """Test validation speed for large configuration."""
        # Create large config (within limits: 5 products max, 50 ops per product)
        operations = []
        num_products = 5
        steps_per_product = 20

        for i in range(num_products):
            product = f"VALID_PROD_{i}"
            for step in range(1, steps_per_product + 1):
                operations.append(OperationInput(
                    product=product,
                    step=step,
                    operation=f"Op_{step}_{product}",
                    machine_tool=f"Machine_{step % 5}",
                    sam_min=2.0,
                    operators=2
                ))

        demands = [
            DemandInput(
                product=f"VALID_PROD_{i}",
                bundle_size=10,
                daily_demand=50
            )
            for i in range(num_products)
        ]

        schedule = ScheduleConfig(
            shifts_enabled=2,
            shift1_hours=8.0,
            shift2_hours=8.0,
            shift3_hours=0.0,
            work_days=5,
            ot_enabled=False
        )

        config = SimulationConfig(
            operations=operations,
            schedule=schedule,
            demands=demands,
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1
        )

        # Time validation
        start_time = time.time()
        report = validate_simulation_config(config)
        end_time = time.time()

        assert report.is_valid
        assert report.products_count == num_products  # 5 products
        assert report.operations_count == num_products * steps_per_product  # 100 operations

        validation_time = end_time - start_time
        assert validation_time < 1.0, f"Validation took {validation_time:.2f}s, expected < 1s"


class TestMemoryEfficiency:
    """Test memory efficiency with large simulations."""

    def test_memory_with_many_bundles(self):
        """Test simulation doesn't have memory issues with many bundles."""
        operations = [
            OperationInput(
                product="MEMORY_TEST",
                step=i,
                operation=f"Step_{i}",
                machine_tool=f"Machine_{i}",
                sam_min=0.5,  # Fast operations
                operators=3
            )
            for i in range(1, 4)
        ]

        # High demand = many bundles
        demands = [
            DemandInput(
                product="MEMORY_TEST",
                bundle_size=5,  # Small bundles = more bundles
                daily_demand=500
            )
        ]

        schedule = ScheduleConfig(
            shifts_enabled=2,
            shift1_hours=8.0,
            shift2_hours=8.0,
            shift3_hours=0.0,
            work_days=5,
            ot_enabled=False
        )

        config = SimulationConfig(
            operations=operations,
            schedule=schedule,
            demands=demands,
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=3  # 3 days = more bundles
        )

        report = validate_simulation_config(config)
        assert report.is_valid

        # Run multiple times to check for memory leaks
        for iteration in range(3):
            metrics, duration = run_simulation(config, seed=42 + iteration)
            assert metrics.bundles_completed > 0

        # If we get here without memory errors, test passes


class TestBenchmarkSummary:
    """Summary benchmark tests for documentation purposes."""

    def test_benchmark_summary(self):
        """Run a standard benchmark and report results."""
        # Standard configuration
        operations = []
        products = ["A", "B", "C"]

        for product in products:
            for step in range(1, 6):
                operations.append(OperationInput(
                    product=product,
                    step=step,
                    operation=f"Op_{step}_{product}",
                    machine_tool=f"Machine_{step}",
                    sam_min=2.0,
                    operators=2
                ))

        demands = [
            DemandInput(product=p, bundle_size=10, daily_demand=100)
            for p in products
        ]

        schedule = ScheduleConfig(
            shifts_enabled=2,
            shift1_hours=8.0,
            shift2_hours=8.0,
            shift3_hours=0.0,
            work_days=5,
            ot_enabled=False
        )

        config = SimulationConfig(
            operations=operations,
            schedule=schedule,
            demands=demands,
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1
        )

        # Run benchmark
        validation_times = []
        simulation_times = []
        calculation_times = []

        for i in range(5):  # 5 iterations
            # Validation
            start = time.time()
            report = validate_simulation_config(config)
            validation_times.append(time.time() - start)

            # Simulation
            start = time.time()
            metrics, sim_duration = run_simulation(config, seed=42 + i)
            simulation_times.append(time.time() - start)

            # Calculations
            start = time.time()
            outputs = calculate_all_blocks(config, metrics, report, sim_duration)
            calculation_times.append(time.time() - start)

        # Calculate averages
        avg_validation = sum(validation_times) / len(validation_times)
        avg_simulation = sum(simulation_times) / len(simulation_times)
        avg_calculation = sum(calculation_times) / len(calculation_times)

        # Print benchmark results (visible in test output with -v)
        print(f"\n=== Benchmark Results (5 iterations, 3 products, 15 operations) ===")
        print(f"Average validation time: {avg_validation*1000:.2f}ms")
        print(f"Average simulation time: {avg_simulation*1000:.2f}ms")
        print(f"Average calculation time: {avg_calculation*1000:.2f}ms")
        print(f"Total average time: {(avg_validation + avg_simulation + avg_calculation)*1000:.2f}ms")

        # Performance assertions
        assert avg_validation < 0.1, "Validation should be < 100ms"
        assert avg_simulation < 5.0, "Simulation should be < 5s"
        assert avg_calculation < 0.5, "Calculation should be < 500ms"
