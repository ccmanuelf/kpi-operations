"""
CRUD operations for Shifts.
Supports per-client shift management with soft-delete.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_
from typing import List, Optional

from backend.schemas.shift import Shift
from backend.models.shift import ShiftCreate, ShiftUpdate
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)


def create_shift(db: Session, data: ShiftCreate) -> Shift:
    """Create a new shift for a client.

    Args:
        db: Database session.
        data: Shift creation payload.

    Returns:
        The newly created Shift ORM object.

    Raises:
        ValueError: If a shift with the same name already exists for the client.
    """
    db_entry = Shift(
        client_id=data.client_id,
        shift_name=data.shift_name,
        start_time=data.start_time,
        end_time=data.end_time,
        is_active=True,
    )
    try:
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Shift name '{data.shift_name}' already exists for client '{data.client_id}'"
        )
    logger.info("Created shift '%s' for client '%s'", data.shift_name, data.client_id)
    return db_entry


def list_shifts(
    db: Session,
    client_id: str,
    include_inactive: bool = False,
) -> List[Shift]:
    """List shifts for a client, ordered by shift_name.

    Args:
        db: Database session.
        client_id: Client to filter by.
        include_inactive: If True, include deactivated shifts.

    Returns:
        List of Shift ORM objects.
    """
    query = db.query(Shift).filter(Shift.client_id == client_id)
    if not include_inactive:
        query = query.filter(Shift.is_active == True)  # noqa: E712
    return query.order_by(Shift.shift_name).all()


def get_shift(db: Session, shift_id: int) -> Optional[Shift]:
    """Get a single shift by ID.

    Args:
        db: Database session.
        shift_id: Primary key of the shift.

    Returns:
        Shift ORM object or None if not found.
    """
    return db.query(Shift).filter(Shift.shift_id == shift_id).first()


def update_shift(
    db: Session,
    shift_id: int,
    data: ShiftUpdate,
) -> Optional[Shift]:
    """Update an existing shift.

    Args:
        db: Database session.
        shift_id: Primary key of the shift to update.
        data: Fields to update (only non-None fields are applied).

    Returns:
        Updated Shift ORM object, or None if not found.
    """
    db_entry = db.query(Shift).filter(Shift.shift_id == shift_id).first()
    if not db_entry:
        return None
    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(db_entry, field, value)
    db.commit()
    db.refresh(db_entry)
    logger.info("Updated shift shift_id=%d", shift_id)
    return db_entry


def deactivate_shift(db: Session, shift_id: int) -> bool:
    """Soft-delete a shift (set is_active = False).

    Args:
        db: Database session.
        shift_id: Primary key of the shift to deactivate.

    Returns:
        True if shift was found and deactivated, False if not found.
    """
    db_entry = db.query(Shift).filter(Shift.shift_id == shift_id).first()
    if not db_entry:
        return False
    db_entry.is_active = False
    db.commit()
    logger.info("Deactivated shift shift_id=%d", shift_id)
    return True
