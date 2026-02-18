"""
Analytics - KPI Trend Analysis Endpoint

Covers: GET /api/analytics/trends with moving averages and anomaly detection.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, timedelta
from decimal import Decimal
import statistics

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.schemas.analytics import (
    TrendAnalysisResponse,
    TrendDataPoint,
    TrendDirection,
    KPIType,
)
from backend.calculations.trend_analysis import calculate_moving_average, analyze_trend, detect_anomalies
from backend.crud.analytics import get_kpi_time_series_data
from backend.utils.logging_utils import get_module_logger
from ._helpers import parse_time_range

logger = get_module_logger(__name__)

trends_router = APIRouter()


@trends_router.get(
    "/trends",
    response_model=TrendAnalysisResponse,
    summary="KPI Trend Analysis",
    description="""
    Analyze KPI trends over time with moving averages, linear regression, and anomaly detection.

    **Features:**
    - 7-day and 30-day moving averages
    - Linear regression with R-squared
    - Trend direction classification (increasing, decreasing, stable, volatile)
    - Anomaly detection using standard deviation method

    **Access Control:**
    - Client-specific data filtering enforced
    - Only accessible clients are returned

    **Example Usage:**
    ```
    GET /api/analytics/trends?client_id=BOOT-LINE-A&kpi_type=efficiency&time_range=30d
    ```
    """,
    responses={
        200: {"description": "Trend analysis completed successfully"},
        400: {"description": "Invalid parameters"},
        403: {"description": "Access denied to client data"},
        404: {"description": "No data found for specified parameters"},
    },
)
async def get_kpi_trends(
    client_id: str = Query(..., description="Client ID to analyze"),
    kpi_type: KPIType = Query(..., description="Type of KPI to analyze"),
    time_range: str = Query("30d", pattern="^(7d|30d|90d)$", description="Time range (7d, 30d, 90d)"),
    start_date: Optional[date] = Query(None, description="Custom start date (overrides time_range)"),
    end_date: Optional[date] = Query(None, description="Custom end date (defaults to today)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrendAnalysisResponse:
    """
    GET /api/analytics/trends - KPI trend analysis with moving averages and anomaly detection
    """
    verify_client_access(current_user, client_id)

    if start_date and end_date:
        pass  # Use provided dates
    else:
        start_date, end_date = parse_time_range(time_range, end_date)

    time_series = get_kpi_time_series_data(db, client_id, kpi_type.value, start_date, end_date, current_user)

    if not time_series:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {kpi_type.value} data found for client {client_id} in specified date range",
        )

    dates = [d for d, v in time_series]
    values = [v for d, v in time_series]

    ma_7 = calculate_moving_average(values, 7)
    ma_30 = calculate_moving_average(values, 30)

    data_points = []
    for i in range(len(dates)):
        data_points.append(
            TrendDataPoint(date=dates[i], value=values[i], moving_average_7=ma_7[i], moving_average_30=ma_30[i])
        )

    trend_result = analyze_trend(dates, values)

    float_values = [float(v) for v in values]
    avg_value = Decimal(str(statistics.mean(float_values)))
    std_dev = Decimal(str(statistics.stdev(float_values))) if len(float_values) > 1 else Decimal("0")
    min_value = min(values)
    max_value = max(values)

    anomaly_indices = detect_anomalies(values, Decimal("2.0"))
    anomaly_dates = [dates[i] for i in anomaly_indices]

    return TrendAnalysisResponse(
        client_id=client_id,
        kpi_type=kpi_type,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        data_points=data_points,
        trend_direction=TrendDirection(trend_result.trend_direction),
        trend_slope=trend_result.slope,
        average_value=avg_value,
        std_deviation=std_dev,
        min_value=min_value,
        max_value=max_value,
        anomalies_detected=len(anomaly_indices),
        anomaly_dates=anomaly_dates,
    )
