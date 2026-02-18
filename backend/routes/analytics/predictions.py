"""
Analytics - KPI Predictive Forecasting Endpoint

Covers: GET /api/analytics/predictions with exponential smoothing and trend extrapolation.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, timedelta
from decimal import Decimal

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.schemas.analytics import (
    PredictionResponse,
    PredictionDataPoint,
    KPIType,
)
from backend.calculations.predictions import (
    auto_forecast,
    simple_exponential_smoothing,
    double_exponential_smoothing,
    linear_trend_extrapolation,
)
from backend.crud.analytics import get_kpi_time_series_data
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

predictions_router = APIRouter()


@predictions_router.get(
    "/predictions",
    response_model=PredictionResponse,
    summary="KPI Predictive Forecasting",
    description="""
    Forecast future KPI values using exponential smoothing and trend extrapolation.

    **Features:**
    - Automatic method selection based on data characteristics
    - Simple exponential smoothing for stable data
    - Double exponential smoothing (Holt's method) for trending data
    - Linear trend extrapolation
    - 95% confidence intervals
    - Accuracy scoring

    **Access Control:**
    - Client-specific data filtering enforced

    **Example Usage:**
    ```
    GET /api/analytics/predictions?client_id=BOOT-LINE-A&kpi_type=efficiency&forecast_days=7
    ```
    """,
    responses={
        200: {"description": "Forecast completed successfully"},
        400: {"description": "Insufficient data for forecasting"},
        403: {"description": "Access denied to client data"},
        404: {"description": "No historical data found"},
    },
)
async def get_kpi_predictions(
    client_id: str = Query(..., description="Client ID to forecast"),
    kpi_type: KPIType = Query(..., description="Type of KPI to forecast"),
    historical_days: int = Query(30, ge=7, le=90, description="Historical data window (7-90 days)"),
    forecast_days: int = Query(7, ge=1, le=30, description="Forecast horizon (1-30 days)"),
    method: Optional[str] = Query(
        None,
        pattern="^(auto|simple|double|linear)$",
        description="Forecasting method (auto, simple, double, linear)",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PredictionResponse:
    """
    GET /api/analytics/predictions - Predictive KPI forecasting with confidence intervals
    """
    verify_client_access(current_user, client_id)

    end_date = date.today()
    start_date = end_date - timedelta(days=historical_days)

    time_series = get_kpi_time_series_data(db, client_id, kpi_type.value, start_date, end_date, current_user)

    if len(time_series) < 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient historical data for forecasting. Need at least 7 days, found {len(time_series)}",
        )

    values = [v for d, v in time_series]

    if method is None or method == "auto":
        forecast_result = auto_forecast(values, forecast_days)
    elif method == "simple":
        forecast_result = simple_exponential_smoothing(values, forecast_periods=forecast_days)
    elif method == "double":
        forecast_result = double_exponential_smoothing(values, forecast_periods=forecast_days)
    elif method == "linear":
        forecast_result = linear_trend_extrapolation(values, forecast_periods=forecast_days)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown forecasting method: {method}")

    historical_avg = sum(values) / len(values)

    forecast_start = end_date + timedelta(days=1)
    forecast_dates = [forecast_start + timedelta(days=i) for i in range(forecast_days)]

    predictions = []
    for i in range(forecast_days):
        predictions.append(
            PredictionDataPoint(
                date=forecast_dates[i],
                predicted_value=forecast_result.predictions[i],
                lower_bound=forecast_result.lower_bounds[i],
                upper_bound=forecast_result.upper_bounds[i],
                confidence=forecast_result.confidence_scores[i],
            )
        )

    predicted_avg = sum(forecast_result.predictions) / len(forecast_result.predictions)
    trend_continuing = abs(predicted_avg - historical_avg) > historical_avg * Decimal("0.05")

    return PredictionResponse(
        client_id=client_id,
        kpi_type=kpi_type,
        prediction_method=forecast_result.method,
        historical_start=start_date,
        historical_end=end_date,
        forecast_start=forecast_start,
        forecast_end=forecast_dates[-1],
        predictions=predictions,
        model_accuracy=forecast_result.accuracy_score,
        historical_average=Decimal(str(round(historical_avg, 4))),
        predicted_average=Decimal(str(round(predicted_avg, 4))),
        trend_continuation=trend_continuing,
    )
