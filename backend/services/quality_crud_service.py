"""
Quality CRUD Service
Thin service layer wrapping Quality Inspection CRUD operations.
Routes should import from this module instead of backend.crud.quality directly.

Note: The QualityService class in backend.services.quality_service provides
higher-level quality analytics. This module handles basic CRUD passthrough.
"""

from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.crud.quality import (
    create_quality_inspection,
    delete_quality_inspection,
    get_quality_inspection,
    get_quality_inspections,
    update_quality_inspection,
)
from backend.orm.quality_entry import QualityEntry
from backend.orm.user import User
from backend.schemas.quality import (
    QualityInspectionCreate,
    QualityInspectionResponse,
    QualityInspectionUpdate,
)


def create_inspection(
    db: Session, inspection_data: QualityInspectionCreate, current_user: User
) -> QualityInspectionResponse:
    """Create a new quality inspection."""
    return create_quality_inspection(db, inspection_data, current_user)


def get_inspection(db: Session, inspection_id: str, current_user: User) -> Optional[QualityEntry]:
    """Get a quality inspection by ID."""
    return get_quality_inspection(db, inspection_id, current_user)


def list_inspections(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    work_order_id: Optional[str] = None,
    inspection_stage: Optional[str] = None,
    client_id: Optional[str] = None,
) -> List[QualityEntry]:
    """List quality inspections with filters."""
    return get_quality_inspections(
        db,
        current_user,
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        work_order_id=work_order_id,
        inspection_stage=inspection_stage,
        client_id=client_id,
    )


def update_inspection(
    db: Session, inspection_id: str, inspection_data: QualityInspectionUpdate, current_user: User
) -> Optional[QualityInspectionResponse]:
    """Update a quality inspection."""
    return update_quality_inspection(db, inspection_id, inspection_data, current_user)


def delete_inspection(db: Session, inspection_id: str, current_user: User) -> bool:
    """Delete a quality inspection."""
    return delete_quality_inspection(db, inspection_id, current_user)
