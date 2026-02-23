"""
Shift Service
Thin service layer wrapping Shift CRUD operations.
Routes should import from this module instead of backend.crud.shift directly.
"""

from typing import List, Optional
from datetime import time
from sqlalchemy.orm import Session

from backend.crud.shift import (
    create_shift,
    list_shifts,
    get_shift,
    update_shift,
    deactivate_shift,
    check_shift_overlaps,
)
from backend.orm.shift import Shift


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


def check_overlaps(
    db: Session,
    client_id: str,
    start_time: time,
    end_time: time,
    exclude_shift_id: Optional[int] = None,
) -> List[Shift]:
    """Check for overlapping shifts for a given client and time range.

    Args:
        db: Database session.
        client_id: Client to check shifts for.
        start_time: Proposed shift start time.
        end_time: Proposed shift end time.
        exclude_shift_id: Shift ID to exclude (for update operations).

    Returns:
        List of overlapping Shift ORM objects (empty = no overlaps).
    """
    return check_shift_overlaps(db, client_id, start_time, end_time, exclude_shift_id)


def format_overlap_warnings(overlapping_shifts: List[Shift]) -> List[str]:
    """Format overlapping shifts into human-readable warning strings.

    Args:
        overlapping_shifts: List of Shift ORM objects that overlap.

    Returns:
        List of warning message strings.
    """
    warnings: List[str] = []
    for s in overlapping_shifts:
        start_str = s.start_time.strftime("%H:%M")
        end_str = s.end_time.strftime("%H:%M")
        warnings.append(
            f"Shift overlaps with {s.shift_name} ({start_str}-{end_str})"
        )
    return warnings
