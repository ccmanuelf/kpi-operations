"""
CRUD operations for downtime tracking
PHASE 2
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List
from datetime import date
from fastapi import HTTPException

from backend.schemas.downtime import DowntimeEvent
from backend.schemas.downtime import (
    DowntimeEventCreate,
    DowntimeEventUpdate,
    DowntimeEventResponse
)
from middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.schemas.user import User


def create_downtime_event(
    db: Session,
    downtime: DowntimeEventCreate,
    current_user: User
) -> DowntimeEventResponse:
    """Create new downtime event"""
    # Verify user has access to this client
    verify_client_access(current_user, downtime.client_id)

    db_downtime = DowntimeEvent(
        **downtime.dict(),
        entered_by=current_user.user_id
    )

    db.add(db_downtime)
    db.commit()
    db.refresh(db_downtime)

    return DowntimeEventResponse.from_orm(db_downtime)


def get_downtime_event(
    db: Session,
    downtime_id: int,
    current_user: User
) -> Optional[DowntimeEvent]:
    """Get downtime event by ID"""
    db_downtime = db.query(DowntimeEvent).filter(
        DowntimeEvent.downtime_id == downtime_id
    ).first()

    if not db_downtime:
        raise HTTPException(status_code=404, detail="Downtime event not found")

    # Verify user has access to this client
    verify_client_access(current_user, db_downtime.client_id)

    return db_downtime


def get_downtime_events(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    downtime_category: Optional[str] = None
) -> List[DowntimeEvent]:
    """Get downtime events with filters"""
    query = db.query(DowntimeEvent)

    # Apply client filtering based on user role
    client_filter = build_client_filter_clause(current_user, DowntimeEvent.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    if start_date:
        query = query.filter(DowntimeEvent.production_date >= start_date)

    if end_date:
        query = query.filter(DowntimeEvent.production_date <= end_date)

    if product_id:
        query = query.filter(DowntimeEvent.product_id == product_id)

    if shift_id:
        query = query.filter(DowntimeEvent.shift_id == shift_id)

    if downtime_category:
        query = query.filter(DowntimeEvent.downtime_category == downtime_category)

    return query.order_by(
        DowntimeEvent.production_date.desc()
    ).offset(skip).limit(limit).all()


def update_downtime_event(
    db: Session,
    downtime_id: int,
    downtime_update: DowntimeEventUpdate,
    current_user: User
) -> Optional[DowntimeEventResponse]:
    """Update downtime event"""
    db_downtime = get_downtime_event(db, downtime_id, current_user)

    if not db_downtime:
        return None

    update_data = downtime_update.dict(exclude_unset=True)

    # Verify client_id if being updated
    if 'client_id' in update_data:
        verify_client_access(current_user, update_data['client_id'])

    for field, value in update_data.items():
        setattr(db_downtime, field, value)

    db.commit()
    db.refresh(db_downtime)

    return DowntimeEventResponse.from_orm(db_downtime)


def delete_downtime_event(
    db: Session,
    downtime_id: int,
    current_user: User
) -> bool:
    """Delete downtime event"""
    db_downtime = get_downtime_event(db, downtime_id, current_user)

    if not db_downtime:
        return False

    db.delete(db_downtime)
    db.commit()

    return True
