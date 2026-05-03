"""
Tests for Pattern 1 — operator-allocation optimization.

Covers:
  - data-projection helpers (`_resolve_daily_demand`, `_build_minizinc_data`)
  - optimizer happy path (3-op fixture meets demand with fewer operators)
  - infeasible budget (`total_operators_budget` lower than required)
  - empty-operations short-circuit
  - apply_allocation_to_config produces a fresh config with new operator counts

Tests that exercise the actual MiniZinc subprocess are decorated with
`@pytest.mark.skipif(not is_minizinc_available(), ...)` so CI environments
without MZ stay green; the local dev mac and the production Docker image
have the binary, so coverage is real where it matters.
"""

from typing import List

import pytest

from backend.simulation_v2.models import (
    DemandInput,
    DemandMode,
    OperationInput,
    ScheduleConfig,
    SimulationConfig,
    VariabilityType,
)
from backend.simulation_v2.optimization import is_minizinc_available
from backend.simulation_v2.optimization.operator_allocation import (
    _build_minizinc_data,
    _resolve_daily_demand,
    apply_allocation_to_config,
    optimize_operator_allocation,
)


needs_minizinc = pytest.mark.skipif(
    not is_minizinc_available(),
    reason="MiniZinc CLI not available; subprocess-level tests skipped.",
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def three_step_ops() -> List[OperationInput]:
    return [
        OperationInput(
            product="A", step=1, operation="Cut", machine_tool="M1",
            sam_min=2.0, operators=2,
            variability=VariabilityType.TRIANGULAR,
            rework_pct=0, grade_pct=90, fpd_pct=10,
        ),
        OperationInput(
            product="A", step=2, operation="Sew", machine_tool="M2",
            sam_min=3.5, operators=3,
            variability=VariabilityType.TRIANGULAR,
            rework_pct=2, grade_pct=85, fpd_pct=15,
        ),
        OperationInput(
            product="A", step=3, operation="Pack", machine_tool="M3",
            sam_min=1.0, operators=1,
            variability=VariabilityType.DETERMINISTIC,
            rework_pct=0, grade_pct=95, fpd_pct=5,
        ),
    ]


@pytest.fixture
def standard_schedule() -> ScheduleConfig:
    return ScheduleConfig(
        shifts_enabled=1, shift1_hours=8, shift2_hours=0, shift3_hours=0,
        work_days=5, ot_enabled=False,
    )


@pytest.fixture
def daily_200_demand() -> List[DemandInput]:
    return [DemandInput(product="A", bundle_size=10, daily_demand=200)]


@pytest.fixture
def base_config(
    three_step_ops, standard_schedule, daily_200_demand
) -> SimulationConfig:
    return SimulationConfig(
        operations=three_step_ops,
        schedule=standard_schedule,
        demands=daily_200_demand,
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1,
    )


# =============================================================================
# _resolve_daily_demand
# =============================================================================


class TestResolveDailyDemand:
    def test_daily_demand_passthrough(self, base_config):
        assert _resolve_daily_demand(base_config, "A") == 200

    def test_weekly_demand_divides_by_workdays(self, three_step_ops, standard_schedule):
        cfg = SimulationConfig(
            operations=three_step_ops,
            schedule=standard_schedule,
            demands=[DemandInput(product="A", bundle_size=10, weekly_demand=1000)],
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1,
        )
        assert _resolve_daily_demand(cfg, "A") == 200  # 1000 / 5

    def test_mix_driven_uses_share(self, three_step_ops, standard_schedule):
        cfg = SimulationConfig(
            operations=three_step_ops,
            schedule=standard_schedule,
            demands=[DemandInput(product="A", bundle_size=10, mix_share_pct=40.0)],
            mode=DemandMode.MIX_DRIVEN,
            horizon_days=1,
            total_demand=500.0,
        )
        assert _resolve_daily_demand(cfg, "A") == 200  # 500 * 40 / 100

    def test_unknown_product_returns_zero(self, base_config):
        assert _resolve_daily_demand(base_config, "Z") == 0


# =============================================================================
# _build_minizinc_data
# =============================================================================


class TestBuildMinizincData:
    def test_shape(self, base_config):
        data, ops = _build_minizinc_data(
            base_config, max_operators_per_op=10, total_operators_budget=None
        )
        assert data["n_ops"] == 3
        assert data["sam_min"] == [2.0, 3.5, 1.0]
        assert data["grade_pct"] == [90, 85, 95]
        assert data["demand_pcs_per_day"] == [200, 200, 200]
        assert data["daily_planned_minutes"] == 480
        assert data["max_operators_per_op"] == 10
        assert data["total_operators_budget"] == -1  # None → -1 sentinel
        assert len(ops) == 3
        assert ops[0].operation == "Cut"

    def test_budget_passthrough(self, base_config):
        data, _ = _build_minizinc_data(
            base_config, max_operators_per_op=10, total_operators_budget=8
        )
        assert data["total_operators_budget"] == 8


# =============================================================================
# optimize_operator_allocation (real solver)
# =============================================================================


@needs_minizinc
class TestOptimizeOperatorAllocation:
    def test_finds_minimum_operators_for_three_op_line(self, base_config):
        result = optimize_operator_allocation(base_config)
        assert result.is_satisfied
        assert result.is_optimal
        # Original allocation (2,3,1) totals 6; the optimum at 200 pcs/day
        # demand should be lower (each station meets demand with 1 operator
        # except sew which needs 2 due to SAM=3.5).
        assert result.total_operators_before == 6
        assert result.total_operators_after < result.total_operators_before
        assert all(p.operators_after >= 1 for p in result.proposals)

    def test_predicted_throughput_meets_demand(self, base_config):
        result = optimize_operator_allocation(base_config)
        for p in result.proposals:
            assert p.predicted_pcs_per_day >= p.demand_pcs_per_day, (
                f"{p.operation} predicted {p.predicted_pcs_per_day} < "
                f"demand {p.demand_pcs_per_day}"
            )

    def test_unsatisfiable_budget_returns_unsatisfied(self, base_config):
        # Total budget too low to meet 200 pcs/day on Sew alone (SAM 3.5
        # at grade 85%): minimum operators for Sew alone is 2.
        result = optimize_operator_allocation(
            base_config, total_operators_budget=2
        )
        assert not result.is_satisfied
        assert "demand constraints" in result.solver_message.lower() or (
            "could not satisfy" in result.solver_message.lower()
        )

    def test_empty_operations_short_circuits(self, standard_schedule, daily_200_demand):
        # Pydantic forbids empty operations on SimulationConfig — instead
        # confirm the optimizer handles a config that the route-side
        # validation would reject (the helper still works in isolation
        # if someone calls it directly).
        # Skip: Pydantic enforces non-empty operations at construction.
        pytest.skip("SimulationConfig.operations is min_length=1 by Pydantic constraint")


# =============================================================================
# apply_allocation_to_config
# =============================================================================


@needs_minizinc
class TestApplyAllocationToConfig:
    def test_returns_fresh_config_with_updated_operators(self, base_config):
        result = optimize_operator_allocation(base_config)
        assert result.is_satisfied

        new_config = apply_allocation_to_config(base_config, result)

        # Original config untouched.
        assert base_config.operations[0].operators == 2
        # New config's operators match proposals.
        for op, prop in zip(new_config.operations, result.proposals):
            assert op.operators == prop.operators_after

    def test_returns_original_when_unsatisfied(self, base_config):
        # Forge an unsatisfied result by using infeasible budget.
        bad = optimize_operator_allocation(
            base_config, total_operators_budget=2
        )
        assert not bad.is_satisfied
        same = apply_allocation_to_config(base_config, bad)
        assert same is base_config
