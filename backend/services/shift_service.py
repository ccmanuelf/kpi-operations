"""
Shift Service
Thin service layer wrapping Shift CRUD operations.
Routes should import from this module instead of backend.crud.shift directly.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from backend.crud.shift import (
    create_shift,
    list_shifts,
    get_shift,
    update_shift,
    deactivate_shift,
)


def create_shift_record(db: Session, data):
    """Create a new shift for a client."""
    return create_shift(db, data)


def list_client_shifts(db: Session, client_id: str, include_inactive: bool = False):
    """List shifts for a client."""
    return list_shifts(db, client_id, include_inactive)


def get_shift_by_id(db: Session, shift_id: int):
    """Get a shift by ID."""
    return get_shift(db, shift_id)


def update_shift_record(db: Session, shift_id: int, data):
    """Update a shift."""
    return update_shift(db, shift_id, data)


def deactivate_shift_record(db: Session, shift_id: int) -> bool:
    """Soft-delete a shift."""
    return deactivate_shift(db, shift_id)
