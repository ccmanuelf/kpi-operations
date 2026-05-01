"""
Pydantic schemas for the Phase 4 inspector API (`/api/metrics/results/...`).

The "lineage" response is what the inspector UI renders when a user clicks a
metric value. It expands `assumptions_snapshot` (a compact dict by name) into
full assumption metadata and includes the formula text + per-input help.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class MetricResultBrief(BaseModel):
    """List endpoint row — minimal fields for tables/charts."""

    model_config = ConfigDict(from_attributes=True)

    result_id: int
    client_id: str
    metric_name: str
    period_start: datetime
    period_end: datetime
    standard_value: Any
    site_adjusted_value: Any
    delta: Optional[float]
    delta_pct: Optional[float]
    has_assumptions: bool  # convenience: True if assumptions_snapshot is non-empty
    calculated_at: datetime


class AssumptionInLineage(BaseModel):
    """One assumption that affected a calculation, expanded for inspector display."""

    name: str
    value: Any
    description: Optional[str] = None  # from V1_CATALOG
    rationale: Optional[str] = None  # from CalculationAssumption
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    assumption_id: Optional[int] = None


class MetricLineage(BaseModel):
    """Full lineage view — what the inspector panel shows."""

    result_id: int
    client_id: str
    metric_name: str
    metric_display_name: str  # from METRIC_METADATA
    formula: str  # human-readable text per metric
    description: str
    period_start: datetime
    period_end: datetime
    standard_value: Any
    site_adjusted_value: Any
    delta: Optional[float]
    delta_pct: Optional[float]
    inputs: dict[str, Any]  # from inputs_snapshot_json
    inputs_help: dict[str, str]  # description per input field
    assumptions_applied: list[AssumptionInLineage]
    calculated_at: datetime
    calculated_by: Optional[str]
