"""
CRUD operations for quality inspection tracking
PHASE 4
SECURITY: Multi-tenant client filtering enabled

Phase 1.3: Decoupled inline PPM/DPMO calculations.
Quality KPI calculations are now handled by QualityKPIService.
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from decimal import Decimal
from fastapi import HTTPException

from backend.schemas.quality_entry import QualityEntry
from backend.models.quality import (
    QualityInspectionCreate,
    QualityInspectionUpdate,
    QualityInspectionResponse
)
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.schemas.user import User
from backend.utils.soft_delete import soft_delete


def _calculate_quality_kpis(
    units_inspected: int,
    units_defective: int,
    opportunities_per_unit: int = 10
) -> tuple[Decimal, Decimal]:
    """
    Internal helper to calculate PPM and DPMO for a quality entry.

    Phase 1.3: Uses pure calculation functions instead of inline logic.

    Args:
        units_inspected: Total units inspected
        units_defective: Units found defective
        opportunities_per_unit: Defect opportunities per unit (default: 10)

    Returns:
        Tuple of (ppm, dpmo)
    """
    from backend.calculations.ppm import calculate_ppm_pure
    from backend.calculations.dpmo import calculate_dpmo_pure

    ppm = calculate_ppm_pure(units_inspected, units_defective)
    dpmo, _ = calculate_dpmo_pure(units_defective, units_inspected, opportunities_per_unit)

    return ppm, dpmo


def create_quality_inspection(
    db: Session,
    inspection: QualityInspectionCreate,
    current_user: User
) -> QualityInspectionResponse:
    """
    Create new quality inspection record
    SECURITY: Verifies user has access to the specified client
    """
    # SECURITY: Verify user has access to this client
    if hasattr(inspection, 'client_id') and inspection.client_id:
        verify_client_access(current_user, inspection.client_id)

    # Calculate PPM and DPMO using pure functions
    units_inspected = getattr(inspection, 'units_inspected', 0) or 0
    units_defective = getattr(inspection, 'units_defective', 0) or getattr(inspection, 'defects_found', 0) or 0

    ppm, dpmo = _calculate_quality_kpis(units_inspected, units_defective)

    db_inspection = QualityEntry(
        **inspection.dict(),
        ppm=ppm,
        dpmo=dpmo,
        inspector_id=current_user.user_id
    )

    db.add(db_inspection)
    db.commit()
    db.refresh(db_inspection)

    return QualityInspectionResponse.from_orm(db_inspection)


def get_quality_inspection(
    db: Session,
    inspection_id: str,
    current_user: User
) -> Optional[QualityEntry]:
    """
    Get quality inspection by ID
    SECURITY: Verifies user has access to the record's client
    """
    db_inspection = db.query(QualityEntry).filter(
        QualityEntry.quality_entry_id == inspection_id
    ).first()

    if not db_inspection:
        raise HTTPException(status_code=404, detail="Quality inspection not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_inspection, 'client_id') and db_inspection.client_id:
        verify_client_access(current_user, db_inspection.client_id)

    return db_inspection


def get_quality_inspections(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    work_order_id: Optional[str] = None,
    inspection_stage: Optional[str] = None,
    client_id: Optional[str] = None
) -> List[QualityEntry]:
    """
    Get quality inspections with filters
    SECURITY: Automatically filters by user's authorized clients
    """
    query = db.query(QualityEntry)

    # SECURITY: Apply client filtering based on user's role
    client_filter = build_client_filter_clause(current_user, QualityEntry.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Apply additional filters
    if client_id:
        query = query.filter(QualityEntry.client_id == client_id)

    if start_date:
        query = query.filter(QualityEntry.shift_date >= start_date)

    if end_date:
        query = query.filter(QualityEntry.shift_date <= end_date)

    if work_order_id:
        query = query.filter(QualityEntry.work_order_id == work_order_id)

    if inspection_stage:
        query = query.filter(QualityEntry.inspection_stage == inspection_stage)

    return query.order_by(
        QualityEntry.shift_date.desc()
    ).offset(skip).limit(limit).all()


def update_quality_inspection(
    db: Session,
    inspection_id: str,
    inspection_update: QualityInspectionUpdate,
    current_user: User
) -> Optional[QualityInspectionResponse]:
    """
    Update quality inspection record
    SECURITY: Verifies user has access to the record's client
    """
    db_inspection = db.query(QualityEntry).filter(
        QualityEntry.quality_entry_id == inspection_id
    ).first()

    if not db_inspection:
        raise HTTPException(status_code=404, detail="Quality inspection not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_inspection, 'client_id') and db_inspection.client_id:
        verify_client_access(current_user, db_inspection.client_id)

    update_data = inspection_update.dict(exclude_unset=True)

    # Recalculate PPM and DPMO if values changed (using pure functions)
    units = update_data.get('units_inspected', db_inspection.units_inspected)
    defects = update_data.get('units_defective', db_inspection.units_defective)

    ppm, dpmo = _calculate_quality_kpis(units, defects)
    update_data['ppm'] = ppm
    update_data['dpmo'] = dpmo

    for field, value in update_data.items():
        if hasattr(db_inspection, field):
            setattr(db_inspection, field, value)

    db.commit()
    db.refresh(db_inspection)

    return QualityInspectionResponse.from_orm(db_inspection)


def delete_quality_inspection(
    db: Session,
    inspection_id: str,
    current_user: User
) -> bool:
    """
    Soft delete quality inspection record (sets is_active = False)
    SECURITY: Verifies user has access to the record's client
    """
    db_inspection = db.query(QualityEntry).filter(
        QualityEntry.quality_entry_id == inspection_id
    ).first()

    if not db_inspection:
        raise HTTPException(status_code=404, detail="Quality inspection not found")

    # SECURITY: Verify user has access to this record's client
    if hasattr(db_inspection, 'client_id') and db_inspection.client_id:
        verify_client_access(current_user, db_inspection.client_id)

    # Soft delete - preserves data integrity
    return soft_delete(db, db_inspection)
