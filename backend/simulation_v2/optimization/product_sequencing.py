"""
Pattern 3 — product sequencing.

Given a SimulationConfig with multiple products and a pairwise
setup-time matrix supplied by the caller, find the production order
that minimizes the total wallclock makespan. Useful for campaign-mode
lines that produce one product at a time and pay a changeover cost
when switching between products.

Pattern 3 differs from Patterns 1+2 in that it requires an extra
input (`setup_times_minutes`) that doesn't live on the SimulationConfig.
The route layer accepts a list of `{from_product, to_product,
setup_minutes}` triples and the service marshals them into the dense
N×N matrix the model expects.

Edge cases handled here (and tested in test_product_sequencing.py):
  - n_products == 0 : Pydantic prevents (config.demands min_length=1).
  - n_products == 1 : sequencing is meaningless; helper short-circuits
    without invoking MZ. Returns order=[product_idx].
  - All setup_times = 0 : sequencing is irrelevant; helper still calls
    MZ which returns the lex-first permutation. Caller surface notes
    that the result is degenerate.
  - Asymmetric setup matrix : model handles directional setups (already
    in the formulation; a→b ≠ b→a).
  - Setup-time entries for products NOT in `config.demands` : ignored
    with a logged warning so the request stays robust to stale matrices.
  - Missing setup pair (i.e. the matrix has gaps) : default to 0.
"""

from __future__ import annotations

import logging
import math
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

_MODEL_PATH = Path(__file__).parent / "product_sequencing.mzn"


# =============================================================================
# Public dataclasses
# =============================================================================


@dataclass
class SequencedProduct:
    """One product's place in the optimized sequence."""

    position: int  # 1-indexed
    product: str
    production_time_minutes: int
    start_time_minutes: int
    end_time_minutes: int
    setup_from_previous_minutes: int


@dataclass
class SequencingResult:
    """Top-level sequencing result."""

    is_optimal: bool
    is_satisfied: bool
    status: str
    makespan_minutes: int
    total_setup_minutes: int
    total_production_minutes: int
    sequence: List[SequencedProduct] = field(default_factory=list)
    raw_solver_output: Optional[str] = None
    solver_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_optimal": self.is_optimal,
            "is_satisfied": self.is_satisfied,
            "status": self.status,
            "makespan_minutes": self.makespan_minutes,
            "total_setup_minutes": self.total_setup_minutes,
            "total_production_minutes": self.total_production_minutes,
            "sequence": [asdict(s) for s in self.sequence],
            "solver_message": self.solver_message,
        }


# =============================================================================
# Production-time helper
# =============================================================================


def estimate_production_time_minutes(
    config: SimulationConfig, product: str
) -> int:
    """
    Estimate the wallclock minutes the line spends producing this
    product's daily demand quota when the entire line is dedicated to
    one product at a time.

    Each operation is an independent station with parallel operators.
    The line's piece-rate is bounded by the SLOWEST station — that's
    the bottleneck for sequencing purposes. Time = demand / piece_rate.

    Returns 0 when demand is 0 or operations for this product are
    missing (caller decides whether to surface a warning).
    """
    demand = _resolve_daily_demand(config, product)
    if demand <= 0:
        return 0

    product_ops = [op for op in config.operations if op.product == product]
    if not product_ops:
        return 0

    # Piece-rate per minute at each op = operators * (1 / sam_min) * (grade_pct/100)
    # The line's piece-rate is the minimum across ops (bottleneck).
    rates = []
    for op in product_ops:
        operators = max(int(op.operators or 1), 1)
        sam = float(op.sam_min) if op.sam_min else 1.0
        grade = float(op.grade_pct or 100) / 100.0
        if sam <= 0:
            continue
        rate_pcs_per_min = operators * (1.0 / sam) * grade
        rates.append(rate_pcs_per_min)

    if not rates:
        return 0

    line_rate = min(rates)
    if line_rate <= 0:
        return 0

    minutes = demand / line_rate
    return int(math.ceil(minutes))


# =============================================================================
# Setup-time matrix marshalling
# =============================================================================


def _build_setup_matrix(
    products: List[str],
    setup_entries: List[Dict[str, Any]],
) -> List[List[int]]:
    """
    Translate a list of `{from_product, to_product, setup_minutes}`
    entries into a dense N×N integer matrix in the same row/column
    order as `products`.

    Defaults missing pairs to 0. Logs a warning for entries whose
    product names aren't in the products list (stale matrix tolerance).
    """
    n = len(products)
    index = {name: i for i, name in enumerate(products)}
    matrix = [[0] * n for _ in range(n)]
    for entry in setup_entries:
        src = entry.get("from_product")
        dst = entry.get("to_product")
        minutes = int(entry.get("setup_minutes", 0))
        if src not in index or dst not in index:
            logger.warning(
                "setup-time entry references unknown product(s): from=%r to=%r — ignored",
                src,
                dst,
            )
            continue
        if src == dst:
            # Self-setup is always 0; ignore stray entries.
            continue
        matrix[index[src]][index[dst]] = minutes
    return matrix


# =============================================================================
# Public service
# =============================================================================


def sequence_products(
    config: SimulationConfig,
    setup_entries: List[Dict[str, Any]],
    *,
    timeout_seconds: int = 30,
) -> SequencingResult:
    """
    Run the MiniZinc sequencing model against the given config and
    setup-time entries. Returns the optimized order with per-position
    start/end times and total makespan.
    """
    if not is_minizinc_available():
        raise MiniZincNotAvailableError(
            "MiniZinc CLI is not installed; product sequencing is unavailable."
        )

    # Use the products that have demand (sequencing is about demand quotas).
    products = [d.product for d in config.demands]
    n_products = len(products)

    if n_products == 0:
        # Pydantic prevents this on SimulationConfig but keep the guard.
        return SequencingResult(
            is_optimal=True,
            is_satisfied=True,
            status="empty",
            makespan_minutes=0,
            total_setup_minutes=0,
            total_production_minutes=0,
            sequence=[],
            solver_message="No products in configuration; nothing to sequence.",
        )

    production_time_minutes = [
        estimate_production_time_minutes(config, p) for p in products
    ]

    if n_products == 1:
        # Single product — no sequencing decision; report the trivial schedule.
        prod_min = production_time_minutes[0]
        return SequencingResult(
            is_optimal=True,
            is_satisfied=True,
            status="single-product",
            makespan_minutes=prod_min,
            total_setup_minutes=0,
            total_production_minutes=prod_min,
            sequence=[
                SequencedProduct(
                    position=1,
                    product=products[0],
                    production_time_minutes=prod_min,
                    start_time_minutes=0,
                    end_time_minutes=prod_min,
                    setup_from_previous_minutes=0,
                ),
            ],
            solver_message=(
                "Single-product configuration — sequencing is trivial. "
                f"Total wallclock: {prod_min} minutes."
            ),
        )

    setup_matrix = _build_setup_matrix(products, setup_entries)

    data = {
        "n_products": n_products,
        "production_time_min": production_time_minutes,
        "setup_time_min": setup_matrix,
    }

    mz_result: MiniZincResult = run_minizinc(
        _MODEL_PATH,
        data,
        timeout_seconds=timeout_seconds,
    )

    if not mz_result.is_satisfied or mz_result.solution is None:
        return SequencingResult(
            is_optimal=False,
            is_satisfied=False,
            status=mz_result.status_line or "unsatisfied",
            makespan_minutes=0,
            total_setup_minutes=0,
            total_production_minutes=sum(production_time_minutes),
            sequence=[],
            raw_solver_output=mz_result.raw_stdout,
            solver_message=(
                "Sequencer could not find a feasible permutation. This is "
                "rare for n_products ≤ ~10 with reasonable setup matrices; "
                "check the time-limit and the setup_time_min values for "
                "negative or extreme entries."
            ),
        )

    sol = mz_result.solution
    raw_order = sol.get("order", [])  # 1-indexed product indices
    raw_starts = sol.get("start_time_min", [])
    makespan = int(sol.get("makespan_min", 0))
    total_setup = int(sol.get("total_setup_min", 0))

    sequence = []
    prev_product_idx = None
    for position, idx_1based in enumerate(raw_order, start=1):
        product_idx = int(idx_1based) - 1  # back to 0-indexed
        product_name = products[product_idx]
        prod_min = production_time_minutes[product_idx]
        start_min = int(raw_starts[position - 1])
        end_min = start_min + prod_min
        if prev_product_idx is None:
            setup_min = 0
        else:
            setup_min = setup_matrix[prev_product_idx][product_idx]
        sequence.append(
            SequencedProduct(
                position=position,
                product=product_name,
                production_time_minutes=prod_min,
                start_time_minutes=start_min,
                end_time_minutes=end_min,
                setup_from_previous_minutes=setup_min,
            )
        )
        prev_product_idx = product_idx

    return SequencingResult(
        is_optimal=mz_result.is_optimal,
        is_satisfied=True,
        status=mz_result.status_line or "satisfied",
        makespan_minutes=makespan,
        total_setup_minutes=total_setup,
        total_production_minutes=sum(production_time_minutes),
        sequence=sequence,
        solver_message=(
            f"Optimal sequence found: makespan {makespan} min "
            f"(production {sum(production_time_minutes)} min + setup {total_setup} min)."
            if mz_result.is_optimal
            else "Sequence found but not proven optimal within timeout."
        ),
    )
