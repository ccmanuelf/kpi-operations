"""
OEE orchestrator (Overall Equipment Effectiveness).

Formula: OEE = (Availability × Performance × Quality) / 10_000

This orchestrator composes three already-computed component percentages. It does
not fetch ProductionEntry data; that responsibility belongs to the service that
collects the components and calls this orchestrator.

Phase 1: site_adjusted == standard (no assumption injection yet).
Phase 3: assumptions on the upstream components (e.g., setup_treatment,
ideal_cycle_time_source) flow through their respective orchestrators; this OEE
composition itself takes no direct assumptions.
"""

from decimal import Decimal

from pydantic import BaseModel, Field

from backend.services.calculations.result import (
    CalculationMode,
    CalculationResult,
)

METRIC_NAME = "oee"


class OEEInputs(BaseModel):
    """Pre-computed component percentages, each in [0, 150]."""

    availability_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("150"))
    performance_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("150"))
    quality_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("150"))


def calculate_oee(
    inputs: OEEInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Compute OEE in the requested mode and return the dual-view envelope."""

    value = (
        inputs.availability_pct
        * inputs.performance_pct
        * inputs.quality_pct
    ) / Decimal("10000")

    return CalculationResult[Decimal](
        metric_name=METRIC_NAME,
        value=value.quantize(Decimal("0.01")),
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )
