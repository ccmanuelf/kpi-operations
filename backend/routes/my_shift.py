"""
My Shift Routes
Provides personalized shift summary data for line operators
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel

from backend.database import get_db
from backend.schemas.production_entry import ProductionEntry
from backend.schemas.downtime_entry import DowntimeEntry
from backend.schemas.quality_entry import QualityEntry
from backend.schemas.attendance_entry import AttendanceEntry
from backend.schemas.work_order import WorkOrder
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/my-shift", tags=["my-shift"])


# =============================================================================
# Response Models
# =============================================================================


class ShiftStats(BaseModel):
    """Statistics for the operator's current shift"""

    units_produced: int
    efficiency: float
    downtime_incidents: int
    downtime_minutes: int
    quality_checks: int
    defect_count: int

    class Config:
        from_attributes = True


class WorkOrderProgress(BaseModel):
    """Progress on a specific work order"""

    id: int
    work_order_id: str
    product_name: str
    target_qty: int
    produced: int
    progress_percent: float

    class Config:
        from_attributes = True


class ActivityEntry(BaseModel):
    """A single activity log entry"""

    id: str
    type: str  # production, downtime, quality, hold
    description: str
    timestamp: datetime

    class Config:
        from_attributes = True


class MyShiftSummary(BaseModel):
    """Complete shift summary response"""

    date: date
    shift_number: Optional[int]
    operator_id: Optional[str]
    stats: ShiftStats
    assigned_work_orders: List[WorkOrderProgress]
    recent_activity: List[ActivityEntry]
    data_completeness: dict

    class Config:
        from_attributes = True


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/summary", response_model=MyShiftSummary)
def get_my_shift_summary(
    shift_date: Optional[date] = Query(None, description="Date for shift summary"),
    shift_number: Optional[int] = Query(None, ge=1, le=3, description="Shift number (1-3)"),
    operator_id: Optional[str] = Query(None, description="Operator employee ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get personalized shift summary for an operator.

    Returns:
    - Statistics for units produced, efficiency, downtime, quality
    - List of assigned work orders with progress
    - Recent activity entries
    - Data completeness indicators
    """
    # Default to today if not specified
    target_date = shift_date or date.today()

    # Query production entries for this shift
    production_query = db.query(ProductionEntry).filter(func.date(ProductionEntry.date) == target_date)
    if shift_number:
        production_query = production_query.filter(ProductionEntry.shift == shift_number)
    if operator_id:
        production_query = production_query.filter(ProductionEntry.operator_id == operator_id)

    productions = production_query.all()

    # Calculate production stats
    total_units = sum(p.units_produced or 0 for p in productions)
    total_target = sum(p.target_production or p.units_produced or 0 for p in productions)
    efficiency = (total_units / total_target * 100) if total_target > 0 else 0

    # Query downtime entries
    downtime_query = db.query(DowntimeEntry).filter(func.date(DowntimeEntry.date) == target_date)
    if shift_number:
        downtime_query = downtime_query.filter(DowntimeEntry.shift == shift_number)

    downtimes = downtime_query.all()
    downtime_incidents = len(downtimes)
    downtime_minutes = sum(d.downtime_minutes or 0 for d in downtimes)

    # Query quality entries
    quality_query = db.query(QualityEntry).filter(func.date(QualityEntry.date) == target_date)
    if shift_number:
        quality_query = quality_query.filter(QualityEntry.shift == shift_number)

    qualities = quality_query.all()
    quality_checks = len(qualities)
    defect_count = sum(q.defect_quantity or 0 for q in qualities)

    # Build stats
    stats = ShiftStats(
        units_produced=total_units,
        efficiency=round(efficiency, 1),
        downtime_incidents=downtime_incidents,
        downtime_minutes=downtime_minutes,
        quality_checks=quality_checks,
        defect_count=defect_count,
    )

    # Get work orders with progress
    # Group production entries by work order
    work_order_stats = {}
    for p in productions:
        wo_id = p.work_order_id
        if wo_id not in work_order_stats:
            work_order_stats[wo_id] = {"produced": 0, "target": 0, "product_name": p.product_name or "Unknown"}
        work_order_stats[wo_id]["produced"] += p.units_produced or 0
        work_order_stats[wo_id]["target"] += p.target_production or p.units_produced or 0

    # Build work order progress list
    assigned_work_orders = []
    for i, (wo_id, wo_data) in enumerate(work_order_stats.items(), 1):
        target_qty = wo_data["target"] or 1
        progress = (wo_data["produced"] / target_qty * 100) if target_qty > 0 else 0
        assigned_work_orders.append(
            WorkOrderProgress(
                id=i,
                work_order_id=wo_id,
                product_name=wo_data["product_name"],
                target_qty=target_qty,
                produced=wo_data["produced"],
                progress_percent=round(min(progress, 100), 1),
            )
        )

    # Build recent activity (last 10 entries)
    activities = []

    # Add production activities
    for p in productions[:5]:
        activities.append(
            ActivityEntry(
                id=f"prod-{p.id}",
                type="production",
                description=f"Logged {p.units_produced} units for {p.work_order_id}",
                timestamp=p.created_at or datetime.combine(p.date, datetime.min.time()),
            )
        )

    # Add downtime activities
    for d in downtimes[:3]:
        activities.append(
            ActivityEntry(
                id=f"down-{d.id}",
                type="downtime",
                description=f"{d.reason}: {d.downtime_minutes} min downtime",
                timestamp=d.created_at or datetime.combine(d.date, datetime.min.time()),
            )
        )

    # Add quality activities
    for q in qualities[:2]:
        activities.append(
            ActivityEntry(
                id=f"qual-{q.id}",
                type="quality",
                description=f"Quality check: {q.inspected_quantity} inspected, {q.defect_quantity} defects",
                timestamp=q.created_at or datetime.combine(q.date, datetime.min.time()),
            )
        )

    # Sort by timestamp descending
    activities.sort(key=lambda x: x.timestamp, reverse=True)
    activities = activities[:5]  # Take top 5

    # Calculate data completeness
    # Simple heuristic: check if entries exist for each category
    expected_production = 8  # Hourly entries for 8-hour shift
    expected_quality = 2  # At least 2 quality checks per shift

    data_completeness = {
        "production": {
            "entered": len(productions),
            "expected": expected_production,
            "percentage": min(round(len(productions) / expected_production * 100), 100),
            "status": (
                "complete"
                if len(productions) >= expected_production
                else "warning" if len(productions) >= expected_production * 0.5 else "incomplete"
            ),
        },
        "downtime": {
            "entered": downtime_incidents,
            "expected": downtime_incidents,  # Downtime is recorded as-needed
            "percentage": 100,
            "status": "complete",
        },
        "quality": {
            "entered": quality_checks,
            "expected": expected_quality,
            "percentage": min(round(quality_checks / expected_quality * 100), 100),
            "status": (
                "complete" if quality_checks >= expected_quality else "warning" if quality_checks >= 1 else "incomplete"
            ),
        },
        "overall": {
            "percentage": (
                round(
                    (
                        data_completeness.get("production", {}).get("percentage", 0)
                        + 100
                        + data_completeness.get("quality", {}).get("percentage", 0)
                    )
                    / 3
                )
                if "production" in data_completeness
                else 50
            ),
            "status": (
                "complete"
                if len(productions) >= expected_production and quality_checks >= expected_quality
                else "warning"
            ),
        },
    }

    # Recalculate overall
    prod_pct = min(round(len(productions) / expected_production * 100), 100)
    qual_pct = min(round(quality_checks / expected_quality * 100), 100)
    overall_pct = round((prod_pct + 100 + qual_pct) / 3)
    data_completeness["overall"] = {
        "percentage": overall_pct,
        "status": "complete" if overall_pct >= 90 else "warning" if overall_pct >= 60 else "incomplete",
    }

    return MyShiftSummary(
        date=target_date,
        shift_number=shift_number,
        operator_id=operator_id,
        stats=stats,
        assigned_work_orders=assigned_work_orders,
        recent_activity=activities,
        data_completeness=data_completeness,
    )


@router.get("/stats")
def get_my_shift_stats(
    shift_date: Optional[date] = Query(None),
    shift_number: Optional[int] = Query(None, ge=1, le=3),
    operator_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get just the statistics portion of shift summary.
    Lightweight endpoint for dashboard widgets.
    """
    target_date = shift_date or date.today()

    # Query production
    production_query = db.query(
        func.sum(ProductionEntry.units_produced).label("total_units"),
        func.sum(ProductionEntry.target_production).label("total_target"),
        func.count(ProductionEntry.id).label("entry_count"),
    ).filter(func.date(ProductionEntry.date) == target_date)
    if shift_number:
        production_query = production_query.filter(ProductionEntry.shift == shift_number)
    if operator_id:
        production_query = production_query.filter(ProductionEntry.operator_id == operator_id)

    prod_result = production_query.first()

    # Query downtime
    downtime_query = db.query(
        func.count(DowntimeEntry.id).label("incidents"), func.sum(DowntimeEntry.downtime_minutes).label("total_minutes")
    ).filter(func.date(DowntimeEntry.date) == target_date)
    if shift_number:
        downtime_query = downtime_query.filter(DowntimeEntry.shift == shift_number)

    down_result = downtime_query.first()

    # Query quality
    quality_query = db.query(
        func.count(QualityEntry.id).label("checks"), func.sum(QualityEntry.defect_quantity).label("defects")
    ).filter(func.date(QualityEntry.date) == target_date)
    if shift_number:
        quality_query = quality_query.filter(QualityEntry.shift == shift_number)

    qual_result = quality_query.first()

    # Calculate efficiency
    total_units = prod_result.total_units or 0
    total_target = prod_result.total_target or total_units or 1
    efficiency = (total_units / total_target * 100) if total_target > 0 else 0

    return {
        "date": target_date.isoformat(),
        "shift_number": shift_number,
        "units_produced": total_units,
        "efficiency": round(efficiency, 1),
        "downtime_incidents": down_result.incidents or 0,
        "downtime_minutes": down_result.total_minutes or 0,
        "quality_checks": qual_result.checks or 0,
        "defect_count": qual_result.defects or 0,
    }


@router.get("/activity")
def get_my_recent_activity(
    shift_date: Optional[date] = Query(None),
    shift_number: Optional[int] = Query(None, ge=1, le=3),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get recent activity entries for the shift.
    Returns production, downtime, and quality entries combined.
    """
    target_date = shift_date or date.today()

    activities = []

    # Query production entries
    production_query = db.query(ProductionEntry).filter(func.date(ProductionEntry.date) == target_date)
    if shift_number:
        production_query = production_query.filter(ProductionEntry.shift == shift_number)

    for p in production_query.order_by(ProductionEntry.created_at.desc()).limit(limit):
        activities.append(
            {
                "id": f"prod-{p.id}",
                "type": "production",
                "description": f"Logged {p.units_produced} units for {p.work_order_id}",
                "timestamp": (p.created_at or datetime.combine(p.date, datetime.min.time())).isoformat(),
                "work_order_id": p.work_order_id,
                "value": p.units_produced,
            }
        )

    # Query downtime entries
    downtime_query = db.query(DowntimeEntry).filter(func.date(DowntimeEntry.date) == target_date)
    if shift_number:
        downtime_query = downtime_query.filter(DowntimeEntry.shift == shift_number)

    for d in downtime_query.order_by(DowntimeEntry.created_at.desc()).limit(limit):
        activities.append(
            {
                "id": f"down-{d.id}",
                "type": "downtime",
                "description": f"{d.reason}: {d.downtime_minutes} min downtime",
                "timestamp": (d.created_at or datetime.combine(d.date, datetime.min.time())).isoformat(),
                "work_order_id": d.work_order_id,
                "value": d.downtime_minutes,
            }
        )

    # Query quality entries
    quality_query = db.query(QualityEntry).filter(func.date(QualityEntry.date) == target_date)
    if shift_number:
        quality_query = quality_query.filter(QualityEntry.shift == shift_number)

    for q in quality_query.order_by(QualityEntry.created_at.desc()).limit(limit):
        activities.append(
            {
                "id": f"qual-{q.id}",
                "type": "quality",
                "description": f"Quality check: {q.inspected_quantity} inspected, {q.defect_quantity} defects",
                "timestamp": (q.created_at or datetime.combine(q.date, datetime.min.time())).isoformat(),
                "work_order_id": q.work_order_id,
                "value": q.inspected_quantity,
            }
        )

    # Sort all activities by timestamp descending
    activities.sort(key=lambda x: x["timestamp"], reverse=True)

    return {"date": target_date.isoformat(), "shift_number": shift_number, "activity": activities[:limit]}
