"""
Efficiency orchestrator.

Wraps backend.calculations.efficiency.calculate_efficiency_pure.

Phase 1: site_adjusted == standard.
Phase 3 site assumption candidates that affect this metric:
  - ideal_cycle_time_source (engineering standard / demonstrated best /
    rolling 90-day average)
  - planned_production_time_basis (impacts scheduled_hours selection)
"""

from decimal import Decimal

from pydantic import BaseModel, Field

from backend.calculations.efficiency import calculate_efficiency_pure
from backend.services.calculations.result import (
    CalculationMode,
    CalculationResult,
)


class EfficiencyInputs(BaseModel):
    """Pre-fetched inputs for an efficiency calculation."""

    units_produced: int = Field(ge=0)
    ideal_cycle_time_hours: Decimal = Field(gt=Decimal("0"))
    employees_count: int = Field(ge=0)
    scheduled_hours: Decimal = Field(ge=Decimal("0"))


def calculate_efficiency(
    inputs: EfficiencyInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Efficiency % = (units × ideal_cycle_time) / (employees × scheduled_hours) × 100, capped at 150."""

    value = calculate_efficiency_pure(
        units_produced=inputs.units_produced,
        ideal_cycle_time=inputs.ideal_cycle_time_hours,
        employees_count=inputs.employees_count,
        scheduled_hours=inputs.scheduled_hours,
    )

    return CalculationResult[Decimal](
        metric_name="efficiency",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )
