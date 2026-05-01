"""
WIP (Work-in-Process) orchestrators.

Three metrics:
  - calculate_wip_aging — raw days a hold has been open
  - calculate_wip_aging_adjusted — raw days minus accumulated hold-pause time
    (P2-001 hold-time adjusted aging)
  - calculate_hold_resolution_rate — percent of holds resolved within target

Phase 3 site assumption candidates: none directly. The aging thresholds
(7-day default / 14-day critical) are already in ClientConfig and don't rise
to "named assumption" — they're tier-2 per audit triage.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from backend.services.calculations.result import (
    CalculationMode,
    CalculationResult,
)


class WIPAgingInputs(BaseModel):
    hold_date: date
    as_of_date: date


class WIPAgingAdjustedInputs(BaseModel):
    raw_age_hours: Decimal = Field(ge=Decimal("0"))
    total_hold_duration_hours: Decimal = Field(ge=Decimal("0"))


class HoldResolutionInputs(BaseModel):
    resolved_on_time: int = Field(ge=0)
    total_resolved: int = Field(ge=0)


def calculate_wip_aging(
    inputs: WIPAgingInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[int]:
    """Raw aging in days = (as_of_date - hold_date).days. Negative ranges clamp to 0."""

    aging_days = (inputs.as_of_date - inputs.hold_date).days
    value = max(0, aging_days)

    return CalculationResult[int](
        metric_name="wip_aging",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_wip_aging_adjusted(
    inputs: WIPAgingAdjustedInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Adjusted age (hours) = raw_age - total_hold_duration. Floored at 0."""

    adjusted = inputs.raw_age_hours - inputs.total_hold_duration_hours
    value = max(Decimal("0"), adjusted)

    return CalculationResult[Decimal](
        metric_name="wip_aging_adjusted",
        value=value.quantize(Decimal("0.01")),
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_hold_resolution_rate(
    inputs: HoldResolutionInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Hold Resolution Rate % = resolved_on_time / total_resolved × 100."""

    if inputs.total_resolved == 0:
        value = Decimal("0")
    else:
        if inputs.resolved_on_time > inputs.total_resolved:
            raise ValueError("resolved_on_time cannot exceed total_resolved")
        value = (
            Decimal(str(inputs.resolved_on_time))
            / Decimal(str(inputs.total_resolved))
            * Decimal("100")
        ).quantize(Decimal("0.01"))

    return CalculationResult[Decimal](
        metric_name="hold_resolution_rate",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )
