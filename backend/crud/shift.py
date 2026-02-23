"""
CRUD operations for Shifts.
Supports per-client shift management with soft-delete.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_
from typing import List, Optional
from datetime import time

from backend.orm.shift import Shift
from backend.schemas.shift import ShiftCreate, ShiftUpdate
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)


def _is_overnight(start: time, end: time) -> bool:
    """Return True if a shift crosses midnight (e.g. 22:00-06:00)."""
    return start > end


def _times_overlap(
    start_a: time,
    end_a: time,
    start_b: time,
    end_b: time,
) -> bool:
    """Determine whether two time ranges overlap, handling overnight shifts.

    An overnight shift (start > end, e.g. 22:00-06:00) is treated as two
    logical intervals: [start, 24:00) and [00:00, end).  Two ranges overlap
    when any of their sub-intervals intersect.
    """

    def _segments(s: time, e: time) -> list[tuple[time, time]]:
        """Split a time range into non-overnight segments."""
        if _is_overnight(s, e):
            return [(s, time(23, 59, 59)), (time(0, 0), e)]
        return [(s, e)]

    segs_a = _segments(start_a, end_a)
    segs_b = _segments(start_b, end_b)

    for sa_start, sa_end in segs_a:
        for sb_start, sb_end in segs_b:
            if sa_start < sb_end and sa_end > sb_start:
                return True
    return False


def check_shift_overlaps(
    db: Session,
    client_id: str,
    start_time: time,
    end_time: time,
    exclude_shift_id: Optional[int] = None,
) -> List[Shift]:
    """Check if a shift time range overlaps with existing active shifts for the same client.

    Args:
        db: Database session.
        client_id: The client whose shifts to check against.
        start_time: Proposed shift start time.
        end_time: Proposed shift end time.
        exclude_shift_id: Shift ID to exclude (used when updating a shift so it
            doesn't flag itself).

    Returns:
        List of overlapping Shift ORM objects (empty if no overlaps).
    """
    query = db.query(Shift).filter(
        and_(
            Shift.client_id == client_id,
            Shift.is_active == True,  # noqa: E712
        )
    )
    if exclude_shift_id is not None:
        query = query.filter(Shift.shift_id != exclude_shift_id)

    existing_shifts = query.all()

    overlapping: List[Shift] = []
    for shift in existing_shifts:
        if _times_overlap(start_time, end_time, shift.start_time, shift.end_time):
            overlapping.append(shift)

    if overlapping:
        names = ", ".join(s.shift_name for s in overlapping)
        logger.warning(
            "Shift overlap detected for client '%s': proposed %s-%s overlaps with [%s]",
            client_id,
            start_time,
            end_time,
            names,
        )

    return overlapping


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
