"""
My Shift Routes
Provides personalized shift summary data for line operators
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict

from backend.database import get_db
from backend.orm.production_entry import ProductionEntry
from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.quality_entry import QualityEntry
from backend.orm.work_order import WorkOrder
from backend.auth.jwt import get_current_user, ClientScope, resolve_client_scope
from backend.orm.user import User
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

    model_config = ConfigDict(from_attributes=True)


class WorkOrderProgress(BaseModel):
    """Progress on a specific work order"""

    id: int
    work_order_id: str
    product_name: str
    target_qty: int
    produced: int
    progress_percent: float

    model_config = ConfigDict(from_attributes=True)


class ActivityEntry(BaseModel):
    """A single activity log entry"""

    id: str
    type: str  # production, downtime, quality
    description: str
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class MyShiftSummary(BaseModel):
    """Complete shift summary response"""

    date: date
    shift_id: Optional[int]
    operator_id: Optional[str]
    stats: ShiftStats
    assigned_work_orders: List[WorkOrderProgress]
    recent_activity: List[ActivityEntry]
    data_completeness: dict

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/summary", response_model=MyShiftSummary)
def get_my_shift_summary(
    shift_date: Optional[date] = Query(None, description="Date for shift summary"),
    shift_id: Optional[int] = Query(None, description="Shift ID (FK to SHIFT.shift_id)"),
    operator_id: Optional[str] = Query(None, description="Operator employee ID (currently advisory only)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> Any:
    """
    Get personalized shift summary for an operator.

    Returns:
    - Statistics for units produced, efficiency, downtime, quality
    - List of assigned work orders with progress
    - Recent activity entries
    - Data completeness indicators

    Notes:
    - `shift_id` filters PRODUCTION_ENTRY by `shift_id` foreign key. The
      DOWNTIME_ENTRY and QUALITY_ENTRY tables don't carry a shift FK in
      the current schema; their results are date-scoped only.
    - `operator_id` is accepted for forward-compatibility but currently
      ignored — PRODUCTION_ENTRY tracks the entering user (`entered_by`)
      not the operator. Wire up via EMPLOYEE_LINE_ASSIGNMENT when needed.
    """
    target_date = shift_date or date.today()

    # Production entries — scoped by shift_date and (optionally) shift_id.
    production_query = db.query(ProductionEntry).filter(func.date(ProductionEntry.shift_date) == target_date)
    # Multi-tenant isolation: client-scope authorization
    production_query = production_query.filter(scope.filter(ProductionEntry.client_id))
    if shift_id is not None:
        production_query = production_query.filter(ProductionEntry.shift_id == shift_id)

    productions = production_query.all()

    # Calculate production stats. Target falls back to actual when not
    # tracked; ideal_cycle_time × run_time would give a more accurate
    # target but the current schema doesn't carry a hard target field.
    total_units = sum(p.units_produced or 0 for p in productions)
    total_target = total_units or 1  # avoid div-by-zero in efficiency
    cached_efficiency = [float(p.efficiency_percentage) for p in productions if p.efficiency_percentage is not None]
    if cached_efficiency:
        efficiency = sum(cached_efficiency) / len(cached_efficiency)
    else:
        efficiency = (total_units / total_target * 100) if total_target > 0 else 0

    # Downtime entries — scoped by shift_date.
    downtime_query = db.query(DowntimeEntry).filter(func.date(DowntimeEntry.shift_date) == target_date)
    downtime_query = downtime_query.filter(scope.filter(DowntimeEntry.client_id))

    downtimes = downtime_query.all()
    downtime_incidents = len(downtimes)
    downtime_minutes = sum(d.downtime_duration_minutes or 0 for d in downtimes)

    # Quality entries — scoped by shift_date.
    quality_query = db.query(QualityEntry).filter(func.date(QualityEntry.shift_date) == target_date)
    quality_query = quality_query.filter(scope.filter(QualityEntry.client_id))

    qualities = quality_query.all()
    quality_checks = len(qualities)
    defect_count = sum(q.units_defective or 0 for q in qualities)

    stats = ShiftStats(
        units_produced=total_units,
        efficiency=round(efficiency, 1),
        downtime_incidents=downtime_incidents,
        downtime_minutes=downtime_minutes,
        quality_checks=quality_checks,
        defect_count=defect_count,
    )

    # Work orders active in today's shift, shown with their OVERALL completion
    # (cumulative produced vs the order's planned quantity). A today-only tally
    # (produced/produced) always read 0% or 100%; cumulative-vs-planned gives a
    # real progress bar (e.g. an in-progress order at ~50%).
    work_order_stats: Dict[str, Dict[str, Any]] = {}
    for p in productions:
        wo_id = p.work_order_id
        if not wo_id:
            continue
        if wo_id not in work_order_stats:
            product_name = "Unknown"
            if getattr(p, "product", None) is not None:
                product_name = getattr(p.product, "product_name", None) or "Unknown"
            work_order_stats[wo_id] = {"product_name": product_name}

    assigned_work_orders: List[WorkOrderProgress] = []
    if work_order_stats:
        wo_ids = list(work_order_stats.keys())
        cumulative: Dict[str, int] = {
            str(row[0]): int(row[1] or 0)
            for row in db.query(
                ProductionEntry.work_order_id,
                func.coalesce(func.sum(ProductionEntry.units_produced), 0),
            )
            .filter(ProductionEntry.work_order_id.in_(wo_ids))
            .group_by(ProductionEntry.work_order_id)
            .all()
        }
        planned = {
            w.work_order_id: int(w.planned_quantity or 0)
            for w in db.query(WorkOrder).filter(WorkOrder.work_order_id.in_(wo_ids)).all()
        }
        for i, (wo_id, wo_data) in enumerate(work_order_stats.items(), 1):
            produced = int(cumulative.get(wo_id, 0) or 0)
            # Prefer the order's planned quantity as the target; fall back to
            # produced so progress never divides by zero.
            target_qty = planned.get(wo_id) or produced or 1
            progress = (produced / target_qty * 100) if target_qty > 0 else 0
            assigned_work_orders.append(
                WorkOrderProgress(
                    id=i,
                    work_order_id=wo_id,
                    product_name=wo_data["product_name"],
                    target_qty=target_qty,
                    produced=produced,
                    progress_percent=round(min(progress, 100), 1),
                )
            )

    # Recent activity (top 5, mixed types).
    activities: List[ActivityEntry] = []

    for p in productions[:5]:
        activities.append(
            ActivityEntry(
                id=f"prod-{p.production_entry_id}",
                type="production",
                description=f"Logged {p.units_produced} units for {p.work_order_id or '—'}",
                timestamp=p.created_at or p.shift_date,
            )
        )

    for d in downtimes[:3]:
        activities.append(
            ActivityEntry(
                id=f"down-{d.downtime_entry_id}",
                type="downtime",
                description=f"{d.downtime_reason}: {d.downtime_duration_minutes} min downtime",
                timestamp=d.created_at or d.shift_date,
            )
        )

    for q in qualities[:2]:
        activities.append(
            ActivityEntry(
                id=f"qual-{q.quality_entry_id}",
                type="quality",
                description=f"Quality check: {q.units_inspected} inspected, {q.units_defective} defects",
                timestamp=q.created_at or q.shift_date,
            )
        )

    activities.sort(key=lambda x: x.timestamp, reverse=True)
    activities = activities[:5]

    # Data completeness — light heuristic for the widget.
    expected_production = 8
    expected_quality = 2
    prod_pct = min(round(len(productions) / expected_production * 100), 100)
    qual_pct = min(round(quality_checks / expected_quality * 100), 100)
    overall_pct = round((prod_pct + 100 + qual_pct) / 3)

    data_completeness: Dict[str, Dict[str, Any]] = {
        "production": {
            "entered": len(productions),
            "expected": expected_production,
            "percentage": prod_pct,
            "status": (
                "complete"
                if len(productions) >= expected_production
                else "warning" if len(productions) >= expected_production * 0.5 else "incomplete"
            ),
        },
        "downtime": {
            "entered": downtime_incidents,
            "expected": downtime_incidents,
            "percentage": 100,
            "status": "complete",
        },
        "quality": {
            "entered": quality_checks,
            "expected": expected_quality,
            "percentage": qual_pct,
            "status": (
                "complete" if quality_checks >= expected_quality else "warning" if quality_checks >= 1 else "incomplete"
            ),
        },
        "overall": {
            "percentage": overall_pct,
            "status": "complete" if overall_pct >= 90 else "warning" if overall_pct >= 60 else "incomplete",
        },
    }

    return MyShiftSummary(
        date=target_date,
        shift_id=shift_id,
        operator_id=operator_id,
        stats=stats,
        assigned_work_orders=assigned_work_orders,
        recent_activity=activities,
        data_completeness=data_completeness,
    )


@router.get("/stats")
def get_my_shift_stats(
    shift_date: Optional[date] = Query(None),
    shift_id: Optional[int] = Query(None, description="SHIFT.shift_id FK"),
    operator_id: Optional[str] = Query(None),  # advisory; see /summary docstring
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> Any:
    """
    Get just the statistics portion of shift summary.
    Lightweight endpoint for dashboard widgets.
    """
    target_date = shift_date or date.today()

    production_query = db.query(
        func.sum(ProductionEntry.units_produced).label("total_units"),
        func.count(ProductionEntry.production_entry_id).label("entry_count"),
    ).filter(func.date(ProductionEntry.shift_date) == target_date)
    production_query = production_query.filter(scope.filter(ProductionEntry.client_id))
    if shift_id is not None:
        production_query = production_query.filter(ProductionEntry.shift_id == shift_id)

    prod_result = production_query.first()

    downtime_query = db.query(
        func.count(DowntimeEntry.downtime_entry_id).label("incidents"),
        func.sum(DowntimeEntry.downtime_duration_minutes).label("total_minutes"),
    ).filter(func.date(DowntimeEntry.shift_date) == target_date)
    downtime_query = downtime_query.filter(scope.filter(DowntimeEntry.client_id))

    down_result = downtime_query.first()

    quality_query = db.query(
        func.count(QualityEntry.quality_entry_id).label("checks"),
        func.sum(QualityEntry.units_defective).label("defects"),
    ).filter(func.date(QualityEntry.shift_date) == target_date)
    quality_query = quality_query.filter(scope.filter(QualityEntry.client_id))

    qual_result = quality_query.first()

    total_units = (prod_result.total_units or 0) if prod_result else 0
    total_target = total_units or 1
    efficiency = (total_units / total_target * 100) if total_target > 0 else 0

    return {
        "date": target_date.isoformat(),
        "shift_id": shift_id,
        "units_produced": total_units,
        "efficiency": round(efficiency, 1),
        "downtime_incidents": (down_result.incidents or 0) if down_result else 0,
        "downtime_minutes": (down_result.total_minutes or 0) if down_result else 0,
        "quality_checks": (qual_result.checks or 0) if qual_result else 0,
        "defect_count": (qual_result.defects or 0) if qual_result else 0,
    }


@router.get("/activity")
def get_my_recent_activity(
    shift_date: Optional[date] = Query(None),
    shift_id: Optional[int] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> Any:
    """
    Get recent activity entries for the shift.
    Returns production, downtime, and quality entries combined.
    """
    target_date = shift_date or date.today()
    activities: List[Dict[str, Any]] = []

    production_query = db.query(ProductionEntry).filter(func.date(ProductionEntry.shift_date) == target_date)
    production_query = production_query.filter(scope.filter(ProductionEntry.client_id))
    if shift_id is not None:
        production_query = production_query.filter(ProductionEntry.shift_id == shift_id)

    for p in production_query.order_by(ProductionEntry.created_at.desc()).limit(limit):
        ts = (p.created_at or p.shift_date).isoformat()
        activities.append(
            {
                "id": f"prod-{p.production_entry_id}",
                "type": "production",
                "description": f"Logged {p.units_produced} units for {p.work_order_id or '—'}",
                "timestamp": ts,
                "work_order_id": p.work_order_id,
                "value": p.units_produced,
            }
        )

    downtime_query = db.query(DowntimeEntry).filter(func.date(DowntimeEntry.shift_date) == target_date)
    downtime_query = downtime_query.filter(scope.filter(DowntimeEntry.client_id))

    for d in downtime_query.order_by(DowntimeEntry.created_at.desc()).limit(limit):
        ts = (d.created_at or d.shift_date).isoformat()
        activities.append(
            {
                "id": f"down-{d.downtime_entry_id}",
                "type": "downtime",
                "description": f"{d.downtime_reason}: {d.downtime_duration_minutes} min downtime",
                "timestamp": ts,
                "work_order_id": d.work_order_id,
                "value": d.downtime_duration_minutes,
            }
        )

    quality_query = db.query(QualityEntry).filter(func.date(QualityEntry.shift_date) == target_date)
    quality_query = quality_query.filter(scope.filter(QualityEntry.client_id))

    for q in quality_query.order_by(QualityEntry.created_at.desc()).limit(limit):
        ts = (q.created_at or q.shift_date).isoformat()
        activities.append(
            {
                "id": f"qual-{q.quality_entry_id}",
                "type": "quality",
                "description": f"Quality check: {q.units_inspected} inspected, {q.units_defective} defects",
                "timestamp": ts,
                "work_order_id": q.work_order_id,
                "value": q.units_inspected,
            }
        )

    activities.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)

    return {"date": target_date.isoformat(), "shift_id": shift_id, "activity": activities[:limit]}
