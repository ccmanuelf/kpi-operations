"""
Advanced Analytics API Routes
Provides KPI trend analysis, predictions, comparisons, heatmap, and Pareto analysis

All endpoints enforce client access control and multi-tenant isolation
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, timedelta, datetime
from decimal import Decimal
import statistics

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.schemas.analytics import (
    TrendAnalysisResponse,
    TrendDataPoint,
    TrendDirection,
    KPIType,
    TimeRange,
    PredictionResponse,
    PredictionDataPoint,
    ComparisonResponse,
    ClientComparisonData,
    HeatmapResponse,
    HeatmapCell,
    ParetoResponse,
    ParetoItem,
)
from backend.calculations.trend_analysis import calculate_moving_average, analyze_trend, detect_anomalies
from backend.calculations.predictions import (
    auto_forecast,
    simple_exponential_smoothing,
    double_exponential_smoothing,
    linear_trend_extrapolation,
)
from backend.crud.analytics import (
    get_kpi_time_series_data,
    get_shift_heatmap_data,
    get_client_comparison_data,
    get_defect_pareto_data,
    get_all_shifts,
    get_client_info,
    get_date_range_data_availability,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def parse_time_range(time_range: str, end_date: Optional[date] = None) -> tuple[date, date]:
    """
    Parse time range string to start and end dates

    Args:
        time_range: Time range ('7d', '30d', '90d')
        end_date: Optional end date (defaults to today)

    Returns:
        Tuple of (start_date, end_date)
    """
    if end_date is None:
        end_date = date.today()

    if time_range == "7d":
        start_date = end_date - timedelta(days=7)
    elif time_range == "30d":
        start_date = end_date - timedelta(days=30)
    elif time_range == "90d":
        start_date = end_date - timedelta(days=90)
    else:
        raise ValueError(f"Invalid time range: {time_range}")

    return start_date, end_date


def get_performance_rating(value: Decimal, benchmark: Decimal) -> str:
    """
    Determine performance rating based on value and benchmark

    Args:
        value: KPI value
        benchmark: Benchmark value

    Returns:
        Performance rating string
    """
    ratio = float(value / benchmark) if benchmark > 0 else 0

    if ratio >= 1.1:
        return "Excellent"
    elif ratio >= 0.95:
        return "Good"
    elif ratio >= 0.85:
        return "Fair"
    else:
        return "Poor"


def get_heatmap_color_code(value: Optional[Decimal], benchmark: Decimal = Decimal("85.0")) -> tuple[str, str]:
    """
    Get performance level and color code for heatmap cell

    Args:
        value: KPI value (None if no data)
        benchmark: Benchmark for comparison

    Returns:
        Tuple of (performance_level, color_code)
    """
    if value is None:
        return ("No Data", "#94a3b8")

    if value >= benchmark * Decimal("1.1"):
        return ("Excellent", "#22c55e")
    elif value >= benchmark:
        return ("Good", "#84cc16")
    elif value >= benchmark * Decimal("0.9"):
        return ("Fair", "#eab308")
    else:
        return ("Poor", "#ef4444")


@router.get(
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
    time_range: str = Query("30d", regex="^(7d|30d|90d)$", description="Time range (7d, 30d, 90d)"),
    start_date: Optional[date] = Query(None, description="Custom start date (overrides time_range)"),
    end_date: Optional[date] = Query(None, description="Custom end date (defaults to today)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TrendAnalysisResponse:
    """
    GET /api/analytics/trends - KPI trend analysis with moving averages and anomaly detection
    """
    # Parse date range
    if start_date and end_date:
        pass  # Use provided dates
    else:
        start_date, end_date = parse_time_range(time_range, end_date)

    # Retrieve time series data
    time_series = get_kpi_time_series_data(db, client_id, kpi_type.value, start_date, end_date, current_user)

    if not time_series:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {kpi_type.value} data found for client {client_id} in specified date range",
        )

    # Extract dates and values
    dates = [d for d, v in time_series]
    values = [v for d, v in time_series]

    # Calculate moving averages
    ma_7 = calculate_moving_average(values, 7)
    ma_30 = calculate_moving_average(values, 30)

    # Build data points
    data_points = []
    for i in range(len(dates)):
        data_points.append(
            TrendDataPoint(date=dates[i], value=values[i], moving_average_7=ma_7[i], moving_average_30=ma_30[i])
        )

    # Perform trend analysis
    trend_result = analyze_trend(dates, values)

    # Calculate statistics
    float_values = [float(v) for v in values]
    avg_value = Decimal(str(statistics.mean(float_values)))
    std_dev = Decimal(str(statistics.stdev(float_values))) if len(float_values) > 1 else Decimal("0")
    min_value = min(values)
    max_value = max(values)

    # Detect anomalies
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


@router.get(
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
        None, regex="^(auto|simple|double|linear)$", description="Forecasting method (auto, simple, double, linear)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PredictionResponse:
    """
    GET /api/analytics/predictions - Predictive KPI forecasting with confidence intervals
    """
    # Calculate date range for historical data
    end_date = date.today()
    start_date = end_date - timedelta(days=historical_days)

    # Retrieve historical time series
    time_series = get_kpi_time_series_data(db, client_id, kpi_type.value, start_date, end_date, current_user)

    if len(time_series) < 7:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient historical data for forecasting. Need at least 7 days, found {len(time_series)}",
        )

    # Extract values
    values = [v for d, v in time_series]

    # Select forecasting method
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

    # Calculate historical average
    historical_avg = sum(values) / len(values)

    # Generate forecast dates
    forecast_start = end_date + timedelta(days=1)
    forecast_dates = [forecast_start + timedelta(days=i) for i in range(forecast_days)]

    # Build prediction data points
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

    # Calculate predicted average
    predicted_avg = sum(forecast_result.predictions) / len(forecast_result.predictions)

    # Determine if trend is continuing
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


@router.get(
    "/comparisons",
    response_model=ComparisonResponse,
    summary="Client-to-Client Benchmarking",
    description="""
    Compare KPI performance across multiple clients with percentile rankings.

    **Features:**
    - Client performance comparison
    - Percentile rankings (0-100)
    - Industry benchmark comparison
    - Performance ratings (Excellent, Good, Fair, Poor)
    - Best and worst performer identification

    **Access Control:**
    - Only shows clients the user has access to
    - ADMIN/POWERUSER see all clients
    - LEADER/OPERATOR see only assigned clients

    **Example Usage:**
    ```
    GET /api/analytics/comparisons?kpi_type=efficiency&time_range=30d
    ```
    """,
    responses={
        200: {"description": "Comparison completed successfully"},
        400: {"description": "Invalid parameters"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "No data found"},
    },
)
async def get_client_comparisons(
    kpi_type: KPIType = Query(..., description="Type of KPI to compare"),
    time_range: str = Query("30d", regex="^(7d|30d|90d)$", description="Time range (7d, 30d, 90d)"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ComparisonResponse:
    """
    GET /api/analytics/comparisons - Client-to-client KPI benchmarking
    """
    # Parse date range
    if start_date and end_date:
        pass
    else:
        start_date, end_date = parse_time_range(time_range, end_date)

    # Retrieve comparison data
    comparison_data = get_client_comparison_data(db, kpi_type.value, start_date, end_date, current_user)

    if not comparison_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {kpi_type.value} data found for any accessible clients in specified date range",
        )

    # Calculate overall statistics
    all_values = [avg_value for _, _, avg_value, _ in comparison_data]
    overall_avg = sum(all_values) / len(all_values)

    # Industry benchmark (default 85% for most KPIs)
    industry_benchmark = Decimal("85.0")

    # Sort by value for percentile calculation
    sorted_values = sorted(all_values)

    # Build client comparison data
    clients = []
    for client_id, client_name, avg_value, data_points in comparison_data:
        # Calculate percentile rank
        rank_position = sorted_values.index(avg_value)
        percentile_rank = int((rank_position / (len(sorted_values) - 1)) * 100) if len(sorted_values) > 1 else 50

        # Determine if above benchmark
        above_benchmark = avg_value >= industry_benchmark

        # Get performance rating
        performance_rating = get_performance_rating(avg_value, industry_benchmark)

        clients.append(
            ClientComparisonData(
                client_id=client_id,
                client_name=client_name,
                average_value=avg_value,
                percentile_rank=percentile_rank,
                above_benchmark=above_benchmark,
                performance_rating=performance_rating,
                total_data_points=data_points,
            )
        )

    # Identify best and worst performers
    best_performer = comparison_data[0][0]  # First in descending order
    worst_performer = comparison_data[-1][0]  # Last in descending order
    performance_spread = all_values[0] - all_values[-1]

    return ComparisonResponse(
        kpi_type=kpi_type,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        clients=clients,
        overall_average=Decimal(str(round(overall_avg, 4))),
        industry_benchmark=industry_benchmark,
        best_performer=best_performer,
        worst_performer=worst_performer,
        performance_spread=Decimal(str(round(performance_spread, 4))),
    )


@router.get(
    "/heatmap",
    response_model=HeatmapResponse,
    summary="Performance Heatmap (Date x Shift)",
    description="""
    Generate performance heatmap showing KPI values by date and shift.

    **Features:**
    - Matrix visualization (date x shift)
    - Color-coded performance levels
    - Missing data handling
    - Suggested color scale for UI rendering

    **Performance Levels:**
    - Excellent: >110% of benchmark (Green #22c55e)
    - Good: 100-110% of benchmark (Lime #84cc16)
    - Fair: 90-100% of benchmark (Yellow #eab308)
    - Poor: <90% of benchmark (Red #ef4444)
    - No Data: Missing (Gray #94a3b8)

    **Access Control:**
    - Client-specific data filtering enforced

    **Example Usage:**
    ```
    GET /api/analytics/heatmap?client_id=BOOT-LINE-A&kpi_type=efficiency&time_range=30d
    ```
    """,
    responses={
        200: {"description": "Heatmap generated successfully"},
        403: {"description": "Access denied to client data"},
        404: {"description": "No data found"},
    },
)
async def get_performance_heatmap(
    client_id: str = Query(..., description="Client ID to visualize"),
    kpi_type: KPIType = Query(..., description="Type of KPI to visualize"),
    time_range: str = Query("30d", regex="^(7d|30d|90d)$", description="Time range (7d, 30d, 90d)"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HeatmapResponse:
    """
    GET /api/analytics/heatmap - Performance heatmap by shift and date
    """
    # Parse date range
    if start_date and end_date:
        pass
    else:
        start_date, end_date = parse_time_range(time_range, end_date)

    # Retrieve heatmap data
    heatmap_data = get_shift_heatmap_data(db, client_id, kpi_type.value, start_date, end_date, current_user)

    # Get all shifts for matrix
    all_shifts = get_all_shifts(db)
    shift_names = [name for _, name in all_shifts]

    # Generate all dates in range
    all_dates = []
    current_date = start_date
    while current_date <= end_date:
        all_dates.append(current_date)
        current_date += timedelta(days=1)

    # Create lookup dictionary for quick access
    data_lookup = {(d, shift_id): (shift_name, value) for d, shift_id, shift_name, value in heatmap_data}

    # Build heatmap cells (fill in missing data)
    cells = []
    benchmark = Decimal("85.0")

    for current_date in all_dates:
        for shift_id, shift_name in all_shifts:
            # Check if data exists
            key = (current_date, shift_id)
            if key in data_lookup:
                _, value = data_lookup[key]
            else:
                value = None

            # Get performance level and color
            performance_level, color_code = get_heatmap_color_code(value, benchmark)

            cells.append(
                HeatmapCell(
                    date=current_date,
                    shift_id=shift_id,
                    shift_name=shift_name,
                    value=value,
                    performance_level=performance_level,
                    color_code=color_code,
                )
            )

    # Color scale mapping
    color_scale = {
        "Excellent": "#22c55e",
        "Good": "#84cc16",
        "Fair": "#eab308",
        "Poor": "#ef4444",
        "No Data": "#94a3b8",
    }

    return HeatmapResponse(
        client_id=client_id,
        kpi_type=kpi_type,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        cells=cells,
        shifts=shift_names,
        dates=all_dates,
        color_scale=color_scale,
    )


@router.get(
    "/pareto",
    response_model=ParetoResponse,
    summary="Defect Pareto Analysis",
    description="""
    Perform Pareto analysis on defect types to identify vital few categories (80/20 rule).

    **Features:**
    - Defects ranked by frequency
    - Cumulative percentage calculation
    - Vital few identification (80% threshold)
    - Pareto principle application

    **Use Cases:**
    - Quality improvement prioritization
    - Root cause analysis
    - Resource allocation for defect reduction

    **Access Control:**
    - Client-specific data filtering enforced

    **Example Usage:**
    ```
    GET /api/analytics/pareto?client_id=BOOT-LINE-A&time_range=30d
    ```
    """,
    responses={
        200: {"description": "Pareto analysis completed successfully"},
        403: {"description": "Access denied to client data"},
        404: {"description": "No defect data found"},
    },
)
async def get_defect_pareto_analysis(
    client_id: str = Query(..., description="Client ID to analyze"),
    time_range: str = Query("30d", regex="^(7d|30d|90d)$", description="Time range (7d, 30d, 90d)"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    pareto_threshold: Decimal = Query(Decimal("80.0"), ge=50, le=95, description="Pareto threshold percentage"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ParetoResponse:
    """
    GET /api/analytics/pareto - Defect Pareto analysis (80/20 rule)
    """
    # Parse date range
    if start_date and end_date:
        pass
    else:
        start_date, end_date = parse_time_range(time_range, end_date)

    # Retrieve defect data
    defect_data = get_defect_pareto_data(db, client_id, start_date, end_date, current_user)

    if not defect_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No defect data found for client {client_id} in specified date range",
        )

    # Calculate total defects
    total_defects = sum(count for _, count in defect_data)

    # Build Pareto items
    items = []
    cumulative_count = 0
    vital_few_count = 0

    for defect_type, count in defect_data:
        cumulative_count += count

        percentage = Decimal(str((count / total_defects) * 100))
        cumulative_percentage = Decimal(str((cumulative_count / total_defects) * 100))

        is_vital_few = cumulative_percentage <= pareto_threshold

        if is_vital_few:
            vital_few_count += 1

        items.append(
            ParetoItem(
                defect_type=defect_type,
                count=count,
                percentage=Decimal(str(round(percentage, 2))),
                cumulative_percentage=Decimal(str(round(cumulative_percentage, 2))),
                is_vital_few=is_vital_few,
            )
        )

    # Calculate vital few percentage
    vital_few_total = sum(item.count for item in items if item.is_vital_few)
    vital_few_percentage = Decimal(str((vital_few_total / total_defects) * 100)) if total_defects > 0 else Decimal("0")

    return ParetoResponse(
        client_id=client_id,
        time_range=time_range,
        start_date=start_date,
        end_date=end_date,
        items=items,
        total_defects=total_defects,
        vital_few_count=vital_few_count,
        vital_few_percentage=Decimal(str(round(vital_few_percentage, 2))),
        pareto_threshold=pareto_threshold,
    )
