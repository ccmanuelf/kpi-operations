"""
Phase 5: Comprehensive Predictions API Routes
Advanced predictive analytics for all 10 KPIs

This module provides:
- Single KPI predictions with confidence intervals
- All-KPI predictions dashboard
- Health assessments and recommendations
- Demo data generation for testing

All endpoints enforce client access control and multi-tenant isolation
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
import logging

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.constants import (
    LOOKBACK_WEEKLY_DAYS,
    LOOKBACK_MONTHLY_DAYS,
    LOOKBACK_QUARTERLY_DAYS,
    MIN_FORECAST_DAYS,
    MAX_FORECAST_DAYS,
    MIN_HISTORICAL_DAYS,
    MAX_HISTORICAL_DAYS,
)
from backend.schemas.analytics import (
    KPIType,
    ComprehensivePredictionResponse,
    AllKPIPredictionsResponse,
    EnhancedPredictionDataPoint,
    KPIHistoryPoint,
    KPIHealthAssessment,
    KPIBenchmark,
)
from backend.calculations.predictions import (
    auto_forecast,
    simple_exponential_smoothing,
    double_exponential_smoothing,
    linear_trend_extrapolation,
    ForecastResult,
)
from backend.generators.sample_data_phase5 import (
    generate_kpi_history,
    generate_all_kpi_histories,
    get_kpi_benchmarks,
    calculate_kpi_health_score,
    KPIHistoryGenerator,
    KPITypePhase5,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


# KPI display names for human-readable output
KPI_DISPLAY_NAMES = {
    "efficiency": "Production Efficiency",
    "performance": "Production Performance",
    "availability": "Equipment Availability",
    "oee": "Overall Equipment Effectiveness",
    "ppm": "Parts Per Million (PPM)",
    "dpmo": "Defects Per Million Opportunities",
    "fpy": "First Pass Yield",
    "rty": "Rolled Throughput Yield",
    "absenteeism": "Absenteeism Rate",
    "otd": "On-Time Delivery",
    "quality": "Quality Rate",
    "defect_rate": "Defect Rate",
    "attendance": "Attendance Rate",
}


def get_historical_kpi_data(
    db: Session, client_id: str, kpi_type: str, start_date: date, end_date: date, current_user: User
) -> List[dict]:
    """
    Get historical KPI data for a client

    This function first attempts to retrieve data from the database.
    If insufficient data exists, it generates realistic demo data.

    Args:
        db: Database session
        client_id: Client ID
        kpi_type: Type of KPI
        start_date: Start date
        end_date: End date
        current_user: Current user for access control

    Returns:
        List of historical data points
    """
    from backend.middleware.client_auth import verify_client_access
    from backend.crud.analytics import get_kpi_time_series_data

    # Verify client access
    verify_client_access(current_user, client_id)

    # Try to get real data from database
    try:
        time_series = get_kpi_time_series_data(db, client_id, kpi_type, start_date, end_date, current_user)

        if len(time_series) >= 7:
            return [{"date": d, "value": float(v), "is_anomaly": False} for d, v in time_series]
    except Exception as e:
        logger.exception("Prediction failed: %s", e)

    # Fall back to generated demo data if insufficient real data
    days = (end_date - start_date).days + 1
    generator = KPIHistoryGenerator(seed=hash(f"{client_id}_{kpi_type}") % 10000)

    # Map to Phase5 KPI type if needed
    phase5_kpi = kpi_type
    if kpi_type == "quality":
        phase5_kpi = "fpy"  # Use FPY as proxy for quality
    elif kpi_type == "defect_rate":
        phase5_kpi = "ppm"  # Use PPM as proxy for defect_rate
    elif kpi_type == "attendance":
        phase5_kpi = "absenteeism"

    try:
        history = generator.generate_single_kpi(kpi_type=phase5_kpi, days=days, end_date=end_date, client_id=client_id)
        return history
    except ValueError:
        # Final fallback: generate efficiency data
        history = generator.generate_single_kpi(
            kpi_type="efficiency", days=days, end_date=end_date, client_id=client_id
        )
        return history


def build_comprehensive_prediction(
    client_id: str, kpi_type: str, historical_data: List[dict], forecast_days: int, method: Optional[str] = None
) -> ComprehensivePredictionResponse:
    """
    Build a comprehensive prediction response for a single KPI

    Args:
        client_id: Client ID
        kpi_type: Type of KPI
        historical_data: Historical data points
        forecast_days: Number of days to forecast
        method: Forecasting method (auto, simple, double, linear)

    Returns:
        ComprehensivePredictionResponse with full analytics
    """
    # Extract values for forecasting
    values = [Decimal(str(d["value"])) for d in historical_data]
    dates = [d["date"] for d in historical_data]

    # Get historical bounds
    historical_start = min(dates)
    historical_end = max(dates)
    current_value = float(values[-1]) if values else 0

    # Calculate historical average
    historical_average = sum(float(v) for v in values) / len(values) if values else 0

    # Run forecast
    if method is None or method == "auto":
        forecast_result = auto_forecast(values, forecast_days)
    elif method == "simple":
        forecast_result = simple_exponential_smoothing(values, forecast_periods=forecast_days)
    elif method == "double":
        forecast_result = double_exponential_smoothing(values, forecast_periods=forecast_days)
    elif method == "linear":
        forecast_result = linear_trend_extrapolation(values, forecast_periods=forecast_days)
    else:
        forecast_result = auto_forecast(values, forecast_days)

    # Generate forecast dates
    forecast_start = historical_end + timedelta(days=1)
    forecast_dates = [forecast_start + timedelta(days=i) for i in range(forecast_days)]

    # Build enhanced prediction data points
    predictions = []
    for i in range(forecast_days):
        pred_date = forecast_dates[i]
        predictions.append(
            EnhancedPredictionDataPoint(
                date=pred_date,
                predicted_value=float(forecast_result.predictions[i]),
                lower_bound=float(forecast_result.lower_bounds[i]),
                upper_bound=float(forecast_result.upper_bounds[i]),
                confidence=float(forecast_result.confidence_scores[i]),
                day_of_week=pred_date.strftime("%A"),
                is_weekend=pred_date.weekday() >= 5,
            )
        )

    # Calculate predicted average
    predicted_average = sum(float(p) for p in forecast_result.predictions) / len(forecast_result.predictions)

    # Get benchmarks
    benchmarks = get_kpi_benchmarks()
    kpi_benchmark_data = benchmarks.get(kpi_type, benchmarks.get("efficiency", {}))

    benchmark = KPIBenchmark(
        target=kpi_benchmark_data.get("target", 85.0),
        excellent=kpi_benchmark_data.get("excellent", 92.0),
        good=kpi_benchmark_data.get("good", 85.0),
        fair=kpi_benchmark_data.get("fair", 75.0),
        unit=kpi_benchmark_data.get("unit", "%"),
        description=kpi_benchmark_data.get("description", f"{kpi_type} metric"),
    )

    # Calculate health assessment
    health_data = calculate_kpi_health_score(
        current_value=current_value, predicted_value=predicted_average, kpi_type=kpi_type
    )

    health_assessment = KPIHealthAssessment(
        health_score=health_data["health_score"],
        trend=health_data["trend"],
        current_vs_target=health_data["current_vs_target"],
        recommendations=health_data["recommendations"],
    )

    # Build historical data points
    historical_points = [
        KPIHistoryPoint(date=d["date"], value=d["value"], is_anomaly=d.get("is_anomaly", False))
        for d in historical_data
    ]

    # Calculate expected change
    expected_change_percent = ((predicted_average - current_value) / current_value * 100) if current_value != 0 else 0

    # Determine trend continuation
    trend_continuation = abs(predicted_average - historical_average) > historical_average * 0.03

    # Calculate data quality score (based on data completeness and consistency)
    data_quality_score = min(100.0, len(historical_data) / 30 * 100)

    return ComprehensivePredictionResponse(
        client_id=client_id,
        kpi_type=kpi_type,
        kpi_display_name=KPI_DISPLAY_NAMES.get(kpi_type, kpi_type.replace("_", " ").title()),
        historical_start=historical_start,
        historical_end=historical_end,
        historical_data=historical_points,
        historical_average=round(historical_average, 2),
        current_value=round(current_value, 2),
        forecast_start=forecast_start,
        forecast_end=forecast_dates[-1] if forecast_dates else forecast_start,
        predictions=predictions,
        predicted_average=round(predicted_average, 2),
        prediction_method=forecast_result.method,
        model_accuracy=float(forecast_result.accuracy_score),
        health_assessment=health_assessment,
        benchmark=benchmark,
        trend_continuation=trend_continuation,
        expected_change_percent=round(expected_change_percent, 2),
        generated_at=datetime.now(tz=timezone.utc),
        data_quality_score=round(data_quality_score, 1),
    )


@router.get(
    "/{kpi_type}",
    response_model=ComprehensivePredictionResponse,
    summary="Get KPI Prediction with Full Analytics",
    description="""
    Generate comprehensive KPI prediction with:
    - Historical data analysis
    - Forecasted values with confidence intervals
    - Health assessment and recommendations
    - Industry benchmarks comparison

    **Supported KPI Types:**
    - efficiency, performance, availability, oee
    - ppm, dpmo, fpy, rty
    - absenteeism, otd, quality, attendance

    **Forecasting Methods:**
    - auto: Automatically selects best method
    - simple: Simple exponential smoothing
    - double: Double exponential smoothing (Holt's method)
    - linear: Linear trend extrapolation

    **Example:**
    ```
    GET /api/predictions/efficiency?client_id=BOOT-LINE-A&forecast_days=7
    ```
    """,
    responses={
        200: {"description": "Prediction generated successfully"},
        400: {"description": "Invalid parameters or insufficient data"},
        403: {"description": "Access denied to client data"},
        404: {"description": "KPI type not found"},
    },
)
async def get_kpi_prediction(
    kpi_type: str,
    client_id: Optional[str] = Query(None, description="Client ID to forecast (defaults to user's client)"),
    forecast_days: int = Query(LOOKBACK_WEEKLY_DAYS, ge=MIN_FORECAST_DAYS, le=MAX_FORECAST_DAYS, description="Forecast horizon (1-30 days)"),
    historical_days: int = Query(LOOKBACK_MONTHLY_DAYS, ge=MIN_HISTORICAL_DAYS, le=MAX_HISTORICAL_DAYS, description="Historical data window (7-90 days)"),
    method: Optional[str] = Query(None, pattern="^(auto|simple|double|linear)$", description="Forecasting method"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ComprehensivePredictionResponse:
    """
    GET /api/predictions/{kpi_type} - Comprehensive KPI prediction with analytics
    """
    # Use default client if not provided
    if not client_id:
        # Use user's associated client or a demo client
        client_id = getattr(current_user, "client_id", None) or "DEMO-CLIENT-001"

    # Validate KPI type
    valid_kpis = [e.value for e in KPIType] + [e.value for e in KPITypePhase5]
    if kpi_type not in valid_kpis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown KPI type: {kpi_type}. Valid types: {', '.join(set(valid_kpis))}",
        )

    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=historical_days)

    # Get historical data
    historical_data = get_historical_kpi_data(db, client_id, kpi_type, start_date, end_date, current_user)

    if len(historical_data) < 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient historical data. Need at least 7 days, found {len(historical_data)}",
        )

    # Build comprehensive prediction
    return build_comprehensive_prediction(
        client_id=client_id,
        kpi_type=kpi_type,
        historical_data=historical_data,
        forecast_days=forecast_days,
        method=method,
    )


@router.get(
    "/dashboard/all",
    response_model=AllKPIPredictionsResponse,
    summary="Get All KPI Predictions Dashboard",
    description="""
    Generate predictions for all 10 KPIs in a single dashboard response.

    This endpoint provides:
    - Individual predictions for each KPI
    - Overall health score across all KPIs
    - Count of improving, declining, and stable KPIs
    - Priority action recommendations

    **Ideal for:**
    - Executive dashboards
    - Daily KPI monitoring
    - Performance overview reports

    **Example:**
    ```
    GET /api/predictions/dashboard/all?client_id=BOOT-LINE-A&forecast_days=7
    ```
    """,
    responses={
        200: {"description": "All predictions generated successfully"},
        400: {"description": "Invalid parameters"},
        403: {"description": "Access denied to client data"},
    },
)
async def get_all_kpi_predictions(
    client_id: Optional[str] = Query(None, description="Client ID to forecast (defaults to user's client)"),
    forecast_days: int = Query(LOOKBACK_WEEKLY_DAYS, ge=MIN_FORECAST_DAYS, le=MAX_FORECAST_DAYS, description="Forecast horizon (1-30 days)"),
    historical_days: int = Query(LOOKBACK_MONTHLY_DAYS, ge=MIN_HISTORICAL_DAYS, le=MAX_HISTORICAL_DAYS, description="Historical data window (7-90 days)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AllKPIPredictionsResponse:
    """
    GET /api/predictions/dashboard/all - All KPI predictions dashboard
    """
    from backend.middleware.client_auth import verify_client_access

    # Use default client if not provided
    if not client_id:
        client_id = getattr(current_user, "client_id", None) or "DEMO-CLIENT-001"

    # Verify client access
    verify_client_access(current_user, client_id)

    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=historical_days)

    # Generate predictions for all Phase 5 KPIs
    kpi_predictions = {}
    health_scores = []
    improving = 0
    declining = 0
    stable = 0
    priority_actions = []

    for kpi in KPITypePhase5:
        try:
            historical_data = get_historical_kpi_data(db, client_id, kpi.value, start_date, end_date, current_user)

            if len(historical_data) >= 7:
                prediction = build_comprehensive_prediction(
                    client_id=client_id,
                    kpi_type=kpi.value,
                    historical_data=historical_data,
                    forecast_days=forecast_days,
                    method="auto",
                )

                kpi_predictions[kpi.value] = prediction
                health_scores.append(prediction.health_assessment.health_score)

                # Track trends
                if prediction.health_assessment.trend == "improving":
                    improving += 1
                elif prediction.health_assessment.trend == "declining":
                    declining += 1
                    # Add to priority actions if health is low
                    if prediction.health_assessment.health_score < 70:
                        priority_actions.append(
                            f"Review {prediction.kpi_display_name}: declining trend, score {prediction.health_assessment.health_score:.1f}"
                        )
                else:
                    stable += 1

                # Add recommendations from low-health KPIs
                if prediction.health_assessment.health_score < 60:
                    priority_actions.extend(prediction.health_assessment.recommendations[:2])

        except Exception as e:
            # Skip KPIs that fail to generate
            continue

    # Calculate overall health score
    overall_health_score = sum(health_scores) / len(health_scores) if health_scores else 50.0

    return AllKPIPredictionsResponse(
        client_id=client_id,
        forecast_days=forecast_days,
        generated_at=datetime.now(tz=timezone.utc),
        efficiency=kpi_predictions.get("efficiency"),
        performance=kpi_predictions.get("performance"),
        availability=kpi_predictions.get("availability"),
        oee=kpi_predictions.get("oee"),
        ppm=kpi_predictions.get("ppm"),
        dpmo=kpi_predictions.get("dpmo"),
        fpy=kpi_predictions.get("fpy"),
        rty=kpi_predictions.get("rty"),
        absenteeism=kpi_predictions.get("absenteeism"),
        otd=kpi_predictions.get("otd"),
        overall_health_score=round(overall_health_score, 1),
        kpis_improving=improving,
        kpis_declining=declining,
        kpis_stable=stable,
        priority_actions=priority_actions[:10],  # Limit to top 10 actions
    )


@router.get(
    "/benchmarks",
    summary="Get KPI Benchmarks",
    description="Get industry benchmark values for all 10 KPIs",
    responses={200: {"description": "Benchmarks retrieved successfully"}},
)
async def get_benchmarks(current_user: User = Depends(get_current_user)):
    """
    GET /api/predictions/benchmarks - Industry benchmark values
    """
    return get_kpi_benchmarks()


@router.post(
    "/demo/seed",
    summary="Seed Demo Prediction Data",
    description="""
    Generate and seed demo historical data for prediction testing.

    **Note:** This endpoint is for development/demo purposes only.
    In production, historical data comes from actual KPI measurements.
    """,
    responses={200: {"description": "Demo data seeded successfully"}, 403: {"description": "Admin access required"}},
)
async def seed_demo_data(
    client_id: str = Query("DEMO-CLIENT-001", description="Client ID for demo data"),
    days: int = Query(90, ge=30, le=365, description="Days of historical data"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    POST /api/predictions/demo/seed - Seed demo prediction data
    """
    # Admin only check
    if current_user.role not in ["admin", "super_admin", "ADMIN", "POWERUSER"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required for seeding demo data")

    from generators.sample_data_phase5 import seed_demo_predictions

    try:
        result = seed_demo_predictions(db, client_ids=[client_id], days=days)
        return {"message": "Demo data seeded successfully", **result}
    except Exception as e:
        logger.exception("Prediction operation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Prediction operation failed"
        )


@router.get(
    "/health/{kpi_type}",
    summary="Get KPI Health Assessment",
    description="Get health assessment for a specific KPI without full forecast",
    responses={200: {"description": "Health assessment retrieved successfully"}},
)
async def get_kpi_health(
    kpi_type: str,
    client_id: Optional[str] = Query(None, description="Client ID (defaults to user's client)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    GET /api/predictions/health/{kpi_type} - Quick health check for KPI
    """
    # Use default client if not provided
    if not client_id:
        client_id = getattr(current_user, "client_id", None) or "DEMO-CLIENT-001"

    # Get recent data (7 days)
    end_date = date.today()
    start_date = end_date - timedelta(days=7)

    historical_data = get_historical_kpi_data(db, client_id, kpi_type, start_date, end_date, current_user)

    if len(historical_data) < 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient data for health assessment")

    current_value = historical_data[-1]["value"]

    # Simple prediction using last 3 values average
    recent_avg = sum(d["value"] for d in historical_data[-3:]) / 3

    health_data = calculate_kpi_health_score(current_value=current_value, predicted_value=recent_avg, kpi_type=kpi_type)

    benchmarks = get_kpi_benchmarks()
    kpi_benchmark = benchmarks.get(kpi_type, {})

    return {
        "kpi_type": kpi_type,
        "client_id": client_id,
        "current_value": round(current_value, 2),
        "health_score": health_data["health_score"],
        "trend": health_data["trend"],
        "target": kpi_benchmark.get("target", 85.0),
        "current_vs_target": health_data["current_vs_target"],
        "recommendations": health_data["recommendations"],
        "assessed_at": datetime.now(tz=timezone.utc),
    }
