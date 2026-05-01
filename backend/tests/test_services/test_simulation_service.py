"""Smoke tests for SimulationService re-exports + DB-bound class.

The service is a thin delegation layer over backend.calculations.simulation
and .production_line_simulation. These tests verify the surface is intact
(routes won't fail to import) and that the class wires `db` through.
"""

from unittest.mock import MagicMock

from backend.services import simulation_service as svc


class TestModuleSurface:
    """Guard against accidentally dropping a re-export."""

    def test_pure_functions_reexported(self):
        for name in (
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
        ):
            assert callable(getattr(svc, name)), f"{name} not exported"

    def test_dataclasses_reexported(self):
        for name in (
            "CapacityRequirement",
            "FloatingPoolOptimization",
            "ShiftCoverageSimulation",
            "SimulationResult",
            "ProductionLineConfig",
            "WorkStation",
            "WorkStationType",
        ):
            assert getattr(svc, name) is not None, f"{name} not exported"


class TestSimulationServiceClass:
    def test_init_stores_db(self):
        db = MagicMock()
        service = svc.SimulationService(db)
        assert service.db is db

    def test_db_bound_methods_exist(self):
        service = svc.SimulationService(MagicMock())
        assert callable(service.calculate_capacity_requirements)
        assert callable(service.optimize_floating_pool_allocation)
        assert callable(service.run_capacity_simulation)
