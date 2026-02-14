"""
CRUD operations for Capacity Calendar

Provides operations for managing working days, shifts, and holidays
for capacity planning calculations.

Multi-tenant: All operations enforce client_id isolation.
"""

from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.schemas.capacity.calendar import CapacityCalendar
from backend.utils.tenant_guard import ensure_client_id


def create_calendar_entry(
    db: Session,
    client_id: str,
    calendar_date: date,
    is_working_day: bool = True,
    shifts_available: int = 1,
    shift1_hours: float = 8.0,
    shift2_hours: float = 0,
    shift3_hours: float = 0,
    holiday_name: Optional[str] = None,
    notes: Optional[str] = None,
) -> CapacityCalendar:
    """
    Create a new calendar entry.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        calendar_date: The date for this entry
        is_working_day: Whether this is a working day
        shifts_available: Number of shifts available (1, 2, or 3)
        shift1_hours: Hours for shift 1 (default 8.0)
        shift2_hours: Hours for shift 2 (default 0)
        shift3_hours: Hours for shift 3 (default 0)
        holiday_name: Name of holiday if not a working day
        notes: Additional notes

    Returns:
        Created CapacityCalendar entry
    """
    ensure_client_id(client_id, "calendar entry")

    entry = CapacityCalendar(
        client_id=client_id,
        calendar_date=calendar_date,
        is_working_day=is_working_day,
        shifts_available=shifts_available,
        shift1_hours=shift1_hours,
        shift2_hours=shift2_hours,
        shift3_hours=shift3_hours,
        holiday_name=holiday_name,
        notes=notes,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_calendar_entries(db: Session, client_id: str, skip: int = 0, limit: int = 100) -> List[CapacityCalendar]:
    """
    Get all calendar entries for a client.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        skip: Number of records to skip (pagination)
        limit: Maximum records to return

    Returns:
        List of CapacityCalendar entries ordered by date
    """
    ensure_client_id(client_id, "calendar query")
    return (
        db.query(CapacityCalendar)
        .filter(CapacityCalendar.client_id == client_id)
        .order_by(CapacityCalendar.calendar_date)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_calendar_entry(db: Session, client_id: str, entry_id: int) -> Optional[CapacityCalendar]:
    """
    Get a specific calendar entry by ID.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        entry_id: Calendar entry ID

    Returns:
        CapacityCalendar entry or None if not found
    """
    ensure_client_id(client_id, "calendar query")
    return (
        db.query(CapacityCalendar)
        .filter(and_(CapacityCalendar.client_id == client_id, CapacityCalendar.id == entry_id))
        .first()
    )


def get_calendar_entry_by_date(db: Session, client_id: str, calendar_date: date) -> Optional[CapacityCalendar]:
    """
    Get a specific calendar entry by date.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        calendar_date: The date to look up

    Returns:
        CapacityCalendar entry or None if not found
    """
    ensure_client_id(client_id, "calendar query")
    return (
        db.query(CapacityCalendar)
        .filter(and_(CapacityCalendar.client_id == client_id, CapacityCalendar.calendar_date == calendar_date))
        .first()
    )


def update_calendar_entry(db: Session, client_id: str, entry_id: int, **updates) -> Optional[CapacityCalendar]:
    """
    Update a calendar entry.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        entry_id: Calendar entry ID to update
        **updates: Fields to update (is_working_day, shifts_available, etc.)

    Returns:
        Updated CapacityCalendar entry or None if not found
    """
    entry = get_calendar_entry(db, client_id, entry_id)
    if not entry:
        return None

    for key, value in updates.items():
        if hasattr(entry, key) and value is not None:
            setattr(entry, key, value)

    db.commit()
    db.refresh(entry)
    return entry


def delete_calendar_entry(db: Session, client_id: str, entry_id: int) -> bool:
    """
    Delete a calendar entry.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        entry_id: Calendar entry ID to delete

    Returns:
        True if deleted, False if not found
    """
    entry = get_calendar_entry(db, client_id, entry_id)
    if not entry:
        return False

    db.delete(entry)
    db.commit()
    return True


def get_calendar_for_period(db: Session, client_id: str, start_date: date, end_date: date) -> List[CapacityCalendar]:
    """
    Get calendar entries for a date range.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        List of CapacityCalendar entries for the period, ordered by date
    """
    ensure_client_id(client_id, "calendar period query")
    return (
        db.query(CapacityCalendar)
        .filter(
            and_(
                CapacityCalendar.client_id == client_id,
                CapacityCalendar.calendar_date >= start_date,
                CapacityCalendar.calendar_date <= end_date,
            )
        )
        .order_by(CapacityCalendar.calendar_date)
        .all()
    )


def get_working_days_in_period(db: Session, client_id: str, start_date: date, end_date: date) -> List[CapacityCalendar]:
    """
    Get only working days for a date range.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        List of working day CapacityCalendar entries for the period
    """
    ensure_client_id(client_id, "working days query")
    return (
        db.query(CapacityCalendar)
        .filter(
            and_(
                CapacityCalendar.client_id == client_id,
                CapacityCalendar.calendar_date >= start_date,
                CapacityCalendar.calendar_date <= end_date,
                CapacityCalendar.is_working_day == True,
            )
        )
        .order_by(CapacityCalendar.calendar_date)
        .all()
    )


def get_total_hours_for_period(db: Session, client_id: str, start_date: date, end_date: date) -> float:
    """
    Calculate total available hours for a date range.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)

    Returns:
        Total available hours across all working days in the period
    """
    working_days = get_working_days_in_period(db, client_id, start_date, end_date)
    return sum(day.total_hours() for day in working_days)


def bulk_create_calendar_entries(db: Session, client_id: str, entries: List[dict]) -> List[CapacityCalendar]:
    """
    Bulk create calendar entries.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        entries: List of entry dictionaries with calendar data

    Returns:
        List of created CapacityCalendar entries
    """
    ensure_client_id(client_id, "bulk calendar create")

    created_entries = []
    for entry_data in entries:
        entry = CapacityCalendar(client_id=client_id, **entry_data)
        db.add(entry)
        created_entries.append(entry)

    db.commit()
    for entry in created_entries:
        db.refresh(entry)

    return created_entries
