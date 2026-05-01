"""
Elapsed-time orchestrators.

Pure datetime arithmetic for work-order lifecycle metrics. No DB coupling;
service layer fetches the WorkOrder and feeds dates in.

Phase 3 site assumption candidates:
  - planned_production_time_basis (only affects business-hours calculations
    via the working_days / hours_per_day defaults — which already pass through
    as inputs here, so the orchestrator stays neutral)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from backend.services.calculations.result import (
    CalculationMode,
    CalculationResult,
)


class ElapsedHoursInputs(BaseModel):
    from_datetime: datetime
    to_datetime: Optional[datetime] = None  # defaults to now (UTC) if missing


class ElapsedDaysInputs(BaseModel):
    from_datetime: datetime
    to_datetime: Optional[datetime] = None


class BusinessHoursInputs(BaseModel):
    from_datetime: datetime
    to_datetime: Optional[datetime] = None
    hours_per_day: int = Field(gt=0, default=8)
    working_weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon-Fri


class DaysEarlyOrLateInputs(BaseModel):
    expected_date: datetime
    actual_date: datetime  # closure_date or now


def _ensure_tz(dt1: datetime, dt2: datetime) -> tuple[datetime, datetime]:
    if dt1.tzinfo is None and dt2.tzinfo is not None:
        dt1 = dt1.replace(tzinfo=timezone.utc)
    elif dt1.tzinfo is not None and dt2.tzinfo is None:
        dt2 = dt2.replace(tzinfo=timezone.utc)
    return dt1, dt2


def calculate_elapsed_hours(
    inputs: ElapsedHoursInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[int]:
    """Elapsed hours between from_datetime and to_datetime (now if missing)."""

    to_dt = inputs.to_datetime or datetime.now(tz=timezone.utc)
    from_dt, to_dt = _ensure_tz(inputs.from_datetime, to_dt)
    value = int((to_dt - from_dt).total_seconds() / 3600)

    return CalculationResult[int](
        metric_name="elapsed_hours",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_elapsed_days(
    inputs: ElapsedDaysInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Elapsed days (Decimal, 2 dp) between from_datetime and to_datetime."""

    to_dt = inputs.to_datetime or datetime.now(tz=timezone.utc)
    from_dt, to_dt = _ensure_tz(inputs.from_datetime, to_dt)
    value = Decimal(str(round((to_dt - from_dt).total_seconds() / 86400, 2)))

    return CalculationResult[Decimal](
        metric_name="elapsed_days",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_business_hours(
    inputs: BusinessHoursInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[int]:
    """Business hours between two datetimes (assumes whole working days)."""

    to_dt = inputs.to_datetime or datetime.now(tz=timezone.utc)
    from_dt, to_dt = _ensure_tz(inputs.from_datetime, to_dt)

    business_days = 0
    current = from_dt.date()
    end_date = to_dt.date()
    while current <= end_date:
        if current.weekday() in inputs.working_weekdays:
            business_days += 1
        current += timedelta(days=1)

    value = business_days * inputs.hours_per_day

    return CalculationResult[int](
        metric_name="business_hours",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_days_early_or_late(
    inputs: DaysEarlyOrLateInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[int]:
    """(expected - actual).days. Positive = early, negative = late."""

    expected, actual = _ensure_tz(inputs.expected_date, inputs.actual_date)
    value = (expected - actual).days

    return CalculationResult[int](
        metric_name="days_early_or_late",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )
