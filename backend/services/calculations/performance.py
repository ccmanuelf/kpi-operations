"""
Performance, Quality Rate, Throughput, Lead Time, and Cycle Time orchestrators.

Performance and Quality Rate wrap pure helpers from backend.calculations.performance.
Throughput, Lead Time, and Cycle Time are simple compositions kept inline.

Phase 3 site assumption candidates:
  - ideal_cycle_time_source (Performance, Throughput)
  - scrap_classification_rule (Quality Rate — what counts as a defect vs scrap
    vs rework-recovered)
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from backend.calculations.performance import (
    calculate_performance_pure,
    calculate_quality_rate_pure,
)
from backend.services.calculations.result import (
    CalculationMode,
    CalculationResult,
)


class PerformanceInputs(BaseModel):
    units_produced: int = Field(ge=0)
    run_time_hours: Decimal = Field(ge=Decimal("0"))
    ideal_cycle_time_hours: Decimal = Field(gt=Decimal("0"))


class PerformanceValue(BaseModel):
    performance_pct: Decimal
    actual_rate_units_per_hour: Decimal


class QualityRateInputs(BaseModel):
    units_produced: int = Field(ge=0)
    defect_count: int = Field(ge=0)
    scrap_count: int = Field(ge=0)


class QualityRateValue(BaseModel):
    quality_rate_pct: Decimal
    good_units: int


class ThroughputInputs(BaseModel):
    units_produced: int = Field(ge=0)
    run_time_hours: Decimal = Field(ge=Decimal("0"))


class LeadTimeInputs(BaseModel):
    start_date: datetime
    end_date: datetime


class CycleTimeInputs(BaseModel):
    total_run_time_hours: Decimal = Field(ge=Decimal("0"))


class ExpectedOutputInputs(BaseModel):
    """Reverse-derive expected (target) output from actual + efficiency."""

    actual_output: int = Field(ge=0)
    efficiency_pct: Decimal = Field(gt=Decimal("0"), le=Decimal("150"))


def calculate_performance(
    inputs: PerformanceInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[PerformanceValue]:
    """Performance % = (ideal_cycle_time × units) / run_time_hours × 100, capped at 150."""

    perf, rate = calculate_performance_pure(
        units_produced=inputs.units_produced,
        run_time_hours=inputs.run_time_hours,
        ideal_cycle_time=inputs.ideal_cycle_time_hours,
    )

    return CalculationResult[PerformanceValue](
        metric_name="performance",
        value=PerformanceValue(performance_pct=perf, actual_rate_units_per_hour=rate),
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_quality_rate(
    inputs: QualityRateInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[QualityRateValue]:
    """Quality Rate % = (units - defects - scrap) / units × 100."""

    rate, good = calculate_quality_rate_pure(
        units_produced=inputs.units_produced,
        defect_count=inputs.defect_count,
        scrap_count=inputs.scrap_count,
    )

    return CalculationResult[QualityRateValue](
        metric_name="quality_rate",
        value=QualityRateValue(quality_rate_pct=rate, good_units=good),
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_throughput(
    inputs: ThroughputInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Throughput (units/hour) = units_produced / run_time_hours."""

    if inputs.run_time_hours == 0:
        value = Decimal("0")
    else:
        value = (
            Decimal(str(inputs.units_produced)) / inputs.run_time_hours
        ).quantize(Decimal("0.01"))

    return CalculationResult[Decimal](
        metric_name="throughput",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_lead_time(
    inputs: LeadTimeInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Optional[int]]:
    """Lead time (days) = (end_date - start_date).days + 1. Negative ranges return None."""

    delta_days = (inputs.end_date - inputs.start_date).days
    value: Optional[int] = delta_days + 1 if delta_days >= 0 else None

    return CalculationResult[Optional[int]](
        metric_name="lead_time",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_cycle_time(
    inputs: CycleTimeInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Cycle time (hours) for the work order is the summed run_time_hours."""

    return CalculationResult[Decimal](
        metric_name="cycle_time",
        value=inputs.total_run_time_hours.quantize(Decimal("0.01")),
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_expected_output(
    inputs: ExpectedOutputInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[int]:
    """Expected output = actual_output / (efficiency_pct / 100). Used in by-shift dashboards."""

    value = int(
        Decimal(str(inputs.actual_output)) / (inputs.efficiency_pct / Decimal("100"))
    )

    return CalculationResult[int](
        metric_name="expected_output",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )
