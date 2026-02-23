"""
Defect Detail Service
Thin service layer wrapping Defect Detail CRUD operations.
Routes should import from this module instead of backend.crud.defect_detail directly.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.crud.defect_detail import (
    create_defect_detail,
    get_defect_detail,
    get_defect_details,
    get_defect_details_by_quality_entry,
    update_defect_detail,
    delete_defect_detail,
    get_defect_summary_by_type,
)


def create_defect(db: Session, defect_data: dict, current_user: User):
    """Create a new defect detail."""
    return create_defect_detail(db, defect_data, current_user)


def get_defect(db: Session, defect_detail_id: str, current_user: User):
    """Get a defect detail by ID."""
    return get_defect_detail(db, defect_detail_id, current_user)


def list_defects(
    db: Session,
    current_user: User,
    quality_entry_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    """List defect details with filters."""
    return get_defect_details(db, current_user, quality_entry_id, skip, limit)


def list_defects_by_quality_entry(db: Session, quality_entry_id: str, current_user: User):
    """Get defect details for a quality entry."""
    return get_defect_details_by_quality_entry(db, quality_entry_id, current_user)


def update_defect(db: Session, defect_detail_id: str, defect_data: dict, current_user: User):
    """Update a defect detail."""
    return update_defect_detail(db, defect_detail_id, defect_data, current_user)


def delete_defect(db: Session, defect_detail_id: str, current_user: User) -> bool:
    """Delete a defect detail."""
    return delete_defect_detail(db, defect_detail_id, current_user)


def get_summary_by_type(db: Session, current_user: User, client_id: Optional[str] = None):
    """Get defect summary grouped by type."""
    return get_defect_summary_by_type(db, current_user, client_id)
