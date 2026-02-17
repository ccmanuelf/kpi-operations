"""
Capacity Planning - Calendar Endpoints

Master Calendar (working days, shifts, holidays) CRUD operations.
"""

import logging
from typing import List, Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.constants import DEFAULT_PAGE_SIZE
from backend.crud.capacity import calendar

from ._models import (
    CalendarEntryCreate,
    CalendarEntryUpdate,
    CalendarEntryResponse,
    MessageResponse,
)

logger = logging.getLogger(__name__)

calendar_router = APIRouter()


@calendar_router.get("/calendar", response_model=List[CalendarEntryResponse])
def list_calendar_entries(
    client_id: str = Query(..., description="Client ID"),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get calendar entries for a client."""
    verify_client_access(current_user, client_id, db)
    if start_date and end_date:
        return calendar.get_calendar_for_period(db, client_id, start_date, end_date)
    return calendar.get_calendar_entries(db, client_id, skip, limit)


@calendar_router.post("/calendar", response_model=CalendarEntryResponse, status_code=status.HTTP_201_CREATED)
def create_calendar(
    entry: CalendarEntryCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new calendar entry."""
    verify_client_access(current_user, client_id, db)
    return calendar.create_calendar_entry(
        db,
        client_id,
        entry.calendar_date,
        entry.is_working_day,
        entry.shifts_available,
        entry.shift1_hours,
        entry.shift2_hours,
        entry.shift3_hours,
        entry.holiday_name,
        entry.notes,
    )


@calendar_router.get("/calendar/{entry_id}", response_model=CalendarEntryResponse, responses={404: {"description": "Calendar entry not found"}})
def get_calendar(
    entry_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific calendar entry."""
    verify_client_access(current_user, client_id, db)
    entry = calendar.get_calendar_entry(db, client_id, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    return entry


@calendar_router.put("/calendar/{entry_id}", response_model=CalendarEntryResponse, responses={404: {"description": "Calendar entry not found"}})
def update_calendar(
    entry_id: int,
    update: CalendarEntryUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a calendar entry."""
    verify_client_access(current_user, client_id, db)
    entry = calendar.update_calendar_entry(db, client_id, entry_id, **update.model_dump(exclude_unset=True))
    if not entry:
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    return entry


@calendar_router.delete("/calendar/{entry_id}", response_model=MessageResponse, responses={404: {"description": "Calendar entry not found"}})
def delete_calendar(
    entry_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a calendar entry."""
    verify_client_access(current_user, client_id, db)
    if not calendar.delete_calendar_entry(db, client_id, entry_id):
        raise HTTPException(status_code=404, detail="Calendar entry not found")
    return {"message": "Calendar entry deleted"}
