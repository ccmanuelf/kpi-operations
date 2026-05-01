"""
Capacity orchestrators: Capacity Requirements, Production Capacity.

Phase 3 site assumption candidates:
  - planned_production_time_basis (impacts shift_hours selection)
  - ideal_cycle_time_source (impacts cycle_time_hours selection)
"""

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field

from backend.services.calculations.result import (
    CalculationMode,
    CalculationResult,
)


class CapacityRequirementsInputs(BaseModel):
    target_units: int = Field(ge=0)
    cycle_time_hours: Decimal = Field(gt=Decimal("0"))
    shift_hours: Decimal = Field(gt=Decimal("0"))
    target_efficiency_pct: Decimal = Field(gt=Decimal("0"), le=Decimal("100"))
    absenteeism_buffer_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"), default=Decimal("0"))


class CapacityRequirementsValue(BaseModel):
    required_employees: int
    buffer_employees: int
    total_recommended: int
    required_hours: Decimal


class ProductionCapacityInputs(BaseModel):
    employees: int = Field(ge=0)
    shift_hours: Decimal = Field(gt=Decimal("0"))
    cycle_time_hours: Decimal = Field(gt=Decimal("0"))
    efficiency_pct: Decimal = Field(gt=Decimal("0"), le=Decimal("150"))


class ComponentCoverageInputs(BaseModel):
    """MRP component-availability ratio. 100% if no requirement (nothing needed)."""

    available_quantity: Decimal = Field(ge=Decimal("0"))
    required_quantity: Decimal = Field(ge=Decimal("0"))


def calculate_capacity_requirements(
    inputs: CapacityRequirementsInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[CapacityRequirementsValue]:
    """
    Employees needed = (target_units × cycle_time) / (shift_hours × efficiency_factor),
    rounded up; plus an absenteeism buffer applied as a percentage.
    """

    target_units_dec = Decimal(str(inputs.target_units))
    efficiency_factor = inputs.target_efficiency_pct / Decimal("100")
    total_hours_needed = target_units_dec * inputs.cycle_time_hours
    effective_hours_per_employee = inputs.shift_hours * efficiency_factor

    raw_employees = (total_hours_needed / effective_hours_per_employee).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    required_employees = int(raw_employees.to_integral_value(rounding=ROUND_HALF_UP))

    buffer_rate = inputs.absenteeism_buffer_pct / Decimal("100")
    buffer_employees = int(
        (Decimal(required_employees) * buffer_rate).to_integral_value(rounding=ROUND_HALF_UP)
    )
    if required_employees > 0 and buffer_rate > 0 and buffer_employees == 0:
        buffer_employees = 1

    value = CapacityRequirementsValue(
        required_employees=required_employees,
        buffer_employees=buffer_employees,
        total_recommended=required_employees + buffer_employees,
        required_hours=total_hours_needed,
    )

    return CalculationResult[CapacityRequirementsValue](
        metric_name="capacity_requirements",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_production_capacity(
    inputs: ProductionCapacityInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Capacity (units) = (employees × shift_hours × efficiency_factor) / cycle_time."""

    efficiency_factor = inputs.efficiency_pct / Decimal("100")
    capacity = (
        Decimal(str(inputs.employees)) * inputs.shift_hours * efficiency_factor
    ) / inputs.cycle_time_hours

    return CalculationResult[Decimal](
        metric_name="production_capacity",
        value=capacity.quantize(Decimal("0.01")),
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_component_coverage(
    inputs: ComponentCoverageInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Coverage % = available / required × 100. 100% when nothing required."""

    if inputs.required_quantity == 0:
        value = Decimal("100.00")
    else:
        value = (
            inputs.available_quantity / inputs.required_quantity * Decimal("100")
        ).quantize(Decimal("0.01"))

    return CalculationResult[Decimal](
        metric_name="component_coverage",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )
