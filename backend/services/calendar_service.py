"""
Calendar Service
Thin service layer for operational calendar access.
Routes should import from this module instead of backend.crud.capacity.calendar directly.

This wraps the capacity calendar CRUD functions for use by operational routes
(not the capacity planning routes which have their own service layer).
"""

from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session

from backend.crud.capacity.calendar import (
    get_calendar_entry_by_date,
    get_calendar_for_period,
)


def get_calendar_entry(db: Session, client_id: str, entry_date: date):
    """Get a calendar entry for a specific date."""
    return get_calendar_entry_by_date(db, client_id, entry_date)


def get_calendar_period(db: Session, client_id: str, start_date: date, end_date: date):
    """Get calendar entries for a date range."""
    return get_calendar_for_period(db, client_id, start_date, end_date)
