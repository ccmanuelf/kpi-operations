"""
Pattern 2 — bottleneck rebalancing.

Take an existing operator allocation (typically one where SimPy Block 7
already flagged a bottleneck) and reshuffle operators across stations
to lift the bottleneck without (by default) growing the total head-
count. The model maximizes the minimum slack (predicted - demand)
across all stations, so the new bottleneck — if any — is the highest
the rebalancing can push it.

Edge cases handled here (and tested in test_bottleneck_rebalancing.py):
  - Empty operations: prevented by Pydantic on the request shape; the
    helper still tolerates n_ops==0 gracefully and short-circuits.
  - Single op: rebalancing is impossible (delta=0 always). Returned
    with an explanatory message — no MZ call is made.
  - Already balanced: model still solves but `delta == [0,0,...]`
    and `min_slack` reflects the existing surplus.
  - Infeasible delta budget: when `total_delta_max=0` and the demand
    can't be met by any reshuffle, the model returns an
    is_satisfied=true result with negative `min_slack` — the surface
    layer can convert that into a "best-effort, demand still short"
    warning.
  - Operator floor violation (would drop below `min_operators_per_op`):
    constraint blocks moves that would set any station to 0.
  - Operator ceiling violation: same on the upper bound.
  - Demand resolution is shared with Pattern 1 via `_resolve_daily_demand`.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..models import OperationInput, SimulationConfig
from .minizinc_runner import (
    MiniZincNotAvailableError,
    MiniZincResult,
    MiniZincSolveError,
    is_minizinc_available,
    run_minizinc,
)
from .operator_allocation import _resolve_daily_demand

logger = logging.getLogger(__name__)

_MODEL_PATH = Path(__file__).parent / "bottleneck_rebalancing.mzn"


# =============================================================================
# Result dataclasses
# =============================================================================


@dataclass
class RebalancingProposal:
    """One station's delta + after-rebalance prediction."""

    product: str
    step: int
    operation: str
    machine_tool: str
    sam_min: float
    grade_pct: float
    operators_before: int
    operators_after: int
    delta: int
    demand_pcs_per_day: int
    predicted_pcs_per_day: int
    slack_pcs: int


@dataclass
class RebalancingResult:
    """Top-level rebalancing result."""

    is_optimal: bool
    is_satisfied: bool
    status: str
    total_operators_before: int
    total_operators_after: int
    total_delta: int
    min_slack_pcs: int
    proposals: List[RebalancingProposal] = field(default_factory=list)
    raw_solver_output: Optional[str] = None
    solver_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_optimal": self.is_optimal,
            "is_satisfied": self.is_satisfied,
            "status": self.status,
            "total_operators_before": self.total_operators_before,
            "total_operators_after": self.total_operators_after,
            "total_delta": self.total_delta,
            "min_slack_pcs": self.min_slack_pcs,
            "proposals": [asdict(p) for p in self.proposals],
            "solver_message": self.solver_message,
        }


# =============================================================================
# Data marshalling
# =============================================================================


def _build_minizinc_data(
    config: SimulationConfig,
    *,
    min_operators_per_op: int,
    max_operators_per_op: int,
    total_delta_max: int,
    total_delta_min: int,
) -> Tuple[Dict[str, Any], List[OperationInput]]:
    """Project the SimulationConfig onto the rebalancing model's input vector."""
    operations = list(config.operations)
    n_ops = len(operations)

    # SAM in cents-style integer (× 100). Round for safety; SAM is
    # typically 2-decimal precision in the source data.
    sam_min_x100 = [int(round(float(op.sam_min) * 100)) for op in operations]
    grade_pct = [int(round(op.grade_pct or 100)) for op in operations]
    demand_pcs_per_day = [_resolve_daily_demand(config, op.product) for op in operations]
    current_operators = [int(op.operators or 1) for op in operations]

    daily_planned_minutes = int(round(config.schedule.daily_planned_hours * 60))

    data = {
        "n_ops": n_ops,
        "sam_min_x100": sam_min_x100,
        "grade_pct": grade_pct,
        "demand_pcs_per_day": demand_pcs_per_day,
        "current_operators": current_operators,
        "daily_planned_minutes": daily_planned_minutes,
        "min_operators_per_op": int(min_operators_per_op),
        "max_operators_per_op": int(max_operators_per_op),
        "total_delta_max": int(total_delta_max),
        "total_delta_min": int(total_delta_min),
    }
    return data, operations


# =============================================================================
# Public service
# =============================================================================


def rebalance_bottleneck(
    config: SimulationConfig,
    *,
    min_operators_per_op: int = 1,
    max_operators_per_op: int = 10,
    total_delta_max: int = 0,
    total_delta_min: int = -50,
    timeout_seconds: int = 30,
) -> RebalancingResult:
    """
    Run the rebalancing MZ model and return a RebalancingResult.

    `total_delta_max=0` (default) means strict swap — net head-count is
    preserved. Set `total_delta_max=N` to allow up to N additional
    operators (turning the rebalance into a "rebalance-and-grow"). The
    `total_delta_min` lower-bound prevents the solver from removing more
    than that many operators from the line.

    Edge-case behavior:
      - n_ops == 0 → returns satisfied with empty proposals (no MZ call).
      - n_ops == 1 → returns satisfied with delta=[0] (no MZ call;
        rebalancing across one station is meaningless).
      - Infeasible (any constraint can't be met under the bounds) →
        the model emits =====UNSATISFIABLE=====; we surface a clear
        message.
      - Demand can't be met even with optimal reshuffle → the model
        returns is_satisfied=True with negative min_slack; the route
        layer presents that as a "best-effort, station X still short
        by Y pcs/day" warning.
    """
    if not is_minizinc_available():
        raise MiniZincNotAvailableError(
            "MiniZinc CLI is not installed; bottleneck rebalancing is unavailable."
        )

    data, operations = _build_minizinc_data(
        config,
        min_operators_per_op=min_operators_per_op,
        max_operators_per_op=max_operators_per_op,
        total_delta_max=total_delta_max,
        total_delta_min=total_delta_min,
    )

    n_ops = data["n_ops"]
    current_total = sum(data["current_operators"])

    if n_ops == 0:
        # Pydantic should prevent this, but the helper handles it.
        return RebalancingResult(
            is_optimal=True,
            is_satisfied=True,
            status="empty",
            total_operators_before=0,
            total_operators_after=0,
            total_delta=0,
            min_slack_pcs=0,
            proposals=[],
            solver_message="No operations in configuration; nothing to rebalance.",
        )

    if n_ops == 1:
        # Single-station line: rebalancing is undefined.
        op = operations[0]
        demand = data["demand_pcs_per_day"][0]
        cur = data["current_operators"][0]
        # Predict the existing throughput for transparency.
        predicted = (
            cur * data["daily_planned_minutes"] * data["grade_pct"][0]
        ) // data["sam_min_x100"][0]
        return RebalancingResult(
            is_optimal=True,
            is_satisfied=True,
            status="single-op",
            total_operators_before=cur,
            total_operators_after=cur,
            total_delta=0,
            min_slack_pcs=int(predicted - demand),
            proposals=[
                RebalancingProposal(
                    product=op.product,
                    step=int(op.step),
                    operation=op.operation,
                    machine_tool=op.machine_tool,
                    sam_min=float(op.sam_min),
                    grade_pct=float(op.grade_pct or 100),
                    operators_before=cur,
                    operators_after=cur,
                    delta=0,
                    demand_pcs_per_day=int(demand),
                    predicted_pcs_per_day=int(predicted),
                    slack_pcs=int(predicted - demand),
                ),
            ],
            solver_message=(
                "Single-operation line — rebalancing is not applicable. "
                f"Existing throughput {predicted} pcs/day vs demand {demand}."
            ),
        )

    mz_result: MiniZincResult = run_minizinc(
        _MODEL_PATH,
        data,
        timeout_seconds=timeout_seconds,
    )

    if not mz_result.is_satisfied or mz_result.solution is None:
        return RebalancingResult(
            is_optimal=False,
            is_satisfied=False,
            status=mz_result.status_line or "unsatisfied",
            total_operators_before=current_total,
            total_operators_after=current_total,
            total_delta=0,
            min_slack_pcs=0,
            proposals=[],
            raw_solver_output=mz_result.raw_stdout,
            solver_message=(
                "Rebalancing infeasible under the given bounds. Try widening "
                "max_operators_per_op or relaxing total_delta_min/max."
            ),
        )

    sol = mz_result.solution
    deltas = sol.get("delta", [0] * n_ops)
    operators_after = sol.get("operators_after", data["current_operators"])
    predicted = sol.get("predicted_pcs_per_day_per_op", [0] * n_ops)
    slacks = sol.get("slack_pcs", [0] * n_ops)
    min_slack = int(sol.get("min_slack", 0))
    total_delta = int(sol.get("total_delta", 0))

    proposals = [
        RebalancingProposal(
            product=op.product,
            step=int(op.step),
            operation=op.operation,
            machine_tool=op.machine_tool,
            sam_min=float(op.sam_min),
            grade_pct=float(op.grade_pct or 100),
            operators_before=int(data["current_operators"][i]),
            operators_after=int(operators_after[i]),
            delta=int(deltas[i]),
            demand_pcs_per_day=int(data["demand_pcs_per_day"][i]),
            predicted_pcs_per_day=int(predicted[i]),
            slack_pcs=int(slacks[i]),
        )
        for i, op in enumerate(operations)
    ]

    new_total = sum(p.operators_after for p in proposals)

    if min_slack >= 0:
        message = (
            f"Rebalanced {sum(1 for p in proposals if p.delta != 0)} stations; "
            f"new bottleneck has {min_slack} pcs/day surplus over demand."
        )
    else:
        worst = min(proposals, key=lambda p: p.slack_pcs)
        message = (
            f"Best-effort allocation found, but {worst.operation} "
            f"still falls short by {-worst.slack_pcs} pcs/day. Consider "
            "raising total_delta_max or max_operators_per_op."
        )

    return RebalancingResult(
        is_optimal=mz_result.is_optimal,
        is_satisfied=True,
        status=mz_result.status_line or "satisfied",
        total_operators_before=current_total,
        total_operators_after=new_total,
        total_delta=total_delta,
        min_slack_pcs=min_slack,
        proposals=proposals,
        solver_message=message,
    )


# =============================================================================
# Apply rebalancing back to a config
# =============================================================================


def apply_rebalancing_to_config(
    config: SimulationConfig, result: RebalancingResult
) -> SimulationConfig:
    """
    Return a copy of `config` whose operations carry the proposed
    operator counts. Used by the route to drive a SimPy validation
    run with the rebalanced allocation. Preserves `config` when the
    proposals can't be aligned (length mismatch or unsatisfied result).
    """
    if not result.is_satisfied or len(result.proposals) != len(config.operations):
        return config

    new_config = deepcopy(config)
    for op, prop in zip(new_config.operations, result.proposals):
        op.operators = prop.operators_after
    return new_config
