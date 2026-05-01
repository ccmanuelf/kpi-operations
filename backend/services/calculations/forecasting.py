"""
Forecasting orchestrator.

Wraps simple_exponential_smoothing from backend.calculations.predictions.
The orchestrator only exposes the simple method; auto/double/linear variants
remain available via the underlying module.

Phase 3 site assumption candidates: none — the smoothing alpha is tier-2 per
audit triage (per-client tweakable, not a finance-approved assumption).
"""

from decimal import Decimal
from typing import List

from pydantic import BaseModel, Field

from backend.calculations.predictions import simple_exponential_smoothing
from backend.services.calculations.result import (
    CalculationMode,
    CalculationResult,
)


class ForecastInputs(BaseModel):
    historical_values: List[Decimal] = Field(min_length=2)
    alpha: Decimal = Field(gt=Decimal("0"), le=Decimal("1"), default=Decimal("0.3"))
    forecast_periods: int = Field(gt=0, default=7)


class ForecastValue(BaseModel):
    predictions: List[Decimal]
    lower_bounds: List[Decimal]
    upper_bounds: List[Decimal]
    confidence_scores: List[Decimal]
    method: str
    accuracy_score: Decimal


def calculate_forecast(
    inputs: ForecastInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[ForecastValue]:
    """Simple exponential-smoothing forecast with 95% confidence bounds."""

    result = simple_exponential_smoothing(
        values=inputs.historical_values,
        alpha=inputs.alpha,
        forecast_periods=inputs.forecast_periods,
    )

    value = ForecastValue(
        predictions=result.predictions,
        lower_bounds=result.lower_bounds,
        upper_bounds=result.upper_bounds,
        confidence_scores=result.confidence_scores,
        method=result.method,
        accuracy_score=result.accuracy_score,
    )

    return CalculationResult[ForecastValue](
        metric_name="forecast",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )
