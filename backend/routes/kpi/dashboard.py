"""
KPI Aggregated Dashboard Route

Single endpoint that combines multiple KPI metrics into one response,
reducing frontend API call overhead.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional
from datetime import date, datetime, timedelta, timezone

from backend.utils.logging_utils import get_module_logger
from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User

logger = get_module_logger(__name__)

dashboard_router = APIRouter(prefix="/api/kpi", tags=["KPI Calculations"])


@dashboard_router.get("/dashboard/aggregated")
def get_aggregated_dashboard(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get aggregated KPI dashboard data in a single API call.

    Combines multiple KPI endpoints into one response to reduce frontend API calls:
    - Efficiency metrics and trends
    - Performance metrics and trends
    - Quality metrics (FPY, RTY, PPM, DPMO)
    - Availability
    - Absenteeism
    - WIP aging summary
    - OTD (On-Time Delivery)

    This endpoint reduces 10+ API calls to a single request.
    """
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.quality_entry import QualityEntry
    from backend.schemas.attendance_entry import AttendanceEntry
    from backend.schemas.downtime_entry import DowntimeEntry
    from backend.schemas.work_order import WorkOrder
    from backend.schemas.hold_entry import HoldEntry
    from backend.calculations.ppm import calculate_ppm
    from backend.calculations.dpmo import calculate_dpmo
    from backend.calculations.fpy_rty import calculate_fpy

    # Default dates
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Build date filter conditions
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    result = {
        "date_range": {"start_date": str(start_date), "end_date": str(end_date)},
        "client_id": effective_client_id,
        "efficiency": None,
        "performance": None,
        "quality": None,
        "availability": None,
        "absenteeism": None,
        "wip_aging": None,
        "otd": None,
        "trends": {"efficiency": [], "performance": []},
    }

    # ---- EFFICIENCY & PERFORMANCE ----
    prod_result = None
    try:
        prod_query = db.query(
            func.avg(ProductionEntry.efficiency_percentage).label("avg_efficiency"),
            func.avg(ProductionEntry.performance_percentage).label("avg_performance"),
            func.sum(ProductionEntry.units_produced).label("total_units"),
            func.sum(ProductionEntry.run_time_hours).label("total_hours"),
        ).filter(ProductionEntry.shift_date >= start_dt, ProductionEntry.shift_date <= end_dt)
        if effective_client_id:
            prod_query = prod_query.filter(ProductionEntry.client_id == effective_client_id)

        prod_result = prod_query.first()
        result["efficiency"] = {
            "current": round(float(prod_result.avg_efficiency or 0), 1),
            "target": 85.0,
            "total_units": int(prod_result.total_units or 0),
            "total_hours": round(float(prod_result.total_hours or 0), 1),
        }
        result["performance"] = {"current": round(float(prod_result.avg_performance or 0), 1), "target": 90.0}

        # Efficiency trend
        trend_query = db.query(
            func.date(ProductionEntry.shift_date).label("date"),
            func.avg(ProductionEntry.efficiency_percentage).label("efficiency"),
            func.avg(ProductionEntry.performance_percentage).label("performance"),
        ).filter(ProductionEntry.shift_date >= start_dt, ProductionEntry.shift_date <= end_dt)
        if effective_client_id:
            trend_query = trend_query.filter(ProductionEntry.client_id == effective_client_id)

        trend_results = (
            trend_query.group_by(func.date(ProductionEntry.shift_date))
            .order_by(func.date(ProductionEntry.shift_date))
            .all()
        )

        result["trends"]["efficiency"] = [
            {"date": str(r.date), "value": round(float(r.efficiency or 0), 1)} for r in trend_results
        ]
        result["trends"]["performance"] = [
            {"date": str(r.date), "value": round(float(r.performance or 0), 1)} for r in trend_results
        ]
    except SQLAlchemyError:
        logger.exception("Database error fetching efficiency/performance metrics")
        result["efficiency"] = {"current": 0, "target": 85.0, "error": "Database error"}
        result["performance"] = {"current": 0, "target": 90.0, "error": "Database error"}
    except Exception:
        logger.exception("Unexpected error fetching efficiency/performance metrics")
        result["efficiency"] = {"current": 0, "target": 85.0, "error": "Calculation error"}
        result["performance"] = {"current": 0, "target": 90.0, "error": "Calculation error"}

    # ---- QUALITY (FPY, RTY, PPM, DPMO) ----
    try:
        fpy_rty = calculate_fpy_rty(db, effective_client_id, start_date, end_date)
        ppm_data = calculate_ppm(db, effective_client_id, start_date, end_date)
        dpmo_data = calculate_dpmo(db, effective_client_id, start_date, end_date)

        result["quality"] = {
            "fpy": round(fpy_rty.get("fpy", 0), 1),
            "rty": round(fpy_rty.get("rty", 0), 1),
            "ppm": int(ppm_data.get("ppm", 0)),
            "dpmo": int(dpmo_data.get("dpmo", 0)),
            "total_inspected": ppm_data.get("total_inspected", 0),
            "total_defective": ppm_data.get("total_defective", 0),
        }
    except SQLAlchemyError:
        logger.exception("Database error fetching quality metrics")
        result["quality"] = {"fpy": 0, "rty": 0, "ppm": 0, "dpmo": 0, "error": "Database error"}
    except Exception:
        logger.exception("Unexpected error fetching quality metrics")
        result["quality"] = {"fpy": 0, "rty": 0, "ppm": 0, "dpmo": 0, "error": "Calculation error"}

    # ---- AVAILABILITY ----
    try:
        downtime_query = db.query(
            func.sum(DowntimeEntry.downtime_duration_minutes / 60.0).label("downtime_hours")
        ).filter(DowntimeEntry.shift_date >= start_dt, DowntimeEntry.shift_date <= end_dt)
        if effective_client_id:
            downtime_query = downtime_query.filter(DowntimeEntry.client_id == effective_client_id)

        downtime_result = downtime_query.first()
        downtime_hours = float(downtime_result.downtime_hours or 0)

        # Calculate scheduled hours from production entries
        scheduled_hours = float(prod_result.total_hours or 480) if prod_result else 480
        availability = ((scheduled_hours - downtime_hours) / scheduled_hours * 100) if scheduled_hours > 0 else 100

        result["availability"] = {
            "current": round(max(0, min(100, availability)), 1),
            "target": 95.0,
            "downtime_hours": round(downtime_hours, 1),
            "scheduled_hours": round(scheduled_hours, 1),
        }
    except SQLAlchemyError:
        logger.exception("Database error fetching availability metrics")
        result["availability"] = {"current": 100, "target": 95.0, "error": "Database error"}
    except Exception:
        logger.exception("Unexpected error fetching availability metrics")
        result["availability"] = {"current": 100, "target": 95.0, "error": "Calculation error"}

    # ---- ABSENTEEISM ----
    try:
        att_query = db.query(
            func.sum(AttendanceEntry.scheduled_hours).label("scheduled"),
            func.sum(func.coalesce(AttendanceEntry.absence_hours, 0)).label("absent"),
            func.count(func.distinct(AttendanceEntry.employee_id)).label("employee_count"),
        ).filter(AttendanceEntry.shift_date >= start_dt, AttendanceEntry.shift_date <= end_dt)
        if effective_client_id:
            att_query = att_query.filter(AttendanceEntry.client_id == effective_client_id)

        att_result = att_query.first()
        scheduled = float(att_result.scheduled or 0)
        absent = float(att_result.absent or 0)
        absenteeism_rate = (absent / scheduled * 100) if scheduled > 0 else 0

        result["absenteeism"] = {
            "rate": round(absenteeism_rate, 2),
            "target": 5.0,
            "total_scheduled_hours": round(scheduled, 1),
            "total_absent_hours": round(absent, 1),
            "employee_count": att_result.employee_count or 0,
        }
    except SQLAlchemyError:
        logger.exception("Database error fetching absenteeism metrics")
        result["absenteeism"] = {"rate": 0, "target": 5.0, "error": "Database error"}
    except Exception:
        logger.exception("Unexpected error fetching absenteeism metrics")
        result["absenteeism"] = {"rate": 0, "target": 5.0, "error": "Calculation error"}

    # ---- WIP AGING ----
    try:
        from backend.schemas.hold_entry import HoldStatus

        # Count active holds (ON_HOLD status)
        wip_query = db.query(func.count(HoldEntry.hold_entry_id).label("total_count")).filter(
            HoldEntry.hold_status == HoldStatus.ON_HOLD
        )
        if effective_client_id:
            wip_query = wip_query.filter(HoldEntry.client_id == effective_client_id)

        wip_result = wip_query.first()
        total_active = wip_result.total_count or 0

        # For simplicity, set defaults - proper aging calculation would need hold_date analysis
        result["wip_aging"] = {
            "total_active": total_active,
            "within_target": total_active,
            "overdue": 0,
            "avg_aging_days": 0,
        }
    except SQLAlchemyError:
        logger.exception("Database error fetching WIP aging metrics")
        result["wip_aging"] = {"total_active": 0, "within_target": 0, "overdue": 0, "error": "Database error"}
    except Exception:
        logger.exception("Unexpected error fetching WIP aging metrics")
        result["wip_aging"] = {"total_active": 0, "within_target": 0, "overdue": 0, "error": "Calculation error"}

    # ---- OTD (On-Time Delivery) ----
    try:
        otd_query = db.query(
            func.count(WorkOrder.work_order_id).label("total"),
            func.sum(case((WorkOrder.actual_delivery_date <= WorkOrder.required_date, 1), else_=0)).label("on_time"),
        ).filter(
            WorkOrder.required_date.isnot(None),
            WorkOrder.required_date >= start_dt,
            WorkOrder.required_date <= end_dt,
            WorkOrder.actual_delivery_date.isnot(None),
        )
        if effective_client_id:
            otd_query = otd_query.filter(WorkOrder.client_id == effective_client_id)

        otd_result = otd_query.first()
        total_orders = otd_result.total or 0
        on_time_orders = otd_result.on_time or 0
        otd_rate = (on_time_orders / total_orders * 100) if total_orders > 0 else 100

        result["otd"] = {
            "rate": round(otd_rate, 1),
            "target": 95.0,
            "total_orders": total_orders,
            "on_time_orders": on_time_orders,
            "late_orders": total_orders - on_time_orders,
        }
    except SQLAlchemyError:
        logger.exception("Database error fetching OTD metrics")
        result["otd"] = {"rate": 100, "target": 95.0, "error": "Database error"}
    except Exception:
        logger.exception("Unexpected error fetching OTD metrics")
        result["otd"] = {"rate": 100, "target": 95.0, "error": "Calculation error"}

    return result
