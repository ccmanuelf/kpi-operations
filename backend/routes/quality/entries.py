"""
Quality Inspection - Entry CRUD Endpoints

Create, read, update, delete quality inspection records plus
work-order and statistics summary endpoints.
"""

from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User
from backend.middleware.client_auth import build_client_filter_clause, verify_client_access
from backend.models.quality import (
    QualityInspectionCreate,
    QualityInspectionUpdate,
    QualityInspectionResponse,
)
from backend.crud.quality import (
    create_quality_inspection,
    get_quality_inspection,
    get_quality_inspections,
    update_quality_inspection,
    delete_quality_inspection,
)
from backend.utils.logging_utils import get_module_logger, log_operation, log_error

logger = get_module_logger(__name__)

entries_router = APIRouter()


@entries_router.post("/", response_model=QualityInspectionResponse, status_code=status.HTTP_201_CREATED)
def create_quality(
    inspection: QualityInspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QualityInspectionResponse:
    """
    Create new quality inspection record
    SECURITY: Enforces client filtering through user authentication
    """
    try:
        result = create_quality_inspection(db, inspection, current_user)
        log_operation(
            logger,
            "CREATE",
            "quality",
            resource_id=str(result.quality_entry_id),
            user_id=current_user.user_id,
            details={"units_inspected": getattr(inspection, "units_inspected", None)},
        )
        return result
    except Exception as e:
        db.rollback()
        log_error(logger, "CREATE", "quality", e, user_id=current_user.user_id)
        raise


@entries_router.get("/", response_model=List[QualityInspectionResponse])
def list_quality(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    work_order_id: Optional[str] = None,
    inspection_stage: Optional[str] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[QualityInspectionResponse]:
    """
    List quality inspections with filters
    SECURITY: Returns only inspections for user's authorized clients
    """
    return get_quality_inspections(
        db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        work_order_id=work_order_id,
        inspection_stage=inspection_stage,
        client_id=client_id,
    )


@entries_router.get("/statistics/summary")
def get_quality_statistics(
    start_date: date,
    end_date: date,
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Get quality statistics summary for a date range
    SECURITY: Returns only data for user's authorized clients
    """
    from sqlalchemy import func, cast, Date
    from backend.schemas.quality_entry import QualityEntry

    query = db.query(
        func.sum(QualityEntry.units_inspected).label("total_inspected"),
        func.sum(QualityEntry.units_defective).label("total_defects"),
        func.sum(QualityEntry.units_scrapped).label("total_scrap"),
        func.sum(QualityEntry.units_reworked).label("total_rework"),
        func.avg(QualityEntry.ppm).label("avg_ppm"),
        func.avg(QualityEntry.dpmo).label("avg_dpmo"),
    )

    # SECURITY FIX (VULN-002): Apply client filter to prevent cross-client data access
    # If specific client_id requested, verify access first
    if client_id:
        verify_client_access(current_user, client_id)
        query = query.filter(QualityEntry.client_id == client_id)
    else:
        # Apply user's authorized client filter
        client_filter = build_client_filter_clause(current_user, QualityEntry.client_id)
        if client_filter is not None:
            query = query.filter(client_filter)

    # Apply date filters (shift_date is DateTime, cast to Date for comparison)
    query = query.filter(
        cast(QualityEntry.shift_date, Date) >= start_date,
        cast(QualityEntry.shift_date, Date) <= end_date,
    )

    # Note: QualityEntry doesn't have product_id/shift_id - these filters are ignored
    # for backward compatibility (they were likely never used correctly anyway)

    result = query.first()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "product_id": product_id,
        "shift_id": shift_id,
        "total_units_inspected": result.total_inspected or 0,
        "total_defects_found": result.total_defects or 0,
        "total_scrap_units": result.total_scrap or 0,
        "total_rework_units": result.total_rework or 0,
        "average_ppm": float(result.avg_ppm) if result.avg_ppm else 0,
        "average_dpmo": float(result.avg_dpmo) if result.avg_dpmo else 0,
        "calculation_timestamp": datetime.now(tz=timezone.utc),
    }


@entries_router.get("/by-work-order/{work_order_id}", response_model=List[QualityInspectionResponse])
def get_quality_by_work_order(
    work_order_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[QualityInspectionResponse]:
    """
    Get all quality inspections for a specific work order
    SECURITY: Returns only inspections for user's authorized clients
    """
    from backend.schemas.quality_entry import QualityEntry

    query = db.query(QualityEntry).filter(QualityEntry.work_order_id == work_order_id)

    # SECURITY FIX (VULN-001): Apply client filter to prevent cross-client data access
    client_filter = build_client_filter_clause(current_user, QualityEntry.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.offset(skip).limit(limit).all()


@entries_router.get("/{inspection_id}", response_model=QualityInspectionResponse)
def get_quality(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QualityInspectionResponse:
    """
    Get quality inspection by ID
    SECURITY: Verifies user has access to this inspection record
    """
    inspection = get_quality_inspection(db, inspection_id, current_user)
    if not inspection:
        raise HTTPException(status_code=404, detail="Quality inspection not found")
    return inspection


@entries_router.put("/{inspection_id}", response_model=QualityInspectionResponse)
def update_quality(
    inspection_id: int,
    inspection_update: QualityInspectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QualityInspectionResponse:
    """
    Update quality inspection record
    SECURITY: Verifies user has access to this inspection record
    """
    try:
        updated = update_quality_inspection(db, inspection_id, inspection_update, current_user)
        if not updated:
            raise HTTPException(status_code=404, detail="Quality inspection not found")
        log_operation(logger, "UPDATE", "quality", resource_id=str(inspection_id), user_id=current_user.user_id)
        return updated
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log_error(logger, "UPDATE", "quality", e, resource_id=str(inspection_id), user_id=current_user.user_id)
        raise


@entries_router.delete("/{inspection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quality(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> None:
    """
    Delete quality inspection record (supervisor only)
    SECURITY: Supervisor/admin only, verifies client access
    """
    try:
        success = delete_quality_inspection(db, inspection_id, current_user)
        if not success:
            raise HTTPException(status_code=404, detail="Quality inspection not found")
        log_operation(logger, "DELETE", "quality", resource_id=str(inspection_id), user_id=current_user.user_id)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        log_error(logger, "DELETE", "quality", e, resource_id=str(inspection_id), user_id=current_user.user_id)
        raise
