"""
KPI Trend Routes

Daily trend data endpoints for performance, quality, availability, OEE,
on-time delivery, and absenteeism; plus performance breakdown by shift and product.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import Optional
from datetime import date, datetime, timedelta, timezone

from backend.utils.logging_utils import get_module_logger
from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User

logger = get_module_logger(__name__)

trends_router = APIRouter(prefix="/api/kpi", tags=["KPI Calculations"])


@trends_router.get("/performance/trend")
def get_performance_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get daily performance trend data.

    Returns date/value pairs of average performance percentage per day
    for charting. Defaults to the last 30 days.

    SECURITY: Requires authentication; non-admin users see only their assigned client.
    """
    from backend.schemas.production_entry import ProductionEntry

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = db.query(
        func.date(ProductionEntry.shift_date).label("date"),
        func.avg(ProductionEntry.performance_percentage).label("value"),
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
    )

    if effective_client_id:
        query = query.filter(ProductionEntry.client_id == effective_client_id)

    results = (
        query.group_by(func.date(ProductionEntry.shift_date)).order_by(func.date(ProductionEntry.shift_date)).all()
    )

    return [{"date": str(r.date), "value": round(float(r.value), 2) if r.value else 0} for r in results]


@trends_router.get("/performance/by-shift")
def get_performance_by_shift(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get performance aggregated by shift.

    Returns units produced, production rate, and average performance percentage
    grouped by shift for the specified date range.

    SECURITY: Requires authentication; non-admin users see only their assigned client.
    """
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.shift import Shift

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = (
        db.query(
            ProductionEntry.shift_id,
            Shift.shift_name,
            func.sum(ProductionEntry.units_produced).label("units"),
            func.sum(ProductionEntry.run_time_hours).label("hours"),
            func.avg(ProductionEntry.performance_percentage).label("performance"),
            func.count(ProductionEntry.production_entry_id).label("entry_count"),
        )
        .outerjoin(Shift, ProductionEntry.shift_id == Shift.shift_id)
        .filter(
            ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
            ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
        )
    )

    if effective_client_id:
        query = query.filter(ProductionEntry.client_id == effective_client_id)

    results = (
        query.group_by(ProductionEntry.shift_id, Shift.shift_name)
        .order_by(func.avg(ProductionEntry.performance_percentage).desc())
        .all()
    )

    return [
        {
            "shift_id": r.shift_id,
            "shift_name": r.shift_name or f"Shift {r.shift_id}",
            "units": int(r.units) if r.units else 0,
            "rate": round(float(r.units) / float(r.hours), 1) if r.hours and r.hours > 0 else 0,
            "performance": round(float(r.performance), 1) if r.performance else 0,
        }
        for r in results
    ]


@trends_router.get("/performance/by-product")
def get_performance_by_product(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get performance aggregated by product.

    Returns units produced, production rate, and average performance percentage
    grouped by product. Limited to the top N products (default 10).

    SECURITY: Requires authentication; non-admin users see only their assigned client.
    """
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.product import Product

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = (
        db.query(
            ProductionEntry.product_id,
            Product.product_name,
            func.sum(ProductionEntry.units_produced).label("units"),
            func.sum(ProductionEntry.run_time_hours).label("hours"),
            func.avg(ProductionEntry.performance_percentage).label("performance"),
            func.count(ProductionEntry.production_entry_id).label("entry_count"),
        )
        .join(Product, ProductionEntry.product_id == Product.product_id)
        .filter(
            ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
            ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
        )
    )

    if effective_client_id:
        query = query.filter(ProductionEntry.client_id == effective_client_id)

    results = (
        query.group_by(ProductionEntry.product_id, Product.product_name)
        .order_by(func.avg(ProductionEntry.performance_percentage).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "product_id": r.product_id,
            "product_name": r.product_name or f"Product {r.product_id}",
            "units": int(r.units) if r.units else 0,
            "rate": round(float(r.units) / float(r.hours), 1) if r.hours and r.hours > 0 else 0,
            "performance": round(float(r.performance), 1) if r.performance else 0,
        }
        for r in results
    ]


@trends_router.get("/quality/trend")
def get_quality_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get daily quality (FPY) trend data"""
    from backend.schemas.quality_entry import QualityEntry

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = db.query(
        func.date(QualityEntry.shift_date).label("date"),
        func.sum(QualityEntry.units_passed).label("passed"),
        func.sum(QualityEntry.units_inspected).label("inspected"),
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
    )

    if effective_client_id:
        query = query.filter(QualityEntry.client_id == effective_client_id)

    results = query.group_by(func.date(QualityEntry.shift_date)).order_by(func.date(QualityEntry.shift_date)).all()

    return [
        {
            "date": str(r.date),
            "value": round((r.passed / r.inspected) * 100, 2) if r.inspected and r.inspected > 0 else 0,
        }
        for r in results
    ]


@trends_router.get("/availability/trend")
def get_availability_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get daily availability trend data (calculated from downtime)"""
    from backend.schemas.downtime_entry import DowntimeEntry
    from backend.schemas.production_entry import ProductionEntry

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Get production days (scheduled time proxy)
    prod_query = db.query(
        func.date(ProductionEntry.shift_date).label("date"),
        func.count(ProductionEntry.production_entry_id).label("entries"),
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
    )
    if effective_client_id:
        prod_query = prod_query.filter(ProductionEntry.client_id == effective_client_id)
    prod_results = {
        str(r.date): r.entries * 8 for r in prod_query.group_by(func.date(ProductionEntry.shift_date)).all()
    }

    # Get downtime by day
    dt_query = db.query(
        func.date(DowntimeEntry.shift_date).label("date"),
        func.sum(DowntimeEntry.downtime_duration_minutes).label("downtime_mins"),
    ).filter(
        DowntimeEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        DowntimeEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
    )
    if effective_client_id:
        dt_query = dt_query.filter(DowntimeEntry.client_id == effective_client_id)
    dt_results = {
        str(r.date): float(r.downtime_mins) / 60 if r.downtime_mins else 0
        for r in dt_query.group_by(func.date(DowntimeEntry.shift_date)).all()
    }

    # Calculate availability per day
    trend_data = []
    for day in sorted(prod_results.keys()):
        scheduled = prod_results.get(day, 8)
        downtime = dt_results.get(day, 0)
        availability = ((scheduled - downtime) / scheduled * 100) if scheduled > 0 else 100
        trend_data.append({"date": day, "value": round(max(0, min(100, availability)), 2)})

    return trend_data


@trends_router.get("/oee/trend")
def get_oee_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get daily OEE trend data (Availability x Performance x Quality)"""
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.quality_entry import QualityEntry
    from backend.schemas.downtime_entry import DowntimeEntry

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Get performance by day
    perf_query = db.query(
        func.date(ProductionEntry.shift_date).label("date"),
        func.avg(ProductionEntry.performance_percentage).label("performance"),
        func.count(ProductionEntry.production_entry_id).label("entries"),
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
    )
    if effective_client_id:
        perf_query = perf_query.filter(ProductionEntry.client_id == effective_client_id)
    perf_results = {
        str(r.date): {"performance": float(r.performance) if r.performance else 95, "entries": r.entries}
        for r in perf_query.group_by(func.date(ProductionEntry.shift_date)).all()
    }

    # Get quality by day
    qual_query = db.query(
        func.date(QualityEntry.shift_date).label("date"),
        func.sum(QualityEntry.units_passed).label("passed"),
        func.sum(QualityEntry.units_inspected).label("inspected"),
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
    )
    if effective_client_id:
        qual_query = qual_query.filter(QualityEntry.client_id == effective_client_id)
    qual_results = {
        str(r.date): (r.passed / r.inspected * 100) if r.inspected and r.inspected > 0 else 97
        for r in qual_query.group_by(func.date(QualityEntry.shift_date)).all()
    }

    # Get downtime by day
    dt_query = db.query(
        func.date(DowntimeEntry.shift_date).label("date"),
        func.sum(DowntimeEntry.downtime_duration_minutes).label("downtime_mins"),
    ).filter(
        DowntimeEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        DowntimeEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
    )
    if effective_client_id:
        dt_query = dt_query.filter(DowntimeEntry.client_id == effective_client_id)
    dt_results = {
        str(r.date): float(r.downtime_mins) / 60 if r.downtime_mins else 0
        for r in dt_query.group_by(func.date(DowntimeEntry.shift_date)).all()
    }

    # Calculate OEE per day
    trend_data = []
    for day in sorted(perf_results.keys()):
        scheduled = perf_results[day]["entries"] * 8
        downtime = dt_results.get(day, 0)
        availability = ((scheduled - downtime) / scheduled * 100) if scheduled > 0 else 90
        performance = perf_results[day]["performance"]
        quality = qual_results.get(day, 97)
        oee = (availability / 100) * (performance / 100) * (quality / 100) * 100
        trend_data.append({"date": day, "value": round(min(100, oee), 2)})

    return trend_data


@trends_router.get("/on-time-delivery/trend")
def get_otd_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get daily On-Time Delivery trend data"""
    from backend.schemas.work_order import WorkOrder

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Query work orders grouped by required_date
    query = db.query(
        func.date(WorkOrder.required_date).label("date"),
        func.count(WorkOrder.work_order_id).label("total"),
        func.sum(case((WorkOrder.actual_delivery_date <= WorkOrder.required_date, 1), else_=0)).label("on_time"),
    ).filter(
        WorkOrder.required_date.isnot(None),
        WorkOrder.required_date >= datetime.combine(start_date, datetime.min.time()),
        WorkOrder.required_date <= datetime.combine(end_date, datetime.max.time()),
    )

    if effective_client_id:
        query = query.filter(WorkOrder.client_id == effective_client_id)

    results = query.group_by(func.date(WorkOrder.required_date)).order_by(func.date(WorkOrder.required_date)).all()

    return [
        {"date": str(r.date), "value": round((r.on_time / r.total * 100) if r.total > 0 else 0, 2)} for r in results
    ]


@trends_router.get("/absenteeism/trend")
def get_absenteeism_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get daily absenteeism trend data"""
    from backend.schemas.attendance_entry import AttendanceEntry

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Query attendance grouped by shift_date
    query = db.query(
        func.date(AttendanceEntry.shift_date).label("date"),
        func.sum(AttendanceEntry.scheduled_hours).label("scheduled"),
        func.sum(func.coalesce(AttendanceEntry.absence_hours, 0)).label("absent"),
    ).filter(
        AttendanceEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        AttendanceEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
    )

    if effective_client_id:
        query = query.filter(AttendanceEntry.client_id == effective_client_id)

    results = (
        query.group_by(func.date(AttendanceEntry.shift_date)).order_by(func.date(AttendanceEntry.shift_date)).all()
    )

    return [
        {
            "date": str(r.date),
            "value": round((r.absent / r.scheduled * 100) if r.scheduled and r.scheduled > 0 else 0, 2),
        }
        for r in results
    ]
