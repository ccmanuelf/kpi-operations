"""
Phase 3 dual-view services.

Per-metric service-layer wrappers that:
  1. Take pre-aggregated raw inputs (data fetching is the caller's job).
  2. Build the standard-mode InputsModel and call the pure orchestrator.
  3. Fetch the active assumption set via AssumptionService.
  4. Apply assumption-driven transformations to inputs.
  5. Call the pure orchestrator again in site_adjusted mode.
  6. Persist the result pair to METRIC_CALCULATION_RESULT.

Each service encapsulates *which assumptions affect which inputs* for one
metric. That mapping lives nowhere else in the codebase, so adding a new
assumption requires touching exactly one service per affected metric.
"""

from backend.services.dual_view.dual_view_result import DualViewResult

__all__ = ["DualViewResult"]
