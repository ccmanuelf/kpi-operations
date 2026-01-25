"""
Downtime Tracking API Routes
All downtime CRUD and availability KPI endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime

from backend.database import get_db
from backend.models.downtime import (
    DowntimeEventCreate,
    DowntimeEventUpdate,
    DowntimeEventResponse,
    AvailabilityCalculationResponse
)
from backend.crud.downtime import (
    create_downtime_event,
    get_downtime_event,
    get_downtime_events,
    update_downtime_event,
    delete_downtime_event
)
from backend.calculations.availability import calculate_availability
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User


router = APIRouter(
    prefix="/api/downtime",
    tags=["Downtime Tracking"]
)


@router.post("", response_model=DowntimeEventResponse, status_code=status.HTTP_201_CREATED)
def create_downtime(
    downtime: DowntimeEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create downtime event"""
    return create_downtime_event(db, downtime, current_user)


@router.get("", response_model=List[DowntimeEventResponse])
def list_downtime(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    downtime_reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List downtime events with filters"""
    return get_downtime_events(
        db, current_user=current_user, skip=skip, limit=limit, start_date=start_date,
        end_date=end_date, client_id=client_id, work_order_id=work_order_id,
        downtime_reason=downtime_reason
    )


@router.get("/{downtime_id}", response_model=DowntimeEventResponse)
def get_downtime(
    downtime_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get downtime event by ID"""
    event = get_downtime_event(db, downtime_id, current_user)
    if not event:
        raise HTTPException(status_code=404, detail="Downtime event not found")
    return event


@router.put("/{downtime_id}", response_model=DowntimeEventResponse)
def update_downtime(
    downtime_id: str,
    downtime_update: DowntimeEventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update downtime event"""
    updated = update_downtime_event(db, downtime_id, downtime_update, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Downtime event not found")
    return updated


@router.delete("/{downtime_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_downtime(
    downtime_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """Delete downtime event (supervisor only)"""
    success = delete_downtime_event(db, downtime_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Downtime event not found")


# Availability KPI endpoint (separate prefix for /api/kpi namespace)
availability_router = APIRouter(
    prefix="/api/kpi",
    tags=["Downtime Tracking"]
)


@availability_router.get("/availability", response_model=AvailabilityCalculationResponse)
def calculate_availability_kpi(
    product_id: int,
    shift_id: int,
    production_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate availability KPI"""
    availability, scheduled, downtime, events = calculate_availability(
        db, product_id, shift_id, production_date
    )

    return AvailabilityCalculationResponse(
        product_id=product_id,
        shift_id=shift_id,
        production_date=production_date,
        total_scheduled_hours=scheduled,
        total_downtime_hours=downtime,
        available_hours=scheduled - downtime,
        availability_percentage=availability,
        downtime_events=events,
        calculation_timestamp=datetime.utcnow()
    )
