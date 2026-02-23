"""
CRUD operations for break time management.
Provides create, list, aggregate, update, and soft-delete for break times.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from fastapi import HTTPException

from backend.orm.break_time import BreakTime
from backend.orm.shift import Shift
from backend.schemas.break_time import BreakTimeCreate, BreakTimeUpdate


def create_break_time(db: Session, data: BreakTimeCreate) -> BreakTime:
    """
    Create a new break time entry.

    Validates that the referenced shift_id exists before creating.

    Args:
        db: Database session
        data: Validated break time creation data

    Returns:
        Created BreakTime ORM instance

    Raises:
        HTTPException 404: If shift_id does not exist
    """
    shift = db.query(Shift).filter(Shift.shift_id == data.shift_id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    db_break = BreakTime(**data.model_dump())
    db.add(db_break)
    db.commit()
    db.refresh(db_break)
    return db_break


def list_break_times(db: Session, shift_id: int, client_id: str) -> List[BreakTime]:
    """
    List active break times for a specific shift, ordered by start_offset_minutes.

    Args:
        db: Database session
        shift_id: Shift to list breaks for
        client_id: Tenant isolation filter

    Returns:
        List of active BreakTime records ordered by start_offset_minutes
    """
    return (
        db.query(BreakTime)
        .filter(
            BreakTime.shift_id == shift_id,
            BreakTime.client_id == client_id,
            BreakTime.is_active == True,  # noqa: E712 — SQLAlchemy filter
        )
        .order_by(BreakTime.start_offset_minutes)
        .all()
    )


def list_break_times_for_client(db: Session, client_id: str) -> List[BreakTime]:
    """
    List all active break times for a client across all shifts.

    Args:
        db: Database session
        client_id: Tenant isolation filter

    Returns:
        List of active BreakTime records for the client
    """
    return (
        db.query(BreakTime)
        .filter(
            BreakTime.client_id == client_id,
            BreakTime.is_active == True,  # noqa: E712
        )
        .order_by(BreakTime.shift_id, BreakTime.start_offset_minutes)
        .all()
    )


def get_total_break_minutes(db: Session, shift_id: int, client_id: str) -> int:
    """
    Get the total break minutes for a shift (sum of active break durations).

    This is the KEY function for KPI integration — subtracts breaks from
    available production time.

    Args:
        db: Database session
        shift_id: Shift to sum breaks for
        client_id: Tenant isolation filter

    Returns:
        Total break minutes as integer (0 if no breaks configured)
    """
    result = (
        db.query(func.coalesce(func.sum(BreakTime.duration_minutes), 0))
        .filter(
            BreakTime.shift_id == shift_id,
            BreakTime.client_id == client_id,
            BreakTime.is_active == True,  # noqa: E712
        )
        .scalar()
    )
    return int(result)


def update_break_time(db: Session, break_id: int, data: BreakTimeUpdate) -> Optional[BreakTime]:
    """
    Update an existing break time entry.

    Args:
        db: Database session
        break_id: ID of the break to update
        data: Partial update data

    Returns:
        Updated BreakTime instance, or None if not found

    Raises:
        HTTPException 404: If break_id does not exist
    """
    db_break = db.query(BreakTime).filter(BreakTime.break_id == break_id).first()
    if not db_break:
        raise HTTPException(status_code=404, detail="Break time not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_break, field, value)

    db.commit()
    db.refresh(db_break)
    return db_break


def deactivate_break_time(db: Session, break_id: int) -> bool:
    """
    Soft-delete a break time entry (sets is_active = False).

    Args:
        db: Database session
        break_id: ID of the break to deactivate

    Returns:
        True if deactivated, False if not found

    Raises:
        HTTPException 404: If break_id does not exist
    """
    db_break = db.query(BreakTime).filter(BreakTime.break_id == break_id).first()
    if not db_break:
        raise HTTPException(status_code=404, detail="Break time not found")

    db_break.is_active = False
    db.commit()
    return True
