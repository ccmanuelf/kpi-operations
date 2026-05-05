"""
Availability, MTBF, and MTTR orchestrators.

Phase 1: site_adjusted == standard.
Phase 3 site assumption candidates that affect these metrics:
  - planned_production_time_basis (does scheduled maintenance count as
    available time?)
  - setup_treatment (count setups as downtime / exclude from availability)
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from backend.services.calculations.result import (
    CalculationMode,
    CalculationResult,
)


class AvailabilityInputs(BaseModel):
    """Pre-aggregated scheduled and downtime hours for the period."""

    scheduled_hours: Decimal = Field(ge=Decimal("0"))
    downtime_hours: Decimal = Field(ge=Decimal("0"))


class MTBFInputs(BaseModel):
    """Operating time and failure count for the period."""

    operating_hours: Decimal = Field(ge=Decimal("0"))
    failure_count: int = Field(ge=0)


class MTTRInputs(BaseModel):
    """Total repair time and repair count for the period."""

    total_repair_hours: Decimal = Field(ge=Decimal("0"))
    repair_count: int = Field(ge=0)


def calculate_availability(
    inputs: AvailabilityInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Availability % = max(0, (scheduled_hours - downtime_hours) / scheduled_hours × 100)."""

    if inputs.scheduled_hours == 0:
        value = Decimal("0")
    else:
        available = inputs.scheduled_hours - inputs.downtime_hours
        raw = (available / inputs.scheduled_hours) * Decimal("100")
        value = max(Decimal("0"), raw)

    return CalculationResult[Decimal](
        metric_name="availability",
        value=value.quantize(Decimal("0.01")),
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_mtbf(
    inputs: MTBFInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Optional[Decimal]]:
    """MTBF (hours) = operating_hours / failure_count. None if no failures."""

    if inputs.failure_count == 0:
        value: Optional[Decimal] = None
    else:
        value = (inputs.operating_hours / Decimal(str(inputs.failure_count))).quantize(Decimal("0.01"))

    return CalculationResult[Optional[Decimal]](
        metric_name="mtbf",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_mttr(
    inputs: MTTRInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Optional[Decimal]]:
    """MTTR (hours) = total_repair_hours / repair_count. None if no repairs."""

    if inputs.repair_count == 0:
        value: Optional[Decimal] = None
    else:
        value = (inputs.total_repair_hours / Decimal(str(inputs.repair_count))).quantize(Decimal("0.01"))

    return CalculationResult[Optional[Decimal]](
        metric_name="mttr",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )
