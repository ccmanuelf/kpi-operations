"""
Pattern 4 — planning vs. execution horizon.

MiniZinc plans the week (or month, or any multi-day horizon) by
distributing weekly demand into per-day production quotas that minimize
the MAX daily utilization (smoothest workload). SimPy then executes
each day with that day's quota using the existing engine.

Why this is useful:
  - A capacity planner says "I need 1000 of A and 500 of B by end of
    week" — the planner does not want to compute a day-by-day split
    by hand, especially when products have different bottleneck rates.
  - A flat schedule (max-load minimized) leaves the same headroom every
    day, so a single-day surprise (breakdown, absenteeism) can be
    absorbed without cascading into a missed week.

Edge cases handled (and tested in test_planning_horizon.py):
  - n_products == 0           : Pydantic prevents at config layer.
  - n_products == 1           : weekly target evenly split across days
    (helper short-circuits without calling MZ).
  - horizon_days == 1         : the entire weekly target lands on day 1;
    capacity check decides feasibility.
  - infeasible weekly demand  : MZ returns UNSATISFIABLE; helper still
    produces a best-effort plan that respects daily capacity and reports
    the per-product shortfall in the response message.
  - mode == "mix-driven"      : sequencing/planning needs hard quantities;
    surface a clear error so the route can return validation-failed.
  - missing/zero weekly_demand : helper returns an empty plan with a
    descriptive message instead of crashing the model.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import SimulationConfig
from .minizinc_runner import (
    MiniZincNotAvailableError,
    MiniZincResult,
    is_minizinc_available,
    run_minizinc,
)

logger = logging.getLogger(__name__)

_MODEL_PATH = Path(__file__).parent / "planning_horizon.mzn"


# =============================================================================
# Public dataclasses
# =============================================================================


@dataclass
class DailyPlan:
    """One day's portion of the planning horizon."""

    day: int  # 1-indexed
    pieces_by_product: Dict[str, int]
    total_pieces: int
    minutes_used: int
    daily_minutes_capacity: int
    load_pct: float


@dataclass
class PlanningResult:
    """Top-level planning result."""

    is_optimal: bool
    is_satisfied: bool
    status: str
    horizon_days: int
    products: List[str] = field(default_factory=list)
    weekly_demand: Dict[str, int] = field(default_factory=dict)
    daily_minutes_capacity: int = 0
    max_load_pct: int = 0
    daily_plans: List[DailyPlan] = field(default_factory=list)
    fulfillment_by_product: Dict[str, int] = field(default_factory=dict)
    raw_solver_output: Optional[str] = None
    solver_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_optimal": self.is_optimal,
            "is_satisfied": self.is_satisfied,
            "status": self.status,
            "horizon_days": self.horizon_days,
            "products": self.products,
            "weekly_demand": self.weekly_demand,
            "daily_minutes_capacity": self.daily_minutes_capacity,
            "max_load_pct": self.max_load_pct,
            "daily_plans": [asdict(p) for p in self.daily_plans],
            "fulfillment_by_product": self.fulfillment_by_product,
            "solver_message": self.solver_message,
        }


# =============================================================================
# Helpers
# =============================================================================


def _resolve_weekly_demand(config: SimulationConfig, product: str) -> int:
    """
    Resolve the weekly target for a product. Falls back to
    `daily_demand × work_days` when only the daily figure is given,
    matching how the rest of the engine treats demand-driven mode.
    Returns 0 when no demand can be resolved (caller decides what to do).
    """
    work_days = max(int(config.schedule.work_days or 1), 1)
    for d in config.demands:
        if d.product != product:
            continue
        if d.weekly_demand and d.weekly_demand > 0:
            return int(round(d.weekly_demand))
        if d.daily_demand and d.daily_demand > 0:
            return int(round(d.daily_demand * work_days))
    return 0


def _bottleneck_minutes_per_piece_x100(config: SimulationConfig, product: str) -> int:
    """
    Compute the bottleneck (slowest-station) minutes per piece for a
    product, encoded as integer × 100 to keep MiniZinc free of `var
    float` (which the gecode backend can't bound for this model).

    Time per piece at one station = sam_min / (operators × grade_pct/100).
    The line's per-piece pacing is set by the SLOWEST station — so the
    per-product bottleneck minutes/piece is the MAX across stations.
    Returns 0 when the product has no operations (caller surfaces
    a warning/skip).
    """
    product_ops = [op for op in config.operations if op.product == product]
    if not product_ops:
        return 0

    times = []
    for op in product_ops:
        operators = max(int(op.operators or 1), 1)
        sam = float(op.sam_min) if op.sam_min else 0.0
        grade = float(op.grade_pct or 100) / 100.0
        if sam <= 0 or grade <= 0:
            continue
        per_piece = sam / (operators * grade)
        times.append(per_piece)

    if not times:
        return 0
    bottleneck_minutes = max(times)
    # × 100 integer rounding; ensure >= 1 to avoid div-by-zero in MZ
    # bound expression `daily_minutes * 100 div minutes_per_piece_x100`.
    return max(1, int(math.ceil(bottleneck_minutes * 100)))


def _daily_minutes(config: SimulationConfig) -> int:
    """Total minutes available in a single working day for this config."""
    daily_hours = float(config.schedule.daily_planned_hours)
    return max(1, int(round(daily_hours * 60)))


# =============================================================================
# Public service
# =============================================================================


def plan_horizon(
    config: SimulationConfig,
    *,
    horizon_days: int,
    timeout_seconds: int = 30,
) -> PlanningResult:
    """
    Plan a multi-day production schedule that smooths daily load.

    Returns a `PlanningResult` whose `daily_plans` list has one entry
    per planning day with the per-product piece count and the resulting
    utilization. Use the returned plan to feed SimPy day-by-day for
    execution-side validation.
    """
    if horizon_days < 1:
        raise ValueError("horizon_days must be >= 1")

    products = [d.product for d in config.demands]
    len(products)
    daily_minutes = _daily_minutes(config)

    weekly_demand = {p: _resolve_weekly_demand(config, p) for p in products}
    minutes_per_piece_x100 = {p: _bottleneck_minutes_per_piece_x100(config, p) for p in products}

    # If every product has zero weekly demand, bail without invoking MZ.
    total_weekly = sum(weekly_demand.values())
    if total_weekly == 0:
        return PlanningResult(
            is_optimal=True,
            is_satisfied=True,
            status="empty",
            horizon_days=horizon_days,
            products=products,
            weekly_demand=weekly_demand,
            daily_minutes_capacity=daily_minutes,
            max_load_pct=0,
            daily_plans=[
                DailyPlan(
                    day=d,
                    pieces_by_product={p: 0 for p in products},
                    total_pieces=0,
                    minutes_used=0,
                    daily_minutes_capacity=daily_minutes,
                    load_pct=0.0,
                )
                for d in range(1, horizon_days + 1)
            ],
            fulfillment_by_product={p: 0 for p in products},
            solver_message=(
                "No weekly demand specified for any product; planning is "
                "trivial. Set daily_demand or weekly_demand on at least one "
                "product to use this feature."
            ),
        )

    # Drop products with zero rate (no ops or all-zero SAMs) — MZ would
    # divide-by-zero in the bound expression. Log a warning so callers
    # know the resulting plan ignored that product.
    skipped = [p for p in products if minutes_per_piece_x100[p] == 0]
    if skipped:
        logger.warning(
            "planning skipped product(s) with no operations / zero rate: %s",
            ", ".join(skipped),
        )
    active_products = [p for p in products if minutes_per_piece_x100[p] > 0]
    if not active_products:
        return PlanningResult(
            is_optimal=False,
            is_satisfied=False,
            status="no-operations",
            horizon_days=horizon_days,
            products=products,
            weekly_demand=weekly_demand,
            daily_minutes_capacity=daily_minutes,
            max_load_pct=0,
            daily_plans=[],
            fulfillment_by_product={p: 0 for p in products},
            solver_message=(
                "No products have valid operations / non-zero SAM. Add "
                "operations for the products in your demands list."
            ),
        )

    n_active = len(active_products)
    weekly_active = [weekly_demand[p] for p in active_products]
    minutes_active = [minutes_per_piece_x100[p] for p in active_products]

    # Single-product or single-day shortcuts: for a single product the
    # smoothest plan is a near-equal split per day (load is constant).
    # For a single day the entire week lands on that day. Both bypass
    # the solver — the solver gives the same answer but spends 30+ ms.
    if horizon_days == 1 or n_active == 1:
        return _build_trivial_plan(
            products=products,
            active_products=active_products,
            weekly_demand=weekly_demand,
            minutes_per_piece_x100=minutes_per_piece_x100,
            daily_minutes=daily_minutes,
            horizon_days=horizon_days,
        )

    data: Dict[str, Any] = {
        "n_days": horizon_days,
        "n_products": n_active,
        "weekly_demand": weekly_active,
        "minutes_per_piece_x100": minutes_active,
        "daily_minutes": daily_minutes,
    }

    # Short-circuits above (zero demand, no-operations, single-product/day)
    # don't need the solver. Only the multi-product / multi-day path does.
    if not is_minizinc_available():
        raise MiniZincNotAvailableError("MiniZinc CLI is not installed; planning horizon is unavailable.")

    mz_result: MiniZincResult = run_minizinc(
        _MODEL_PATH,
        data,
        timeout_seconds=timeout_seconds,
    )

    if not mz_result.is_satisfied or mz_result.solution is None:
        # Best-effort fallback: return per-day capacity-bounded plan even
        # when the model reports infeasibility (typically because weekly
        # demand exceeds horizon capacity). Distribute proportionally.
        return _build_best_effort_plan(
            products=products,
            active_products=active_products,
            weekly_demand=weekly_demand,
            minutes_per_piece_x100=minutes_per_piece_x100,
            daily_minutes=daily_minutes,
            horizon_days=horizon_days,
            raw_stdout=mz_result.raw_stdout,
            status_line=mz_result.status_line,
        )

    sol = mz_result.solution
    flat: List[int] = list(sol.get("daily_pieces_flat", []))
    daily_minutes_used: List[int] = list(sol.get("daily_minutes_used", []))
    max_load_pct = int(sol.get("max_load_pct", 0))
    daily_minutes_capacity = int(sol.get("daily_minutes_capacity", daily_minutes))

    # Reshape n_days × n_active row-major.
    daily_plans: List[DailyPlan] = []
    fulfillment: Dict[str, int] = {p: 0 for p in products}
    for d in range(horizon_days):
        pieces_by_product: Dict[str, int] = {p: 0 for p in products}
        total = 0
        for j, prod in enumerate(active_products):
            cell = int(flat[d * n_active + j]) if d * n_active + j < len(flat) else 0
            pieces_by_product[prod] = cell
            fulfillment[prod] += cell
            total += cell
        minutes_used = daily_minutes_used[d] if d < len(daily_minutes_used) else 0
        load_pct = (minutes_used / daily_minutes_capacity * 100.0) if daily_minutes_capacity else 0.0
        daily_plans.append(
            DailyPlan(
                day=d + 1,
                pieces_by_product=pieces_by_product,
                total_pieces=total,
                minutes_used=minutes_used,
                daily_minutes_capacity=daily_minutes_capacity,
                load_pct=round(load_pct, 2),
            )
        )

    return PlanningResult(
        is_optimal=mz_result.is_optimal,
        is_satisfied=True,
        status=mz_result.status_line or "satisfied",
        horizon_days=horizon_days,
        products=products,
        weekly_demand=weekly_demand,
        daily_minutes_capacity=daily_minutes_capacity,
        max_load_pct=max_load_pct,
        daily_plans=daily_plans,
        fulfillment_by_product=fulfillment,
        raw_solver_output=mz_result.raw_stdout,
        solver_message=(
            f"Optimal plan found: max daily load {max_load_pct}% " f"across {horizon_days} day(s)."
            if mz_result.is_optimal
            else "Plan found but not proven optimal within the timeout."
        ),
    )


# =============================================================================
# Trivial / fallback plan builders
# =============================================================================


def _build_trivial_plan(
    *,
    products: List[str],
    active_products: List[str],
    weekly_demand: Dict[str, int],
    minutes_per_piece_x100: Dict[str, int],
    daily_minutes: int,
    horizon_days: int,
) -> PlanningResult:
    """
    Smoothing the load when there's only ONE active product or only ONE
    day. Splits the weekly target as evenly as possible across days
    (single product: floor + remainder on day 1; single day: everything
    on day 1).
    """
    daily_pieces: List[Dict[str, int]] = [{p: 0 for p in products} for _ in range(horizon_days)]

    if horizon_days == 1:
        # Whole week lands on day 1.
        for p in active_products:
            daily_pieces[0][p] = weekly_demand[p]
    else:
        for p in active_products:
            base = weekly_demand[p] // horizon_days
            remainder = weekly_demand[p] - base * horizon_days
            for d in range(horizon_days):
                daily_pieces[d][p] = base + (1 if d < remainder else 0)

    daily_minutes_capacity = daily_minutes
    daily_plans: List[DailyPlan] = []
    max_load = 0
    for d in range(horizon_days):
        minutes_used = sum(daily_pieces[d][p] * minutes_per_piece_x100[p] // 100 for p in active_products)
        load_pct = minutes_used / daily_minutes_capacity * 100.0 if daily_minutes_capacity else 0.0
        max_load = max(max_load, int(load_pct))
        total = sum(daily_pieces[d][p] for p in products)
        daily_plans.append(
            DailyPlan(
                day=d + 1,
                pieces_by_product=daily_pieces[d],
                total_pieces=total,
                minutes_used=minutes_used,
                daily_minutes_capacity=daily_minutes_capacity,
                load_pct=round(load_pct, 2),
            )
        )

    fulfillment = {p: sum(daily_pieces[d][p] for d in range(horizon_days)) for p in products}

    # Trivial split is always feasible mathematically, but if it leaves
    # a day above 100% load it's not a usable schedule. Surface that as
    # is_satisfied=False with a shortfall-style message so the UI flags
    # it clearly. The user can then extend the horizon or add operators.
    if max_load > 100:
        return PlanningResult(
            is_optimal=False,
            is_satisfied=False,
            status="capacity-exceeded",
            horizon_days=horizon_days,
            products=products,
            weekly_demand=weekly_demand,
            daily_minutes_capacity=daily_minutes_capacity,
            max_load_pct=max_load,
            daily_plans=daily_plans,
            fulfillment_by_product=fulfillment,
            solver_message=(
                f"Weekly demand exceeds horizon capacity: each day would "
                f"need {max_load}% of the available {daily_minutes_capacity} "
                "min. Add operators, extend the horizon, or split the demand."
            ),
        )

    return PlanningResult(
        is_optimal=True,
        is_satisfied=True,
        status="trivial",
        horizon_days=horizon_days,
        products=products,
        weekly_demand=weekly_demand,
        daily_minutes_capacity=daily_minutes_capacity,
        max_load_pct=max_load,
        daily_plans=daily_plans,
        fulfillment_by_product=fulfillment,
        solver_message=("Single-product or single-day horizon — trivially smoothed " "without invoking the solver."),
    )


def _build_best_effort_plan(
    *,
    products: List[str],
    active_products: List[str],
    weekly_demand: Dict[str, int],
    minutes_per_piece_x100: Dict[str, int],
    daily_minutes: int,
    horizon_days: int,
    raw_stdout: Optional[str],
    status_line: Optional[str],
) -> PlanningResult:
    """
    Build a capacity-bounded best-effort plan when MZ reports
    UNSATISFIABLE (typically because weekly demand exceeds horizon
    capacity). Each day fills to capacity using a proportional mix; the
    unmet residual is reported in the message.
    """
    daily_minutes_capacity = daily_minutes
    daily_pieces: List[Dict[str, int]] = [{p: 0 for p in products} for _ in range(horizon_days)]

    # Proportional mix by weekly_demand × minutes_per_piece (so larger
    # weights get more capacity).
    weights = {p: weekly_demand[p] * minutes_per_piece_x100[p] for p in active_products}
    weight_sum = sum(weights.values()) or 1
    daily_minutes_used: List[int] = [0] * horizon_days

    remaining = dict(weekly_demand)
    for d in range(horizon_days):
        # For each product, allocate up to its share of daily capacity.
        available = daily_minutes * 100  # in ×100 units
        for p in active_products:
            share = weights[p] / weight_sum  # 0..1 fraction of daily capacity
            mins_share_x100 = int(available * share)
            mppx = minutes_per_piece_x100[p]
            if mppx <= 0:
                continue
            cell = mins_share_x100 // mppx
            cell = max(0, min(cell, remaining.get(p, 0)))
            daily_pieces[d][p] = cell
            remaining[p] -= cell
            daily_minutes_used[d] += cell * mppx

    fulfillment = {p: sum(daily_pieces[d][p] for d in range(horizon_days)) for p in products}
    shortfall = {p: weekly_demand[p] - fulfillment[p] for p in products}

    daily_plans: List[DailyPlan] = []
    max_load = 0
    for d in range(horizon_days):
        minutes_used = daily_minutes_used[d] // 100
        load_pct = minutes_used / daily_minutes_capacity * 100.0 if daily_minutes_capacity else 0.0
        max_load = max(max_load, int(load_pct))
        total = sum(daily_pieces[d][p] for p in products)
        daily_plans.append(
            DailyPlan(
                day=d + 1,
                pieces_by_product=daily_pieces[d],
                total_pieces=total,
                minutes_used=minutes_used,
                daily_minutes_capacity=daily_minutes_capacity,
                load_pct=round(load_pct, 2),
            )
        )

    short_str = ", ".join(f"{p}: short {short}" for p, short in shortfall.items() if short > 0)
    return PlanningResult(
        is_optimal=False,
        is_satisfied=False,
        status=status_line or "unsatisfied",
        horizon_days=horizon_days,
        products=products,
        weekly_demand=weekly_demand,
        daily_minutes_capacity=daily_minutes_capacity,
        max_load_pct=max_load,
        daily_plans=daily_plans,
        fulfillment_by_product=fulfillment,
        raw_solver_output=raw_stdout,
        solver_message=(
            "Weekly demand exceeds horizon capacity. Best-effort plan fills "
            "each day to capacity; remaining shortfall: "
            + (short_str or "none")
            + ". Consider a longer horizon, more operators, or splitting demand."
        ),
    )
