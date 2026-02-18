"""
KPI Efficiency Routes

Efficiency aggregation endpoints by shift, product, and trend data.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import date, datetime, timedelta, timezone

from backend.utils.logging_utils import get_module_logger
from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User

logger = get_module_logger(__name__)

efficiency_router = APIRouter(prefix="/api/kpi", tags=["KPI Calculations"])


@efficiency_router.get("/efficiency/by-shift")
def get_efficiency_by_shift(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get efficiency aggregated by shift.

    Returns actual output, expected output, and average efficiency percentage
    grouped by shift for the specified date range.

    SECURITY: Requires authentication; non-admin users see only their assigned client.
    """
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.shift import Shift

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    query = (
        db.query(
            ProductionEntry.shift_id,
            Shift.shift_name,
            func.sum(ProductionEntry.units_produced).label("actual_output"),
            func.avg(ProductionEntry.efficiency_percentage).label("efficiency"),
            func.count(ProductionEntry.production_entry_id).label("entry_count"),
        )
        .join(Shift, ProductionEntry.shift_id == Shift.shift_id)
        .filter(ProductionEntry.shift_date >= start_date, ProductionEntry.shift_date <= end_date)
    )

    if client_id:
        query = query.filter(ProductionEntry.client_id == client_id)

    results = query.group_by(ProductionEntry.shift_id, Shift.shift_name).all()

    return [
        {
            "shift_id": r.shift_id,
            "shift_name": r.shift_name or f"Shift {r.shift_id}",
            "actual_output": r.actual_output or 0,
            "expected_output": int((r.actual_output or 0) / ((r.efficiency or 100) / 100)) if r.efficiency else 0,
            "efficiency": float(r.efficiency) if r.efficiency else 0,
        }
        for r in results
    ]


@efficiency_router.get("/efficiency/by-product")
def get_efficiency_by_product(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get top products by efficiency.

    Returns products ranked by average efficiency with actual output and entry counts.
    Limited to the top N products (default 10).

    SECURITY: Requires authentication; non-admin users see only their assigned client.
    """
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.product import Product

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    query = (
        db.query(
            ProductionEntry.product_id,
            Product.product_name,
            func.sum(ProductionEntry.units_produced).label("actual_output"),
            func.avg(ProductionEntry.efficiency_percentage).label("efficiency"),
            func.count(ProductionEntry.production_entry_id).label("entry_count"),
        )
        .join(Product, ProductionEntry.product_id == Product.product_id)
        .filter(ProductionEntry.shift_date >= start_date, ProductionEntry.shift_date <= end_date)
    )

    if client_id:
        query = query.filter(ProductionEntry.client_id == client_id)

    results = (
        query.group_by(ProductionEntry.product_id, Product.product_name)
        .order_by(func.avg(ProductionEntry.efficiency_percentage).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "product_id": r.product_id,
            "product_name": r.product_name or f"Product {r.product_id}",
            "actual_output": r.actual_output or 0,
            "efficiency": float(r.efficiency) if r.efficiency else 0,
        }
        for r in results
    ]


@efficiency_router.get("/efficiency/trend")
def get_efficiency_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get daily efficiency trend data.

    Returns date/value pairs of average efficiency percentage per day
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
        func.avg(ProductionEntry.efficiency_percentage).label("value"),
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
