"""
Coverage Service
Thin service layer wrapping Shift Coverage CRUD operations.
Routes should import from this module instead of backend.crud.coverage directly.
"""

from typing import Any, List, Optional
from datetime import date
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.crud.coverage import (
    create_shift_coverage,
    get_shift_coverage,
    get_shift_coverages,
    update_shift_coverage,
    delete_shift_coverage,
)


def create_coverage(db: Session, coverage_data: Any, current_user: User) -> Any:
    """Create a new shift coverage record."""
    return create_shift_coverage(db, coverage_data, current_user)


def get_coverage(db: Session, coverage_id: int, current_user: User) -> Any:
    """Get a shift coverage record by ID."""
    return get_shift_coverage(db, coverage_id, current_user)


def list_coverages(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    shift_id: Optional[int] = None,
    client_id: Optional[str] = None,
) -> Any:
    """List shift coverage records with filters."""
    return get_shift_coverages(db, current_user, skip, limit, start_date, end_date, shift_id, client_id)


def update_coverage(db: Session, coverage_id: int, coverage_data: Any, current_user: User) -> Any:
    """Update a shift coverage record."""
    return update_shift_coverage(db, coverage_id, coverage_data, current_user)


def delete_coverage(db: Session, coverage_id: int, current_user: User) -> bool:
    """Delete a shift coverage record."""
    return delete_shift_coverage(db, coverage_id, current_user)
