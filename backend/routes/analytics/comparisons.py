"""
Analytics - Comparisons, Heatmap, and Pareto Endpoints

Covers:
- GET /api/analytics/comparisons — client-to-client benchmarking
- GET /api/analytics/heatmap    — performance heatmap (date x shift)
- GET /api/analytics/pareto     — defect Pareto analysis (80/20 rule)
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
    ComparisonResponse,
    ClientComparisonData,
    HeatmapResponse,
    HeatmapCell,
    ParetoResponse,
    ParetoItem,
    KPIType,
)
from backend.crud.analytics import (
    get_shift_heatmap_data,
    get_client_comparison_data,
    get_defect_pareto_data,
    get_all_shifts,
)
from backend.utils.logging_utils import get_module_logger
from ._helpers import parse_time_range, get_performance_rating, get_heatmap_color_code

logger = get_module_logger(__name__)

comparisons_router = APIRouter()


@comparisons_router.get(
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
    time_range: str = Query("30d", pattern="^(7d|30d|90d)$", description="Time range (7d, 30d, 90d)"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ComparisonResponse:
    """
    GET /api/analytics/comparisons - Client-to-client KPI benchmarking
    """
    if start_date and end_date:
        pass
    else:
        start_date, end_date = parse_time_range(time_range, end_date)

    comparison_data = get_client_comparison_data(db, kpi_type.value, start_date, end_date, current_user)

    if not comparison_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {kpi_type.value} data found for any accessible clients in specified date range",
        )

    all_values = [avg_value for _, _, avg_value, _ in comparison_data]
    overall_avg = sum(all_values) / len(all_values)

    industry_benchmark = Decimal("85.0")
    sorted_values = sorted(all_values)

    clients = []
    for client_id, client_name, avg_value, data_points in comparison_data:
        rank_position = sorted_values.index(avg_value)
        percentile_rank = int((rank_position / (len(sorted_values) - 1)) * 100) if len(sorted_values) > 1 else 50

        above_benchmark = avg_value >= industry_benchmark
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

    best_performer = comparison_data[0][0]
    worst_performer = comparison_data[-1][0]
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


@comparisons_router.get(
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
    time_range: str = Query("30d", pattern="^(7d|30d|90d)$", description="Time range (7d, 30d, 90d)"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HeatmapResponse:
    """
    GET /api/analytics/heatmap - Performance heatmap by shift and date
    """
    verify_client_access(current_user, client_id)

    if start_date and end_date:
        pass
    else:
        start_date, end_date = parse_time_range(time_range, end_date)

    heatmap_data = get_shift_heatmap_data(db, client_id, kpi_type.value, start_date, end_date, current_user)

    all_shifts = get_all_shifts(db)
    shift_names = [name for _, name in all_shifts]

    all_dates = []
    current_date = start_date
    while current_date <= end_date:
        all_dates.append(current_date)
        current_date += timedelta(days=1)

    data_lookup = {(d, shift_id): (shift_name, value) for d, shift_id, shift_name, value in heatmap_data}

    cells = []
    benchmark = Decimal("85.0")

    for current_date in all_dates:
        for shift_id, shift_name in all_shifts:
            key = (current_date, shift_id)
            if key in data_lookup:
                _, value = data_lookup[key]
            else:
                value = None

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


@comparisons_router.get(
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
    time_range: str = Query("30d", pattern="^(7d|30d|90d)$", description="Time range (7d, 30d, 90d)"),
    start_date: Optional[date] = Query(None, description="Custom start date"),
    end_date: Optional[date] = Query(None, description="Custom end date"),
    pareto_threshold: Decimal = Query(Decimal("80.0"), ge=50, le=95, description="Pareto threshold percentage"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ParetoResponse:
    """
    GET /api/analytics/pareto - Defect Pareto analysis (80/20 rule)
    """
    verify_client_access(current_user, client_id)

    if start_date and end_date:
        pass
    else:
        start_date, end_date = parse_time_range(time_range, end_date)

    defect_data = get_defect_pareto_data(db, client_id, start_date, end_date, current_user)

    if not defect_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No defect data found for client {client_id} in specified date range",
        )

    total_defects = sum(count for _, count in defect_data)

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

    vital_few_total = sum(item.count for item in items if item.is_vital_few)
    vital_few_percentage = (
        Decimal(str((vital_few_total / total_defects) * 100)) if total_defects > 0 else Decimal("0")
    )

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
