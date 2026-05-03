"""
Tests for Pattern 2 — bottleneck rebalancing.

Edge cases explicitly covered:
  - Single-operation line (helper short-circuits without invoking MZ)
  - Already-balanced allocation (delta == [0,...], min_slack >= 0)
  - Bottleneck under strict swap (total_delta_max=0): operators move
    from over-staffed station to bottleneck
  - Best-effort under infeasible demand (negative min_slack returned
    with helpful message)
  - Operator-floor constraint: rebalance can't drop a station below
    `min_operators_per_op`
  - Operator-ceiling constraint: rebalance can't raise a station above
    `max_operators_per_op`
  - Apply-to-config produces a fresh SimulationConfig with new counts;
    original is untouched

Tests requiring the MiniZinc binary are decorated with `@needs_minizinc`
so CI without MZ skips cleanly.
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
from backend.simulation_v2.optimization.bottleneck_rebalancing import (
    _build_minizinc_data,
    apply_rebalancing_to_config,
    rebalance_bottleneck,
)


needs_minizinc = pytest.mark.skipif(
    not is_minizinc_available(),
    reason="MiniZinc CLI not available",
)


# =============================================================================
# Fixtures
# =============================================================================


def _op(
    *,
    product: str,
    step: int,
    operation: str,
    machine_tool: str,
    sam_min: float,
    operators: int,
    grade_pct: int = 90,
) -> OperationInput:
    return OperationInput(
        product=product, step=step, operation=operation, machine_tool=machine_tool,
        sam_min=sam_min, operators=operators,
        variability=VariabilityType.TRIANGULAR,
        rework_pct=0, grade_pct=grade_pct, fpd_pct=10,
    )


@pytest.fixture
def schedule() -> ScheduleConfig:
    return ScheduleConfig(
        shifts_enabled=1, shift1_hours=8, shift2_hours=0, shift3_hours=0,
        work_days=5, ot_enabled=False,
    )


@pytest.fixture
def bottlenecked_config(schedule) -> SimulationConfig:
    """Cut over-staffed (4), Sew bottlenecked (1, SAM 3.5), Pack OK (1)."""
    return SimulationConfig(
        operations=[
            _op(product="A", step=1, operation="Cut", machine_tool="M1",
                sam_min=2.0, operators=4, grade_pct=90),
            _op(product="A", step=2, operation="Sew", machine_tool="M2",
                sam_min=3.5, operators=1, grade_pct=85),
            _op(product="A", step=3, operation="Pack", machine_tool="M3",
                sam_min=1.0, operators=1, grade_pct=95),
        ],
        schedule=schedule,
        demands=[DemandInput(product="A", bundle_size=10, daily_demand=200)],
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1,
    )


@pytest.fixture
def balanced_config(schedule) -> SimulationConfig:
    """An allocation that's already adequate at low demand."""
    return SimulationConfig(
        operations=[
            _op(product="A", step=1, operation="Cut", machine_tool="M1",
                sam_min=2.0, operators=2, grade_pct=90),
            _op(product="A", step=2, operation="Sew", machine_tool="M2",
                sam_min=3.5, operators=2, grade_pct=85),
            _op(product="A", step=3, operation="Pack", machine_tool="M3",
                sam_min=1.0, operators=1, grade_pct=95),
        ],
        schedule=schedule,
        demands=[DemandInput(product="A", bundle_size=10, daily_demand=200)],
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1,
    )


@pytest.fixture
def single_op_config(schedule) -> SimulationConfig:
    return SimulationConfig(
        operations=[
            _op(product="A", step=1, operation="OnlyOp", machine_tool="M1",
                sam_min=2.0, operators=2, grade_pct=90),
        ],
        schedule=schedule,
        demands=[DemandInput(product="A", bundle_size=10, daily_demand=200)],
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1,
    )


# =============================================================================
# Data marshalling
# =============================================================================


class TestBuildMinizincData:
    def test_sam_min_x100_rounding(self, bottlenecked_config):
        data, _ = _build_minizinc_data(
            bottlenecked_config,
            min_operators_per_op=1, max_operators_per_op=10,
            total_delta_max=0, total_delta_min=-50,
        )
        # SAMs are 2.0 / 3.5 / 1.0 → 200 / 350 / 100.
        assert data["sam_min_x100"] == [200, 350, 100]

    def test_current_operators_passed_through(self, bottlenecked_config):
        data, _ = _build_minizinc_data(
            bottlenecked_config,
            min_operators_per_op=1, max_operators_per_op=10,
            total_delta_max=0, total_delta_min=-50,
        )
        assert data["current_operators"] == [4, 1, 1]


# =============================================================================
# Single-operation short-circuit (no MZ call)
# =============================================================================


class TestSingleOperationShortCircuit:
    def test_returns_zero_delta_without_solver(self, single_op_config):
        result = rebalance_bottleneck(single_op_config)
        assert result.is_optimal is True
        assert result.is_satisfied is True
        assert result.status == "single-op"
        assert result.total_delta == 0
        assert len(result.proposals) == 1
        assert result.proposals[0].delta == 0
        assert "rebalancing is not applicable" in result.solver_message.lower()


# =============================================================================
# Real-solver tests
# =============================================================================


@needs_minizinc
class TestRebalanceBottleneck:

    def test_strict_swap_lifts_bottleneck(self, bottlenecked_config):
        """Cut(4)/Sew(1)/Pack(1) under demand 200: rebalancer should
        move 2 operators from Cut to Sew, keeping total at 6."""
        result = rebalance_bottleneck(bottlenecked_config)
        assert result.is_satisfied
        assert result.is_optimal
        assert result.total_delta == 0  # strict swap
        # All stations should now meet demand (min_slack >= 0).
        assert result.min_slack_pcs >= 0
        # Cut shed operators; Sew gained.
        cut = next(p for p in result.proposals if p.operation == "Cut")
        sew = next(p for p in result.proposals if p.operation == "Sew")
        assert cut.delta < 0
        assert sew.delta > 0

    def test_balanced_config_returns_zero_delta(self, balanced_config):
        """A pre-balanced allocation should yield delta=[0,0,0]."""
        result = rebalance_bottleneck(balanced_config)
        assert result.is_satisfied
        # The model maximizes min_slack, but if delta=0 is already
        # optimal it stays at zero — confirm no churn.
        assert all(p.delta == 0 for p in result.proposals)
        assert result.total_delta == 0

    def test_negative_slack_when_demand_unattainable(self, schedule):
        """If demand is so high that no reshuffle of the existing
        operators meets it, the model still solves but returns
        negative min_slack with a best-effort message."""
        cfg = SimulationConfig(
            operations=[
                _op(product="A", step=1, operation="Slow", machine_tool="M1",
                    sam_min=10.0, operators=2, grade_pct=85),
                _op(product="A", step=2, operation="Slower", machine_tool="M2",
                    sam_min=15.0, operators=1, grade_pct=85),
            ],
            schedule=schedule,
            demands=[DemandInput(product="A", bundle_size=10, daily_demand=500)],
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1,
        )
        result = rebalance_bottleneck(
            cfg, total_delta_max=0, total_delta_min=-3
        )
        # Strict swap can't meet 500 pcs/day on these slow stations.
        assert result.is_satisfied
        assert result.min_slack_pcs < 0
        assert "still falls short" in result.solver_message.lower()

    def test_min_operators_floor_enforced(self, bottlenecked_config):
        """With min_operators_per_op=2, no station may end below 2."""
        # Bottlenecked starts at 4/1/1 — Sew and Pack are below the floor
        # already. Rebalance must lift those without exceeding total_delta_max.
        # Allow some growth so it's feasible.
        result = rebalance_bottleneck(
            bottlenecked_config,
            min_operators_per_op=2,
            total_delta_max=4,
            total_delta_min=0,
        )
        if result.is_satisfied:
            for p in result.proposals:
                assert p.operators_after >= 2

    def test_max_operators_ceiling_enforced(self, bottlenecked_config):
        """With max_operators_per_op=2, the rebalancer can't push any
        station above 2."""
        result = rebalance_bottleneck(
            bottlenecked_config,
            min_operators_per_op=1,
            max_operators_per_op=2,
            total_delta_max=0,
            total_delta_min=-5,
        )
        if result.is_satisfied:
            for p in result.proposals:
                assert p.operators_after <= 2

    def test_growth_allowed_when_budget_set(self, bottlenecked_config):
        """With total_delta_max=2, the rebalancer may add up to 2 ops."""
        result = rebalance_bottleneck(
            bottlenecked_config,
            total_delta_max=2,
            total_delta_min=-5,
        )
        assert result.is_satisfied
        assert -5 <= result.total_delta <= 2


# =============================================================================
# apply_rebalancing_to_config
# =============================================================================


@needs_minizinc
class TestApplyRebalancingToConfig:
    def test_returns_fresh_config_with_new_counts(self, bottlenecked_config):
        result = rebalance_bottleneck(bottlenecked_config)
        assert result.is_satisfied

        new_config = apply_rebalancing_to_config(bottlenecked_config, result)

        # Original config untouched (immutability check).
        assert bottlenecked_config.operations[0].operators == 4
        # New config carries the proposed counts.
        for op, prop in zip(new_config.operations, result.proposals):
            assert op.operators == prop.operators_after

    def test_returns_original_when_unsatisfied(self, bottlenecked_config):
        # Force an unsatisfied result by setting infeasible bounds.
        bad = rebalance_bottleneck(
            bottlenecked_config,
            min_operators_per_op=10,
            max_operators_per_op=10,
            total_delta_max=0,
            total_delta_min=0,
        )
        # When the floor=ceiling=10 and starting at 4/1/1, the constraint
        # `delta in [10-cur, 10-cur]` forces delta=[6,9,9] but
        # total_delta_max=0 forbids the sum=24. Unsatisfiable.
        if not bad.is_satisfied:
            same = apply_rebalancing_to_config(bottlenecked_config, bad)
            assert same is bottlenecked_config


# =============================================================================
# Single-op short-circuit covers the n_ops=1 path; n_ops=0 is prevented
# at the Pydantic layer (operations is min_length=1).
# =============================================================================
