"""
Operational Calendar API Routes

Exposes CapacityCalendar data for operational KPI context.
This is a read-only thin wrapper around the capacity calendar CRUD layer,
providing working-day/holiday information to KPI dashboards and other
operational consumers that do not need full capacity planning access.

All endpoints require authentication (any role) and enforce multi-tenant
isolation via the required client_id query parameter.
"""

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_user
from backend.crud.capacity.calendar import (
    get_calendar_entry_by_date,
    get_calendar_for_period,
)
from backend.database import get_db
from backend.schemas.user import User
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/calendar", tags=["Calendar"])


# =============================================================================
# Response Models
# =============================================================================


class WorkingDayEntry(BaseModel):
    """Single calendar day in the working-days list."""

    calendar_date: date = Field(description="Calendar date")
    is_working_day: bool = Field(description="Whether this is a working day")
    holiday_name: Optional[str] = Field(description="Holiday name, or null")
    shifts_available: int = Field(description="Number of shifts configured for this day")
    planned_hours: float = Field(description="Total planned hours across all shifts")


class HolidayInfo(BaseModel):
    """Holiday entry for the summary response."""

    holiday_date: date = Field(description="Date of the holiday")
    name: str = Field(description="Holiday name")


class CalendarSummary(BaseModel):
    """Aggregated calendar summary for a date range."""

    total_days: int = Field(description="Total calendar entries in the range")
    working_days: int = Field(description="Number of working days")
    non_working_days: int = Field(description="Number of non-working days")
    holidays: List[HolidayInfo] = Field(description="List of holidays in the range")
    total_planned_hours: float = Field(description="Sum of planned hours across all working days")


class SingleDayResponse(BaseModel):
    """Detailed information for a single calendar date."""

    calendar_date: date = Field(description="Calendar date")
    is_working_day: bool = Field(description="Whether this is a working day")
    holiday_name: Optional[str] = Field(description="Holiday name, or null")
    shifts_available: int = Field(description="Number of shifts configured")
    planned_hours: float = Field(description="Total planned hours across all shifts")
    shift1_hours: float = Field(description="Hours for shift 1")
    shift2_hours: float = Field(description="Hours for shift 2")
    shift3_hours: float = Field(description="Hours for shift 3")
    notes: Optional[str] = Field(description="Additional notes")


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/working-days", response_model=List[WorkingDayEntry])
def get_working_days(
    client_id: str = Query(..., description="Client ID for multi-tenant isolation"),
    start_date: date = Query(..., description="Start of date range (inclusive)"),
    end_date: date = Query(..., description="End of date range (inclusive)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return calendar entries for a date range with working/non-working status.

    Returns an empty list when no calendar data exists for the requested range.
    """
    logger.info(
        "GET /working-days requested",
        extra={"client_id": client_id, "start_date": str(start_date), "end_date": str(end_date)},
    )

    entries = get_calendar_for_period(db, client_id, start_date, end_date)

    return [
        WorkingDayEntry(
            calendar_date=entry.calendar_date,
            is_working_day=entry.is_working_day,
            holiday_name=entry.holiday_name,
            shifts_available=entry.shifts_available,
            planned_hours=entry.total_hours(),
        )
        for entry in entries
    ]


@router.get("/summary", response_model=CalendarSummary)
def get_summary(
    client_id: str = Query(..., description="Client ID for multi-tenant isolation"),
    start_date: date = Query(..., description="Start of date range (inclusive)"),
    end_date: date = Query(..., description="End of date range (inclusive)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return an aggregated summary (working days, hours, holidays) for a date range.
    """
    logger.info(
        "GET /summary requested",
        extra={"client_id": client_id, "start_date": str(start_date), "end_date": str(end_date)},
    )

    entries = get_calendar_for_period(db, client_id, start_date, end_date)

    working = [e for e in entries if e.is_working_day]
    non_working = [e for e in entries if not e.is_working_day]
    holidays = [
        HolidayInfo(holiday_date=e.calendar_date, name=e.holiday_name)
        for e in entries
        if e.holiday_name
    ]
    total_planned = sum(e.total_hours() for e in entries)

    return CalendarSummary(
        total_days=len(entries),
        working_days=len(working),
        non_working_days=len(non_working),
        holidays=holidays,
        total_planned_hours=total_planned,
    )


@router.get("/{calendar_date}", response_model=SingleDayResponse)
def get_single_day(
    calendar_date: date,
    client_id: str = Query(..., description="Client ID for multi-tenant isolation"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return detailed information for a single calendar date.

    Returns 404 if no calendar entry exists for the given date and client.
    """
    logger.info(
        "GET /{calendar_date} requested",
        extra={"client_id": client_id, "calendar_date": str(calendar_date)},
    )

    entry = get_calendar_entry_by_date(db, client_id, calendar_date)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No calendar entry found for {calendar_date}",
        )

    return SingleDayResponse(
        calendar_date=entry.calendar_date,
        is_working_day=entry.is_working_day,
        holiday_name=entry.holiday_name,
        shifts_available=entry.shifts_available,
        planned_hours=entry.total_hours(),
        shift1_hours=float(entry.shift1_hours or 0),
        shift2_hours=float(entry.shift2_hours or 0),
        shift3_hours=float(entry.shift3_hours or 0),
        notes=entry.notes,
    )
