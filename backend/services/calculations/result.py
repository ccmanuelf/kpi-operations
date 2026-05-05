"""
CalculationResult — the envelope returned by every dual-view orchestrator.

Required by the dual-view architecture spec § Phase 1: every metric calculation
must return a structured object containing the value, mode, inputs consumed,
assumptions applied (Phase 3+), and a timestamp.
"""

from datetime import datetime, timezone
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

CalculationMode = Literal["standard", "site_adjusted"]

T = TypeVar("T")


class AssumptionApplied(BaseModel):
    """A single assumption that affected a site_adjusted calculation."""

    name: str
    value: Any
    rationale: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None


class CalculationResult(BaseModel, Generic[T]):
    """Envelope returned by every metric orchestrator."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    metric_name: str
    value: T
    mode: CalculationMode
    inputs_consumed: dict[str, Any]
    assumptions_applied: list[AssumptionApplied] = Field(default_factory=list)
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
