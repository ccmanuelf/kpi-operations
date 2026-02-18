"""
Quality Inspection - Pareto Analysis Endpoints

Defect analysis endpoints: top defects, defects by type, and quality by product.
Used for Pareto root-cause analysis.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.calculations.ppm import identify_top_defects
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

pareto_router = APIRouter()


@pareto_router.get("/kpi/top-defects")
def get_top_defects(
    product_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """
    Get top defect types (Pareto analysis)
    Returns defects sorted by frequency for root cause analysis
    """
    return identify_top_defects(db, product_id, start_date, end_date, limit)


@pareto_router.get("/kpi/defects-by-type")
def get_defects_by_type(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """
    Get defect counts grouped by type with client filtering
    Returns defect_type, count, and percentage for Pareto analysis
    """
    from datetime import timedelta
    from sqlalchemy import text

    # Default to last 30 days
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Use raw SQL for reliable column access
    sql = """
        SELECT dd.defect_type, SUM(dd.defect_count) as count
        FROM DEFECT_DETAIL dd
        JOIN QUALITY_ENTRY qe ON dd.quality_entry_id = qe.quality_entry_id
        WHERE qe.shift_date >= :start_date AND qe.shift_date <= :end_date
    """
    params: dict = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}

    if effective_client_id:
        sql += " AND dd.client_id_fk = :client_id"
        params["client_id"] = effective_client_id

    sql += " GROUP BY dd.defect_type ORDER BY count DESC LIMIT :limit"
    params["limit"] = limit

    results = db.execute(text(sql), params).fetchall()

    # Calculate total for percentages
    total_defects = sum(r[1] or 0 for r in results)

    return [
        {
            "defect_type": str(r[0]),
            "count": r[1] or 0,
            "percentage": round((r[1] / total_defects) * 100, 1) if total_defects > 0 else 0,
        }
        for r in results
    ]


@pareto_router.get("/kpi/by-product")
def get_quality_by_product(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """
    Get quality metrics (FPY) grouped by product/style with client filtering
    Returns product_name (style_model), units inspected, defects, and FPY percentage
    """
    from datetime import timedelta
    from sqlalchemy import text

    # Default to last 30 days
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Use raw SQL - WORK_ORDER has style_model, not product_id
    sql = """
        SELECT wo.style_model as product_name,
               SUM(qe.units_inspected) as inspected,
               SUM(qe.units_defective) as defects,
               SUM(qe.units_passed) as passed
        FROM QUALITY_ENTRY qe
        JOIN WORK_ORDER wo ON qe.work_order_id = wo.work_order_id
        WHERE qe.shift_date >= :start_date AND qe.shift_date <= :end_date
    """
    params: dict = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}

    if effective_client_id:
        sql += " AND qe.client_id = :client_id"
        params["client_id"] = effective_client_id

    sql += " GROUP BY wo.style_model ORDER BY inspected DESC LIMIT :limit"
    params["limit"] = limit

    results = db.execute(text(sql), params).fetchall()

    return [
        {
            "product_name": r[0] or "Unknown",
            "inspected": r[1] or 0,
            "defects": r[2] or 0,
            "fpy": round((r[3] / r[1]) * 100, 1) if r[1] and r[1] > 0 else 0,
        }
        for r in results
    ]
