"""
Dual-view calculation orchestrators.

Each module wraps pure calculation functions from `backend.calculations.*` with
a CalculationResult envelope and a `mode: Literal["standard", "site_adjusted"]`
parameter. In Phase 1 both modes produce identical values; Phase 3 wires the
assumption registry so `site_adjusted` can diverge.

Design notes:
- Pure formulas live in `backend.calculations.*` (do not duplicate them here).
- Orchestrators here own the envelope, the inputs_consumed snapshot, and (in
  Phase 3) the assumption lookup. They must remain free of database access.
- Database-backed orchestration belongs in `backend.services.<domain>_service`,
  which calls these orchestrators with already-fetched inputs.
"""

from backend.services.calculations.result import (
    AssumptionApplied,
    CalculationMode,
    CalculationResult,
)

__all__ = ["AssumptionApplied", "CalculationMode", "CalculationResult"]
