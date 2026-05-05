"""
Pattern 1 — operator allocation optimization.

Given a SimulationConfig, build the MiniZinc data dict, run
`operator_allocation.mzn`, parse the result, and (optionally) hand the
optimized allocation to SimPy for stochastic validation via the existing
Monte Carlo wrapper.

The MiniZinc model finds the minimum operator count per station such
that each station's deterministic capacity meets its share of demand.
SimPy then runs N replications under the stochastic engine to confirm
the deterministic prediction holds within reasonable CI bounds.
"""

from __future__ import annotations

import logging
import math
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..models import (
    DemandInput,
    DemandMode,
    OperationInput,
    SimulationConfig,
    SimulationResults,
)
from .minizinc_runner import (
    MiniZincNotAvailableError,
    MiniZincResult,
    MiniZincSolveError,
    is_minizinc_available,
    run_minizinc,
)

logger = logging.getLogger(__name__)

_MODEL_PATH = Path(__file__).parent / "operator_allocation.mzn"


# =============================================================================
# Public dataclasses (the route layer wraps these in Pydantic models)
# =============================================================================


@dataclass
class OperatorAllocationProposal:
    """One station's optimized operator count + the model's prediction."""

    product: str
    step: int
    operation: str
    machine_tool: str
    sam_min: float
    grade_pct: float
    operators_before: int
    operators_after: int
    demand_pcs_per_day: int
    predicted_pcs_per_day: float


@dataclass
class OperatorAllocationResult:
    """Top-level optimization result."""

    is_optimal: bool
    is_satisfied: bool
    status: str
    total_operators_before: int
    total_operators_after: int
    proposals: List[OperatorAllocationProposal] = field(default_factory=list)
    raw_solver_output: Optional[str] = None
    solver_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_optimal": self.is_optimal,
            "is_satisfied": self.is_satisfied,
            "status": self.status,
            "total_operators_before": self.total_operators_before,
            "total_operators_after": self.total_operators_after,
            "proposals": [asdict(p) for p in self.proposals],
            "solver_message": self.solver_message,
        }


# =============================================================================
# Demand fan-out helper
# =============================================================================


def _resolve_daily_demand(config: SimulationConfig, product: str) -> int:
    """
    Translate a product's demand specification into a per-day integer.

    Each demand entry may carry:
      - daily_demand directly,
      - weekly_demand (divided by config.schedule.work_days),
      - mix_share_pct + config.total_demand (mix-driven mode).
    Returns 0 if no demand resolves for this product.
    """
    demand = next(
        (d for d in config.demands if d.product == product),
        None,
    )
    if demand is None:
        return 0
    work_days = max(config.schedule.work_days, 1)
    if demand.daily_demand is not None:
        return int(round(demand.daily_demand))
    if demand.weekly_demand is not None:
        return int(round(demand.weekly_demand / work_days))
    if config.mode == DemandMode.MIX_DRIVEN and config.total_demand is not None and demand.mix_share_pct is not None:
        # total_demand is per day in mix-driven mode by project convention.
        return int(round(config.total_demand * demand.mix_share_pct / 100.0))
    return 0


def _build_minizinc_data(
    config: SimulationConfig,
    *,
    max_operators_per_op: int,
    total_operators_budget: Optional[int],
) -> Tuple[Dict[str, Any], List[OperationInput]]:
    """
    Project a SimulationConfig onto the .mzn model's input vector.

    Returns the data dict + the matching operations list (in the same
    order as the .mzn arrays) so the caller can pair the optimizer's
    output with each station for the proposal list.
    """
    operations = list(config.operations)
    n_ops = len(operations)

    sam_min = [float(op.sam_min) for op in operations]
    grade_pct = [int(round(op.grade_pct or 100)) for op in operations]
    demand_pcs_per_day = [_resolve_daily_demand(config, op.product) for op in operations]

    daily_planned_minutes = int(round(config.schedule.daily_planned_hours * 60))

    data = {
        "n_ops": n_ops,
        "sam_min": sam_min,
        "grade_pct": grade_pct,
        "demand_pcs_per_day": demand_pcs_per_day,
        "daily_planned_minutes": daily_planned_minutes,
        "max_operators_per_op": max_operators_per_op,
        "total_operators_budget": (total_operators_budget if total_operators_budget is not None else -1),
    }
    return data, operations


# =============================================================================
# Public service
# =============================================================================


def optimize_operator_allocation(
    config: SimulationConfig,
    *,
    max_operators_per_op: int = 10,
    total_operators_budget: Optional[int] = None,
    timeout_seconds: int = 30,
) -> OperatorAllocationResult:
    """
    Run the MiniZinc model and return an OperatorAllocationResult.

    Raises `MiniZincNotAvailableError` when the binary is missing
    (caller decides how to surface this — typically a 503 with a
    helpful detail). Validation errors against the model itself are
    raised as `MiniZincSolveError`.

    `max_operators_per_op` is the per-station upper bound (model
    decision-variable domain). `total_operators_budget` is an optional
    cap on the sum; when provided AND infeasible the model will emit
    `=====UNSATISFIABLE=====` and the caller can surface that as a
    user-facing message.
    """
    if not is_minizinc_available():
        raise MiniZincNotAvailableError(
            "MiniZinc CLI is not installed; operator-allocation optimization is unavailable."
        )

    data, operations = _build_minizinc_data(
        config,
        max_operators_per_op=max_operators_per_op,
        total_operators_budget=total_operators_budget,
    )

    if data["n_ops"] == 0:
        # No operations → nothing to optimize. Return an empty satisfied result.
        return OperatorAllocationResult(
            is_optimal=True,
            is_satisfied=True,
            status="empty",
            total_operators_before=0,
            total_operators_after=0,
            proposals=[],
            solver_message="No operations in configuration; nothing to optimize.",
        )

    mz_result: MiniZincResult = run_minizinc(
        _MODEL_PATH,
        data,
        timeout_seconds=timeout_seconds,
    )

    if not mz_result.is_satisfied or mz_result.solution is None:
        return OperatorAllocationResult(
            is_optimal=False,
            is_satisfied=False,
            status=mz_result.status_line or "unsatisfied",
            total_operators_before=sum(int(op.operators or 0) for op in operations),
            total_operators_after=0,
            proposals=[],
            raw_solver_output=mz_result.raw_stdout,
            solver_message=(
                "Optimization could not satisfy the demand constraints with the "
                "given budget. Try a higher max_operators_per_op or removing the "
                "total_operators_budget cap."
            ),
        )

    sol = mz_result.solution
    proposed_ops = sol.get("operators", [])
    predicted_per_op = sol.get("predicted_pcs_per_day_per_op", [])

    proposals = [
        OperatorAllocationProposal(
            product=op.product,
            step=int(op.step),
            operation=op.operation,
            machine_tool=op.machine_tool,
            sam_min=float(op.sam_min),
            grade_pct=float(op.grade_pct or 100),
            operators_before=int(op.operators or 0),
            operators_after=int(proposed_ops[i]),
            demand_pcs_per_day=int(data["demand_pcs_per_day"][i]),
            predicted_pcs_per_day=float(predicted_per_op[i] if i < len(predicted_per_op) else 0),
        )
        for i, op in enumerate(operations)
    ]

    return OperatorAllocationResult(
        is_optimal=mz_result.is_optimal,
        is_satisfied=True,
        status=mz_result.status_line or "satisfied",
        total_operators_before=sum(p.operators_before for p in proposals),
        total_operators_after=sum(p.operators_after for p in proposals),
        proposals=proposals,
        solver_message=(
            f"Optimal allocation found: {sum(p.operators_after for p in proposals)} operators "
            f"(was {sum(p.operators_before for p in proposals)})."
            if mz_result.is_optimal
            else "Allocation found but not proven optimal within timeout."
        ),
    )


# =============================================================================
# Apply optimization to a config (for the validation pass)
# =============================================================================


def apply_allocation_to_config(config: SimulationConfig, result: OperatorAllocationResult) -> SimulationConfig:
    """
    Return a copy of `config` whose operations carry the proposed
    operator counts. Used by the route to drive a SimPy validation
    run with the optimizer's recommendation.

    The `proposals` list aligns positionally with `config.operations`
    by construction (see `_build_minizinc_data`). If the lengths
    diverge the original config is returned unchanged.
    """
    if not result.is_satisfied or len(result.proposals) != len(config.operations):
        return config

    new_config = deepcopy(config)
    for op, prop in zip(new_config.operations, result.proposals):
        op.operators = prop.operators_after
    return new_config
