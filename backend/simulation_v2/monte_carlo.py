"""
Monte Carlo wrapper for SimPy V2 simulation.

Runs the existing single-replication engine N times with different RNG seeds,
then aggregates the eight output blocks into mean ± 95% CI estimates so
operators reading the simulation result can reason about uncertainty
instead of trusting a single point estimate.

The wrapper does NOT change the engine; it only orchestrates replications
and walks the resulting SimulationResults to produce per-field statistics
on every numeric leaf. Non-numeric fields (enums, strings, booleans,
audit logs) are preserved from a designated `sample_run` so consumers
have at least one concrete replication for inspection.

This addresses the simulator's largest credibility gap (single-rep,
no uncertainty bounds) without requiring engine refactoring.
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .calculations import calculate_all_blocks
from .engine import run_simulation
from .models import (
    SimulationConfig,
    SimulationResults,
    ValidationReport,
)
from .validation import validate_simulation_config


# =============================================================================
# Statistic computation
# =============================================================================


def compute_stat(values: List[float]) -> Dict[str, float]:
    """
    Aggregate a list of numeric replication values into mean ± 95% CI.

    Uses 1.96 * standard-error as the half-width (normal approximation).
    For N < 30 the t-distribution would be more accurate; the tradeoff
    here is simplicity and zero-dep stat math for an MVP. CI is still
    informative for the typical 10-50 replications operators will run.
    """
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "std": 0.0, "ci_lo_95": 0.0, "ci_hi_95": 0.0, "n": 0}

    mean = statistics.fmean(values)
    if n == 1:
        return {"mean": mean, "std": 0.0, "ci_lo_95": mean, "ci_hi_95": mean, "n": 1}

    std = statistics.stdev(values)
    se = std / math.sqrt(n)
    half_width = 1.96 * se
    return {
        "mean": mean,
        "std": std,
        "ci_lo_95": mean - half_width,
        "ci_hi_95": mean + half_width,
        "n": n,
    }


# =============================================================================
# Aggregation helpers
# =============================================================================

# Field names where Block 7 (rebalancing) recommendations and Block 8
# (assumption log) sit — these are not numeric metrics; we don't aggregate
# them, we surface the sample run.
_NON_NUMERIC_BLOCKS = {"rebalancing_suggestions", "assumption_log"}

# Per-row natural keys for blocks that are lists of homogeneous rows.
# When aligning rows across replications we group by the row's value of
# this key (or tuple of keys) so we average like-for-like.
_BLOCK_ROW_KEYS: Dict[str, Tuple[str, ...]] = {
    "weekly_demand_capacity": ("product",),
    "station_performance": ("product", "step", "operation"),
    "bundle_metrics": ("product",),
    "per_product_summary": ("product",),
}


def _is_numeric(value: Any) -> bool:
    """A bool is technically int in Python; exclude it from numeric stats."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _aggregate_singleton(rows_per_run: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate a single-object block (e.g. daily_summary) across replications.

    Numeric fields → MonteCarloStat dicts.
    Non-numeric fields → first run's value (deterministic across runs in
    practice; if not, a stable representative is fine for non-stat fields).
    """
    if not rows_per_run:
        return {}

    first = rows_per_run[0]
    out: Dict[str, Any] = {}
    for field, sample_value in first.items():
        if _is_numeric(sample_value):
            values = [r.get(field, 0) for r in rows_per_run if _is_numeric(r.get(field))]
            out[field] = compute_stat(values)
        else:
            out[field] = sample_value
    return out


def _aggregate_list_block(
    rows_per_run: List[List[Dict[str, Any]]],
    key_fields: Tuple[str, ...],
) -> List[Dict[str, Any]]:
    """
    Aggregate a list-of-rows block (e.g. weekly_demand_capacity).

    Each replication produces a list of rows. We group rows across
    replications by `key_fields` and aggregate numeric fields per group.
    Rows that appear in some replications but not others contribute only
    where they exist (stat's `n` reflects this).
    """
    grouped: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for run_rows in rows_per_run:
        for row in run_rows:
            key = tuple(row.get(k) for k in key_fields)
            grouped.setdefault(key, []).append(row)

    aggregated_rows: List[Dict[str, Any]] = []
    for key, rows in grouped.items():
        first = rows[0]
        out_row: Dict[str, Any] = {}
        for field, sample_value in first.items():
            if _is_numeric(sample_value):
                values = [r.get(field, 0) for r in rows if _is_numeric(r.get(field))]
                out_row[field] = compute_stat(values)
            else:
                out_row[field] = sample_value
        aggregated_rows.append(out_row)
    return aggregated_rows


def aggregate_runs(runs: List[SimulationResults]) -> Dict[str, Any]:
    """
    Walk N SimulationResults, produce per-block aggregated stats.

    Output shape (per block):
      - Singleton blocks (daily_summary, free_capacity): one dict whose
        numeric fields are stat dicts and non-numeric fields are
        carried through unchanged.
      - List-of-rows blocks (weekly_demand_capacity, station_performance,
        bundle_metrics, per_product_summary): list of dicts grouped by
        the block's natural key, each with numeric fields as stat dicts.
      - Non-numeric blocks (rebalancing_suggestions, assumption_log):
        omitted here — the route returns them via the sample_run alongside.
    """
    if not runs:
        return {}

    # Each run's results is a Pydantic model; serialise to plain dicts
    # so we can walk the structure uniformly.
    dumps = [r.model_dump(mode="python") for r in runs]

    aggregated: Dict[str, Any] = {}

    # Singleton blocks
    for block in ("daily_summary", "free_capacity"):
        rows = [d.get(block, {}) for d in dumps]
        aggregated[block] = _aggregate_singleton(rows)

    # List blocks
    for block, key_fields in _BLOCK_ROW_KEYS.items():
        rows_per_run = [d.get(block, []) for d in dumps]
        aggregated[block] = _aggregate_list_block(rows_per_run, key_fields)

    return aggregated


# =============================================================================
# Public runner
# =============================================================================


def run_monte_carlo(
    config: SimulationConfig,
    n_replications: int,
    base_seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Run N replications of the simulation engine, aggregate results.

    Args:
        config: Simulation configuration (validated by caller).
        n_replications: Number of replications to run (caller enforces bounds).
        base_seed: Optional anchor for the seed sequence; replication i uses
            `base_seed + i` so the run is fully reproducible. If None,
            replications use independent RNG state from the global Python
            random module.

    Returns:
        Dict with keys:
          - n_replications: int
          - base_seed: Optional[int]
          - total_duration_seconds: float
          - per_run_duration_seconds: list[float]
          - validation_report: ValidationReport (from the canonical config)
          - sample_run: SimulationResults — the replication that used
            seed=base_seed (or the first run if base_seed is None) for
            non-numeric blocks (rebalancing_suggestions, assumption_log)
            and as a concrete reference shape.
          - aggregated_stats: Dict[str, Any] — see `aggregate_runs`.
    """
    start = datetime.now(tz=timezone.utc)

    validation_report = validate_simulation_config(config)
    if validation_report.has_errors:
        # Mirror the route's contract: bail with the validation report;
        # caller decides what to do.
        return {
            "n_replications": 0,
            "base_seed": base_seed,
            "total_duration_seconds": 0.0,
            "per_run_duration_seconds": [],
            "validation_report": validation_report,
            "sample_run": None,
            "aggregated_stats": {},
        }

    runs: List[SimulationResults] = []
    durations: List[float] = []

    for i in range(n_replications):
        seed = (base_seed + i) if base_seed is not None else None
        metrics, duration = run_simulation(config, seed=seed)
        results = calculate_all_blocks(
            config=config,
            metrics=metrics,
            validation_report=validation_report,
            duration_seconds=duration,
            defaults_applied=[],  # caller can attach to sample_run separately
        )
        runs.append(results)
        durations.append(duration)

    aggregated_stats = aggregate_runs(runs)
    end = datetime.now(tz=timezone.utc)

    return {
        "n_replications": n_replications,
        "base_seed": base_seed,
        "total_duration_seconds": (end - start).total_seconds(),
        "per_run_duration_seconds": durations,
        "validation_report": validation_report,
        "sample_run": runs[0] if runs else None,
        "aggregated_stats": aggregated_stats,
    }
