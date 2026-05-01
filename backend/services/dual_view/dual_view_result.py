"""DualViewResult — what every Phase 3 service returns."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from backend.services.calculations.result import AssumptionApplied


class DualViewResult(BaseModel):
    """
    Container returned by every Phase 3 dual-view service.

    Both `standard_value` and `site_adjusted_value` are the metric's natural
    return shape (Decimal for OEE, dict for FPY breakdown, …); the route
    layer serializes them. `delta`/`delta_pct` are populated only when
    both values are scalar numerics.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    metric_name: str
    client_id: str
    period_start: datetime
    period_end: datetime
    standard_value: Any
    site_adjusted_value: Any
    delta: Optional[float] = None
    delta_pct: Optional[float] = None
    assumptions_applied: list[AssumptionApplied]
    assumptions_snapshot: dict[str, Any]  # what got persisted to DB
    calculated_at: datetime
    result_id: Optional[int] = None  # populated after persistence
