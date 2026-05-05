"""
Service-layer entry point for simulation calculations.

Phase 1 (dual-view architecture): this module is the single import surface for
simulation logic. Routes must import from here, not directly from
`backend.calculations.simulation` or `backend.calculations.production_line_simulation`
— that satisfies the spec's "no metric calculation in route handlers" rule.

What this module provides:
  - Pure simulation functions are re-exported (they don't need a DB session,
    so wrapping them in a class would be ceremony for no reason).
  - DB-bound helpers (capacity requirements, floating-pool optimization,
    capacity simulation) live on `SimulationService`, which takes a Session
    in its constructor for parity with the other capacity services.

Phase 3 (assumption registry): `SimulationService` will accept a `mode` arg on
each method and inject site_adjusted assumptions (absenteeism_rate,
target_efficiency, ideal_cycle_time_source, etc.) from the registry before
delegating. The pure re-exports remain untouched.
"""

from typing import Any

from sqlalchemy.orm import Session

from backend.calculations.production_line_simulation import (
    ProductionLineConfig,
    WorkStation,
    WorkStationType,
    analyze_bottlenecks,
    compare_scenarios,
    create_default_production_line,
    run_production_simulation,
    simulate_floating_pool_impact,
)
from backend.calculations.simulation import (
    CapacityRequirement,
    FloatingPoolOptimization,
    ShiftCoverageSimulation,
    SimulationResult,
    calculate_production_capacity,
    run_efficiency_simulation,
    run_staffing_simulation,
    simulate_multi_shift_coverage,
    simulate_shift_coverage,
)
from backend.calculations.simulation import (
    calculate_capacity_requirements as _calculate_capacity_requirements_db,
)
from backend.calculations.simulation import (
    optimize_floating_pool_allocation as _optimize_floating_pool_allocation_db,
)
from backend.calculations.simulation import (
    run_capacity_simulation as _run_capacity_simulation_db,
)


__all__ = [
    "SimulationService",
    # Pure (no-DB) calculation functions
    "calculate_production_capacity",
    "run_efficiency_simulation",
    "run_staffing_simulation",
    "simulate_shift_coverage",
    "simulate_multi_shift_coverage",
    "run_production_simulation",
    "compare_scenarios",
    "analyze_bottlenecks",
    "simulate_floating_pool_impact",
    "create_default_production_line",
    # Result dataclasses
    "CapacityRequirement",
    "FloatingPoolOptimization",
    "ShiftCoverageSimulation",
    "SimulationResult",
    "ProductionLineConfig",
    "WorkStation",
    "WorkStationType",
]


class SimulationService:
    """DB-bound simulation operations. Pure helpers are module-level above."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def calculate_capacity_requirements(self, *args: Any, **kwargs: Any) -> CapacityRequirement:
        return _calculate_capacity_requirements_db(self.db, *args, **kwargs)

    def optimize_floating_pool_allocation(self, *args: Any, **kwargs: Any) -> FloatingPoolOptimization:
        return _optimize_floating_pool_allocation_db(self.db, *args, **kwargs)

    def run_capacity_simulation(self, *args: Any, **kwargs: Any) -> dict:
        return _run_capacity_simulation_db(self.db, *args, **kwargs)
