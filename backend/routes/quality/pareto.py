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
    from sqlalchemy import func

    from backend.schemas.defect_detail import DefectDetail
    from backend.schemas.quality_entry import QualityEntry

    # Default to last 30 days
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = (
        db.query(
            DefectDetail.defect_type,
            func.sum(DefectDetail.defect_count).label("count"),
        )
        .join(QualityEntry, DefectDetail.quality_entry_id == QualityEntry.quality_entry_id)
        .filter(
            QualityEntry.shift_date >= start_date.isoformat(),
            QualityEntry.shift_date <= end_date.isoformat(),
        )
    )

    if effective_client_id:
        query = query.filter(DefectDetail.client_id_fk == effective_client_id)

    results = (
        query.group_by(DefectDetail.defect_type)
        .order_by(func.sum(DefectDetail.defect_count).desc())
        .limit(limit)
        .all()
    )

    # Calculate total for percentages
    total_defects = sum(r.count or 0 for r in results)

    return [
        {
            "defect_type": str(r.defect_type),
            "count": r.count or 0,
            "percentage": round((r.count / total_defects) * 100, 1) if total_defects > 0 else 0,
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
    from sqlalchemy import func

    from backend.schemas.quality_entry import QualityEntry
    from backend.schemas.work_order import WorkOrder

    # Default to last 30 days
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = (
        db.query(
            WorkOrder.style_model.label("product_name"),
            func.sum(QualityEntry.units_inspected).label("inspected"),
            func.sum(QualityEntry.units_defective).label("defects"),
            func.sum(QualityEntry.units_passed).label("passed"),
        )
        .join(WorkOrder, QualityEntry.work_order_id == WorkOrder.work_order_id)
        .filter(
            QualityEntry.shift_date >= start_date.isoformat(),
            QualityEntry.shift_date <= end_date.isoformat(),
        )
    )

    if effective_client_id:
        query = query.filter(QualityEntry.client_id == effective_client_id)

    results = (
        query.group_by(WorkOrder.style_model)
        .order_by(func.sum(QualityEntry.units_inspected).desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "product_name": r.product_name or "Unknown",
            "inspected": r.inspected or 0,
            "defects": r.defects or 0,
            "fpy": round((r.passed / r.inspected) * 100, 1) if r.inspected and r.inspected > 0 else 0,
        }
        for r in results
    ]
