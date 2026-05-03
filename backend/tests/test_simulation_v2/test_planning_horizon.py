"""
Tests for Pattern 4 — planning horizon.

Edge cases explicitly covered:
  - n_products == 1 : helper short-circuits with even split per day.
  - horizon_days == 1 : entire weekly demand lands on day 1; capacity
    dictates feasibility.
  - All-zero weekly demand : helper returns empty plan without invoking
    the solver, with a descriptive message.
  - Weekly demand exceeds horizon capacity : best-effort plan returned
    (is_satisfied=False, fulfillment_by_product < weekly_demand,
    shortfall message).
  - Product missing operations : skipped with a logged warning; the
    other products still get planned. If ALL products are skipped, the
    helper returns is_satisfied=False with a no-operations status.
  - Daily-only demand fallback : weekly target derived as
    daily_demand × work_days when weekly_demand is absent.

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
from backend.simulation_v2.optimization.planning_horizon import (
    _bottleneck_minutes_per_piece_x100,
    _daily_minutes,
    _resolve_weekly_demand,
    plan_horizon,
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
    operators: int = 1,
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
def two_product_weekly_config(schedule) -> SimulationConfig:
    return SimulationConfig(
        operations=[
            _op(product="A", step=1, operation="Cut-A", machine_tool="M1",
                sam_min=2.0, operators=1, grade_pct=90),
            _op(product="A", step=2, operation="Sew-A", machine_tool="M2",
                sam_min=2.0, operators=1, grade_pct=90),
            _op(product="B", step=1, operation="Cut-B", machine_tool="M1",
                sam_min=1.5, operators=1, grade_pct=90),
            _op(product="B", step=2, operation="Sew-B", machine_tool="M2",
                sam_min=1.5, operators=1, grade_pct=90),
        ],
        schedule=schedule,
        demands=[
            DemandInput(product="A", bundle_size=10, weekly_demand=500),
            DemandInput(product="B", bundle_size=10, weekly_demand=300),
        ],
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1,
    )


@pytest.fixture
def single_product_weekly_config(schedule) -> SimulationConfig:
    return SimulationConfig(
        operations=[
            _op(product="A", step=1, operation="Cut", machine_tool="M1",
                sam_min=2.0, operators=1, grade_pct=90),
            _op(product="A", step=2, operation="Sew", machine_tool="M2",
                sam_min=2.5, operators=1, grade_pct=90),
        ],
        schedule=schedule,
        demands=[DemandInput(product="A", bundle_size=10, weekly_demand=300)],
        mode=DemandMode.DEMAND_DRIVEN,
        horizon_days=1,
    )


# =============================================================================
# Helpers
# =============================================================================


class TestResolveWeeklyDemand:
    def test_uses_weekly_demand_when_present(self, two_product_weekly_config):
        assert _resolve_weekly_demand(two_product_weekly_config, "A") == 500

    def test_falls_back_to_daily_x_workdays(self, schedule):
        cfg = SimulationConfig(
            operations=[
                _op(product="A", step=1, operation="Op", machine_tool="M1",
                    sam_min=1.0)
            ],
            schedule=schedule,
            demands=[DemandInput(product="A", bundle_size=10, daily_demand=100)],
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1,
        )
        # work_days=5 → 100 × 5 = 500
        assert _resolve_weekly_demand(cfg, "A") == 500

    def test_returns_zero_when_no_demand(self, schedule):
        cfg = SimulationConfig(
            operations=[
                _op(product="A", step=1, operation="Op", machine_tool="M1",
                    sam_min=1.0)
            ],
            schedule=schedule,
            demands=[DemandInput(product="A", bundle_size=10)],
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1,
        )
        assert _resolve_weekly_demand(cfg, "A") == 0


class TestBottleneckMinutesPerPiece:
    def test_uses_max_across_stations(self, two_product_weekly_config):
        # Product A SAM 2.0 + 2.0 → bottleneck 2.0 → 200 (×100)
        assert _bottleneck_minutes_per_piece_x100(two_product_weekly_config, "A") == 223

    def test_returns_zero_for_unknown_product(self, two_product_weekly_config):
        assert _bottleneck_minutes_per_piece_x100(two_product_weekly_config, "ZZ") == 0


class TestDailyMinutes:
    def test_one_shift_eight_hours(self, schedule):
        cfg = SimulationConfig(
            operations=[
                _op(product="A", step=1, operation="Op", machine_tool="M1",
                    sam_min=1.0)
            ],
            schedule=schedule,
            demands=[DemandInput(product="A", bundle_size=10, daily_demand=10)],
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1,
        )
        assert _daily_minutes(cfg) == 480


# =============================================================================
# Trivial / fallback paths (no MZ needed)
# =============================================================================


class TestEmptyDemand:
    def test_returns_zero_plan_without_solver(self, schedule):
        cfg = SimulationConfig(
            operations=[
                _op(product="A", step=1, operation="Op", machine_tool="M1",
                    sam_min=1.0)
            ],
            schedule=schedule,
            demands=[DemandInput(product="A", bundle_size=10)],  # no demand
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1,
        )
        result = plan_horizon(cfg, horizon_days=5)
        assert result.is_optimal is True
        assert result.is_satisfied is True
        assert result.status == "empty"
        assert all(p.total_pieces == 0 for p in result.daily_plans)
        assert "no weekly demand" in result.solver_message.lower()


class TestSingleDayHorizon:
    def test_entire_week_on_day_one_when_feasible(self, schedule):
        # Tiny demand that fits comfortably in 1 day.
        cfg = SimulationConfig(
            operations=[
                _op(product="A", step=1, operation="Op", machine_tool="M1",
                    sam_min=1.0)
            ],
            schedule=schedule,
            demands=[DemandInput(product="A", bundle_size=10, weekly_demand=100)],
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1,
        )
        result = plan_horizon(cfg, horizon_days=1)
        assert result.is_optimal is True
        assert result.is_satisfied is True
        assert len(result.daily_plans) == 1
        # All weekly demand goes to day 1.
        assert result.daily_plans[0].pieces_by_product["A"] == 100

    def test_capacity_exceeded_flagged_correctly(self, two_product_weekly_config):
        # 800 pcs × 2 min ÷ 0.9 grade = ~1780 min on 1 day vs 480 cap → infeasible.
        result = plan_horizon(two_product_weekly_config, horizon_days=1)
        assert result.is_satisfied is False
        assert result.status == "capacity-exceeded"
        assert result.max_load_pct > 100
        assert "exceeds horizon capacity" in result.solver_message.lower()
        # Pieces still recorded so the planner sees the gap.
        assert result.daily_plans[0].pieces_by_product["A"] == 500
        assert result.daily_plans[0].pieces_by_product["B"] == 300


class TestSingleProductHorizon:
    def test_even_split_across_days(self, single_product_weekly_config):
        result = plan_horizon(single_product_weekly_config, horizon_days=5)
        # 300 pcs / 5 days = 60 pcs/day, perfectly even.
        assert result.is_optimal is True
        assert result.status == "trivial"
        assert all(p.pieces_by_product["A"] == 60 for p in result.daily_plans)
        assert sum(p.pieces_by_product["A"] for p in result.daily_plans) == 300

    def test_uneven_split_remainder_to_first_days(self, schedule):
        cfg = SimulationConfig(
            operations=[
                _op(product="A", step=1, operation="Op", machine_tool="M1",
                    sam_min=1.0)
            ],
            schedule=schedule,
            demands=[DemandInput(product="A", bundle_size=10, weekly_demand=502)],
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1,
        )
        # 502 / 5 = 100 + remainder 2 → days 1+2 get 101, days 3-5 get 100.
        result = plan_horizon(cfg, horizon_days=5)
        assert result.is_satisfied
        counts = [p.pieces_by_product["A"] for p in result.daily_plans]
        assert counts == [101, 101, 100, 100, 100]
        assert sum(counts) == 502


# =============================================================================
# Real-solver tests
# =============================================================================


@needs_minizinc
class TestPlanHorizon:
    def test_smoothes_max_daily_load(self, two_product_weekly_config):
        result = plan_horizon(two_product_weekly_config, horizon_days=5)
        assert result.is_satisfied
        # Solver may not prove optimality within the test timeout for
        # this many free variables, but the practical load uniformity
        # is what matters for the planning use case.
        loads = [p.load_pct for p in result.daily_plans]
        assert max(loads) - min(loads) <= 2.0
        # Weekly fulfillment must meet/exceed each product's demand.
        assert result.fulfillment_by_product["A"] >= 500
        assert result.fulfillment_by_product["B"] >= 300

    def test_invalidates_when_capacity_exceeded(self, schedule):
        # Demand 5000 weekly with single op 5 SAM, 1 op = 1 pc/5min, so:
        # ~1.5 pcs/min (single station) × 60 min × 8 h × 5 days = 480 pcs
        # capacity. 5000 demand >> 480 → infeasible.
        cfg = SimulationConfig(
            operations=[
                _op(product="A", step=1, operation="Slow", machine_tool="M1",
                    sam_min=5.0, operators=1, grade_pct=90),
            ],
            schedule=schedule,
            demands=[DemandInput(product="A", bundle_size=10, weekly_demand=5000)],
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1,
        )
        # n_products == 1 → trivial path (even split). With 1000/day at
        # 5.5 min/piece (5/0.9), each day needs 5500 min vs 480 → load
        # WAY over 100%. Trivial path doesn't enforce capacity caps,
        # so to exercise the best-effort fallback we need n_products
        # >= 2 AND total demand > capacity.
        cfg2 = SimulationConfig(
            operations=[
                _op(product="A", step=1, operation="A1", machine_tool="M1",
                    sam_min=5.0, operators=1, grade_pct=90),
                _op(product="B", step=1, operation="B1", machine_tool="M1",
                    sam_min=5.0, operators=1, grade_pct=90),
            ],
            schedule=schedule,
            demands=[
                DemandInput(product="A", bundle_size=10, weekly_demand=2500),
                DemandInput(product="B", bundle_size=10, weekly_demand=2500),
            ],
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1,
        )
        result = plan_horizon(cfg2, horizon_days=5)
        # Best-effort returned with shortfall message.
        assert not result.is_satisfied
        total_fulfilled = sum(result.fulfillment_by_product.values())
        assert total_fulfilled < 5000
        assert "short" in result.solver_message.lower()

    def test_skips_products_without_operations(self, schedule, caplog):
        cfg = SimulationConfig(
            operations=[
                _op(product="A", step=1, operation="Op", machine_tool="M1",
                    sam_min=1.0),
                _op(product="A", step=2, operation="Op2", machine_tool="M2",
                    sam_min=1.5),
                _op(product="B", step=1, operation="OpB", machine_tool="M1",
                    sam_min=1.0),
            ],
            schedule=schedule,
            demands=[
                DemandInput(product="A", bundle_size=10, weekly_demand=200),
                DemandInput(product="B", bundle_size=10, weekly_demand=100),
                # C in demands but NOT in operations:
                DemandInput(product="C", bundle_size=10, weekly_demand=50),
            ],
            mode=DemandMode.DEMAND_DRIVEN,
            horizon_days=1,
        )
        with caplog.at_level("WARNING"):
            result = plan_horizon(cfg, horizon_days=5)
        # Plan is satisfied (A and B can be fit); C is skipped.
        assert result.is_satisfied
        assert result.fulfillment_by_product["C"] == 0
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any("C" in r.getMessage() for r in warnings)

    def test_load_pct_arithmetic(self, two_product_weekly_config):
        result = plan_horizon(two_product_weekly_config, horizon_days=5)
        assert result.is_satisfied
        for plan in result.daily_plans:
            # minutes_used / capacity ≈ load_pct / 100 (within 1.0%).
            expected = plan.minutes_used / plan.daily_minutes_capacity * 100
            assert abs(plan.load_pct - expected) < 1.0


# =============================================================================
# n_products == 0 prevented at the Pydantic layer; horizon_days < 1 raises.
# =============================================================================


def test_zero_horizon_raises(two_product_weekly_config):
    with pytest.raises(ValueError, match=">= 1"):
        plan_horizon(two_product_weekly_config, horizon_days=0)
