"""
Data Completeness API Routes
Provides data entry completeness indicators for dashboard and data entry views
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date, datetime, timedelta

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.middleware.client_auth import build_client_filter_clause

router = APIRouter(prefix="/api/data-completeness", tags=["Data Completeness"])


def get_date_filter(target_date: date, model_date_column):
    """Create date filter for a specific date (handles both date and datetime columns)"""
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())
    return (model_date_column >= start_of_day, model_date_column <= end_of_day)


def calculate_expected_entries(
    db: Session, target_date: date, shift_id: Optional[int], client_id: Optional[str], entry_type: str
) -> int:
    """
    Calculate expected entries based on business rules.

    Expected counts are derived from:
    - Production: Active work orders with scheduled production for the date
    - Downtime: At least 1 entry per active work order (even if no downtime - 0 minutes)
    - Attendance: Number of employees scheduled for the shift
    - Quality: Number of work orders that reached inspection stage
    - Hold: Based on work orders that have material/quality issues

    For MVP, we use simplified estimates based on typical manufacturing patterns.
    """
    from backend.schemas.work_order import WorkOrder
    from backend.schemas.employee import Employee
    from backend.schemas.shift import Shift

    # Get active work orders for the date
    work_order_query = db.query(func.count(WorkOrder.work_order_id)).filter(
        WorkOrder.planned_start_date <= target_date,
        (WorkOrder.actual_delivery_date >= target_date) | (WorkOrder.actual_delivery_date.is_(None)),
        WorkOrder.status != "COMPLETED",
    )

    if client_id:
        work_order_query = work_order_query.filter(WorkOrder.client_id == client_id)

    active_work_orders = work_order_query.scalar() or 0

    if entry_type == "production":
        # Expect 1 production entry per active work order per shift
        shifts_per_day = 2 if shift_id is None else 1
        return max(active_work_orders * shifts_per_day, 5)  # Minimum 5 entries expected

    elif entry_type == "downtime":
        # Expect at least 1 downtime entry per active work order (can be 0 minutes)
        return max(active_work_orders, 3)  # Minimum 3 entries expected

    elif entry_type == "attendance":
        # Get scheduled employees count
        employee_query = db.query(func.count(Employee.employee_id)).filter(Employee.is_active == 1)
        if client_id:
            # Employee uses client_id_assigned which can be comma-separated
            employee_query = employee_query.filter(Employee.client_id_assigned.contains(client_id))

        scheduled_employees = employee_query.scalar() or 0
        return max(scheduled_employees, 10)  # Minimum 10 employees expected

    elif entry_type == "quality":
        # Expect quality entries for ~80% of active work orders (inspection sampling)
        return max(int(active_work_orders * 0.8), 2)  # Minimum 2 entries expected

    elif entry_type == "hold":
        # Holds are event-driven, expect ~10% of work orders to have holds
        return max(int(active_work_orders * 0.1), 1)  # Minimum 1 entry expected

    return 1


@router.get("")
def get_data_completeness(
    target_date: Optional[date] = Query(None, alias="date", description="Target date (default: today)"),
    shift_id: Optional[int] = Query(None, description="Shift ID filter"),
    client_id: Optional[str] = Query(None, description="Client ID filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get data completeness indicators for a specific date and shift.

    Returns completeness metrics for:
    - Production entries
    - Downtime entries
    - Attendance records
    - Quality inspections
    - WIP Hold/Resume records

    Response includes:
    - entered: Number of records entered
    - expected: Expected number of records based on active work orders and employees
    - percentage: Completeness percentage (0-100)
    - status: "complete" (>90%), "warning" (70-90%), "incomplete" (<70%)
    """
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.downtime_entry import DowntimeEntry
    from backend.schemas.attendance_entry import AttendanceEntry
    from backend.schemas.quality_entry import QualityEntry
    from backend.schemas.hold_entry import HoldEntry

    # Default to today if no date specified
    if target_date is None:
        target_date = date.today()

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Helper function to count entries
    def count_entries(model, date_column, extra_filters=None):
        date_start, date_end = get_date_filter(target_date, date_column)
        query = db.query(func.count()).filter(date_start, date_end)

        # Apply client filter if model has client_id
        if hasattr(model, "client_id") and effective_client_id:
            query = query.filter(model.client_id == effective_client_id)
        elif hasattr(model, "client_id"):
            client_filter = build_client_filter_clause(current_user, model.client_id)
            if client_filter is not None:
                query = query.filter(client_filter)

        # Apply shift filter if provided and model supports it
        if shift_id and hasattr(model, "shift_id"):
            query = query.filter(model.shift_id == shift_id)

        # Apply any extra filters
        if extra_filters:
            for f in extra_filters:
                query = query.filter(f)

        return query.scalar() or 0

    # Helper function to determine status
    def get_status(percentage: float) -> str:
        if percentage >= 90:
            return "complete"
        elif percentage >= 70:
            return "warning"
        return "incomplete"

    # Count entries for each category
    production_entered = count_entries(ProductionEntry, ProductionEntry.shift_date)
    production_expected = calculate_expected_entries(db, target_date, shift_id, effective_client_id, "production")
    production_pct = min((production_entered / production_expected * 100) if production_expected > 0 else 100, 100)

    downtime_entered = count_entries(DowntimeEntry, DowntimeEntry.shift_date)
    downtime_expected = calculate_expected_entries(db, target_date, shift_id, effective_client_id, "downtime")
    downtime_pct = min((downtime_entered / downtime_expected * 100) if downtime_expected > 0 else 100, 100)

    attendance_entered = count_entries(AttendanceEntry, AttendanceEntry.shift_date)
    attendance_expected = calculate_expected_entries(db, target_date, shift_id, effective_client_id, "attendance")
    attendance_pct = min((attendance_entered / attendance_expected * 100) if attendance_expected > 0 else 100, 100)

    quality_entered = count_entries(QualityEntry, QualityEntry.shift_date)
    quality_expected = calculate_expected_entries(db, target_date, shift_id, effective_client_id, "quality")
    quality_pct = min((quality_entered / quality_expected * 100) if quality_expected > 0 else 100, 100)

    hold_entered = count_entries(HoldEntry, HoldEntry.hold_date)
    hold_expected = calculate_expected_entries(db, target_date, shift_id, effective_client_id, "hold")
    hold_pct = min((hold_entered / hold_expected * 100) if hold_expected > 0 else 100, 100)

    # Calculate overall completeness (weighted average)
    # Production and Attendance are weighted higher as they're critical for KPIs
    weights = {"production": 0.30, "downtime": 0.15, "attendance": 0.30, "quality": 0.15, "hold": 0.10}

    overall_pct = (
        production_pct * weights["production"]
        + downtime_pct * weights["downtime"]
        + attendance_pct * weights["attendance"]
        + quality_pct * weights["quality"]
        + hold_pct * weights["hold"]
    )

    return {
        "date": target_date.isoformat(),
        "shift_id": shift_id,
        "client_id": effective_client_id,
        "production": {
            "entered": production_entered,
            "expected": production_expected,
            "percentage": round(production_pct, 1),
            "status": get_status(production_pct),
        },
        "downtime": {
            "entered": downtime_entered,
            "expected": downtime_expected,
            "percentage": round(downtime_pct, 1),
            "status": get_status(downtime_pct),
        },
        "attendance": {
            "entered": attendance_entered,
            "expected": attendance_expected,
            "percentage": round(attendance_pct, 1),
            "status": get_status(attendance_pct),
        },
        "quality": {
            "entered": quality_entered,
            "expected": quality_expected,
            "percentage": round(quality_pct, 1),
            "status": get_status(quality_pct),
        },
        "hold": {
            "entered": hold_entered,
            "expected": hold_expected,
            "percentage": round(hold_pct, 1),
            "status": get_status(hold_pct),
        },
        "overall": {"percentage": round(overall_pct, 1), "status": get_status(overall_pct)},
        "calculation_timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/summary")
def get_completeness_summary(
    start_date: Optional[date] = Query(None, description="Start date (default: 7 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (default: today)"),
    client_id: Optional[str] = Query(None, description="Client ID filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get data completeness summary for a date range.

    Returns daily completeness percentages for trend visualization.
    """
    # Default date range: last 7 days
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=7)

    # Get completeness for each day
    daily_completeness = []
    current_date = start_date

    while current_date <= end_date:
        # Get completeness for this day (simplified - just overall percentage)
        completeness = get_data_completeness(
            target_date=current_date, shift_id=None, client_id=client_id, db=db, current_user=current_user
        )

        daily_completeness.append(
            {
                "date": current_date.isoformat(),
                "overall_percentage": completeness["overall"]["percentage"],
                "status": completeness["overall"]["status"],
                "production": completeness["production"]["percentage"],
                "downtime": completeness["downtime"]["percentage"],
                "attendance": completeness["attendance"]["percentage"],
                "quality": completeness["quality"]["percentage"],
            }
        )

        current_date += timedelta(days=1)

    # Calculate average completeness
    avg_overall = (
        sum(d["overall_percentage"] for d in daily_completeness) / len(daily_completeness) if daily_completeness else 0
    )

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "average_completeness": round(avg_overall, 1),
        "daily": daily_completeness,
        "calculation_timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/categories")
def get_completeness_by_category(
    target_date: Optional[date] = Query(None, alias="date", description="Target date (default: today)"),
    client_id: Optional[str] = Query(None, description="Client ID filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed completeness breakdown by category.

    Returns actionable insights for each category showing what's missing.
    """
    # Default to today
    if target_date is None:
        target_date = date.today()

    # Get base completeness
    completeness = get_data_completeness(
        target_date=target_date, shift_id=None, client_id=client_id, db=db, current_user=current_user
    )

    # Build category details with navigation hints
    categories = [
        {
            "id": "production",
            "name": "Production",
            "icon": "mdi-factory",
            "color": "primary",
            "route": "/entry/production",
            **completeness["production"],
        },
        {
            "id": "downtime",
            "name": "Downtime",
            "icon": "mdi-clock-alert",
            "color": "warning",
            "route": "/entry/downtime",
            **completeness["downtime"],
        },
        {
            "id": "attendance",
            "name": "Attendance",
            "icon": "mdi-account-check",
            "color": "info",
            "route": "/entry/attendance",
            **completeness["attendance"],
        },
        {
            "id": "quality",
            "name": "Quality",
            "icon": "mdi-check-decagram",
            "color": "success",
            "route": "/entry/quality",
            **completeness["quality"],
        },
        {
            "id": "hold",
            "name": "Hold/Resume",
            "icon": "mdi-pause-circle",
            "color": "error",
            "route": "/entry/hold",
            **completeness["hold"],
        },
    ]

    return {
        "date": target_date.isoformat(),
        "overall": completeness["overall"],
        "categories": categories,
        "calculation_timestamp": datetime.utcnow().isoformat(),
    }
