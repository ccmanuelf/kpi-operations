"""
Break Time Service
Thin service layer wrapping Break Time CRUD operations.
Routes should import from this module instead of backend.crud.break_time directly.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from backend.crud.break_time import (
    create_break_time,
    list_break_times,
    list_break_times_for_client,
    get_total_break_minutes,
    update_break_time,
    deactivate_break_time,
)


def create_break_time_record(db: Session, data):
    """Create a new break time."""
    return create_break_time(db, data)


def list_break_times_for_shift(db: Session, shift_id: int, client_id: str):
    """List break times for a specific shift."""
    return list_break_times(db, shift_id, client_id)


def list_all_break_times_for_client(db: Session, client_id: str):
    """List all break times for a client."""
    return list_break_times_for_client(db, client_id)


def get_total_break_minutes_for_shift(db: Session, shift_id: int, client_id: str) -> int:
    """Get total break minutes for a shift."""
    return get_total_break_minutes(db, shift_id, client_id)


def update_break_time_record(db: Session, break_id: int, data):
    """Update a break time."""
    return update_break_time(db, break_id, data)


def deactivate_break_time_record(db: Session, break_id: int) -> bool:
    """Deactivate a break time."""
    return deactivate_break_time(db, break_id)
