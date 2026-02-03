"""
Test fixtures for Production Line Simulation v2.0

Provides reusable fixtures for testing the simulation module.
"""

import pytest
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


@pytest.fixture
def simple_schedule() -> ScheduleConfig:
    """A simple single-shift schedule."""
    return ScheduleConfig(
        shifts_enabled=1,
        shift1_hours=8.0,
        shift2_hours=0.0,
        shift3_hours=0.0,
        work_days=5,
        ot_enabled=False
    )


@pytest.fixture
def two_shift_schedule() -> ScheduleConfig:
    """A two-shift schedule."""
    return ScheduleConfig(
        shifts_enabled=2,
        shift1_hours=8.0,
        shift2_hours=8.0,
        shift3_hours=0.0,
        work_days=5,
        ot_enabled=False
    )


@pytest.fixture
def simple_operations() -> List[OperationInput]:
    """A simple 3-step operation sequence for one product."""
    return [
        OperationInput(
            product="PRODUCT_A",
            step=1,
            operation="Cut fabric",
            machine_tool="Cutting Table",
            sam_min=2.0,
            sequence="Cutting",
            grouping="PREP",
            operators=2,
            variability=VariabilityType.TRIANGULAR,
            rework_pct=0.0,
            grade_pct=85.0,
            fpd_pct=15.0
        ),
        OperationInput(
            product="PRODUCT_A",
            step=2,
            operation="Sew seams",
            machine_tool="Overlock 4-thread",
            sam_min=3.5,
            sequence="Assembly",
            grouping="SEW",
            operators=3,
            variability=VariabilityType.TRIANGULAR,
            rework_pct=2.0,
            grade_pct=90.0,
            fpd_pct=15.0
        ),
        OperationInput(
            product="PRODUCT_A",
            step=3,
            operation="Final inspection",
            machine_tool="Inspection Station",
            sam_min=1.0,
            sequence="Finishing",
            grouping="QC",
            operators=1,
            variability=VariabilityType.DETERMINISTIC,
            rework_pct=0.0,
            grade_pct=100.0,
            fpd_pct=10.0
        ),
    ]


@pytest.fixture
def multi_product_operations() -> List[OperationInput]:
    """Operations for two products with shared resources."""
    return [
        # Product A
        OperationInput(
            product="PRODUCT_A",
            step=1,
            operation="Cut fabric A",
            machine_tool="Cutting Table",
            sam_min=2.0,
            operators=2
        ),
        OperationInput(
            product="PRODUCT_A",
            step=2,
            operation="Sew A",
            machine_tool="Overlock 4-thread",
            sam_min=4.0,
            operators=2
        ),
        # Product B
        OperationInput(
            product="PRODUCT_B",
            step=1,
            operation="Cut fabric B",
            machine_tool="Cutting Table",  # Shared with A
            sam_min=2.5,
            operators=2
        ),
        OperationInput(
            product="PRODUCT_B",
            step=2,
            operation="Sew B",
            machine_tool="Flatlock",  # Different machine
            sam_min=3.0,
            operators=2
        ),
    ]


@pytest.fixture
def simple_demand() -> List[DemandInput]:
    """Simple demand for one product."""
    return [
        DemandInput(
            product="PRODUCT_A",
            bundle_size=10,
            daily_demand=200,
            weekly_demand=1000
        )
    ]


@pytest.fixture
def multi_product_demand() -> List[DemandInput]:
    """Demand for two products."""
    return [
        DemandInput(
            product="PRODUCT_A",
            bundle_size=10,
            daily_demand=150
        ),
        DemandInput(
            product="PRODUCT_B",
            bundle_size=5,
            daily_demand=100
        ),
    ]


@pytest.fixture
def mix_driven_demand() -> List[DemandInput]:
    """Demand using mix percentages."""
    return [
        DemandInput(
            product="PRODUCT_A",
            bundle_size=10,
            mix_share_pct=60.0
        ),
        DemandInput(
            product="PRODUCT_B",
            bundle_size=5,
            mix_share_pct=40.0
        ),
    ]


@pytest.fixture
def sample_breakdowns() -> List[BreakdownInput]:
    """Sample breakdown configuration."""
    return [
        BreakdownInput(machine_tool="Overlock 4-thread", breakdown_pct=5.0),
        BreakdownInput(machine_tool="Cutting Table", breakdown_pct=2.0),
    ]


@pytest.fixture
def simple_config(
    simple_operations: List[OperationInput],
    simple_schedule: ScheduleConfig,
    simple_demand: List[DemandInput]
) -> SimulationConfig:
    """Complete simple simulation configuration."""
    return SimulationConfig(
        operations=simple_operations,
        schedule=simple_schedule,
        demands=simple_demand,
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1
    )


@pytest.fixture
def multi_product_config(
    multi_product_operations: List[OperationInput],
    two_shift_schedule: ScheduleConfig,
    multi_product_demand: List[DemandInput]
) -> SimulationConfig:
    """Configuration with multiple products."""
    return SimulationConfig(
        operations=multi_product_operations,
        schedule=two_shift_schedule,
        demands=multi_product_demand,
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1
    )


@pytest.fixture
def mix_driven_config(
    multi_product_operations: List[OperationInput],
    simple_schedule: ScheduleConfig,
    mix_driven_demand: List[DemandInput]
) -> SimulationConfig:
    """Configuration using mix-driven mode."""
    return SimulationConfig(
        operations=multi_product_operations,
        schedule=simple_schedule,
        demands=mix_driven_demand,
        mode=DemandMode.MIX_DRIVEN,
        total_demand=500,
        horizon_days=1
    )


@pytest.fixture
def config_with_breakdowns(
    simple_operations: List[OperationInput],
    simple_schedule: ScheduleConfig,
    simple_demand: List[DemandInput],
    sample_breakdowns: List[BreakdownInput]
) -> SimulationConfig:
    """Configuration with equipment breakdowns."""
    return SimulationConfig(
        operations=simple_operations,
        schedule=simple_schedule,
        demands=simple_demand,
        breakdowns=sample_breakdowns,
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1
    )
