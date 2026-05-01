"""
Labor orchestrators: Absenteeism Rate, Attendance Rate, Bradford Factor.

The Bradford Factor formula (S² × D) and the absenteeism/attendance ratios are
all pure compositions; no DB-coupled helper exists upstream so they're inline.

Phase 3 site assumption candidates:
  - indirect_labor_allocation_rule (only relevant once labor cost metrics
    exist; deferred per audit reconciliation)
"""

from decimal import Decimal

from pydantic import BaseModel, Field

from backend.services.calculations.result import (
    CalculationMode,
    CalculationResult,
)


class AbsenteeismInputs(BaseModel):
    total_scheduled_hours: Decimal = Field(ge=Decimal("0"))
    total_absent_hours: Decimal = Field(ge=Decimal("0"))


class AttendanceInputs(BaseModel):
    days_present: int = Field(ge=0)
    total_scheduled_days: int = Field(ge=0)


class BradfordInputs(BaseModel):
    """Bradford Factor = S² × D where S = number of absence spells, D = total days absent."""

    spells: int = Field(ge=0)
    total_days_absent: int = Field(ge=0)


def calculate_absenteeism_rate(
    inputs: AbsenteeismInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Absenteeism % = total_absent_hours / total_scheduled_hours × 100."""

    if inputs.total_scheduled_hours == 0:
        value = Decimal("0")
    else:
        if inputs.total_absent_hours > inputs.total_scheduled_hours:
            raise ValueError("total_absent_hours cannot exceed total_scheduled_hours")
        value = (
            inputs.total_absent_hours
            / inputs.total_scheduled_hours
            * Decimal("100")
        ).quantize(Decimal("0.01"))

    return CalculationResult[Decimal](
        metric_name="absenteeism_rate",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_attendance_rate(
    inputs: AttendanceInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Attendance Rate % = days_present / total_scheduled_days × 100."""

    if inputs.total_scheduled_days == 0:
        value = Decimal("0")
    else:
        if inputs.days_present > inputs.total_scheduled_days:
            raise ValueError("days_present cannot exceed total_scheduled_days")
        value = (
            Decimal(str(inputs.days_present))
            / Decimal(str(inputs.total_scheduled_days))
            * Decimal("100")
        ).quantize(Decimal("0.01"))

    return CalculationResult[Decimal](
        metric_name="attendance_rate",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_bradford_factor(
    inputs: BradfordInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[int]:
    """Bradford Factor = spells² × total_days_absent."""

    value = (inputs.spells**2) * inputs.total_days_absent

    return CalculationResult[int](
        metric_name="bradford_factor",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )
