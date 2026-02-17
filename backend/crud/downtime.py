"""
CRUD operations for downtime tracking
PHASE 2
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional, List
from datetime import date
from fastapi import HTTPException

from backend.schemas.downtime_entry import DowntimeEntry
from backend.models.downtime import DowntimeEventCreate, DowntimeEventUpdate, DowntimeEventResponse
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.schemas.user import User
from backend.utils.soft_delete import soft_delete


def create_downtime_event(db: Session, downtime: DowntimeEventCreate, current_user: User) -> DowntimeEventResponse:
    """Create new downtime event"""
    # Verify user has access to this client
    verify_client_access(current_user, downtime.client_id)

    db_downtime = DowntimeEntry(**downtime.model_dump(), entered_by=current_user.user_id)

    db.add(db_downtime)
    db.commit()
    db.refresh(db_downtime)

    return DowntimeEventResponse.from_orm(db_downtime)


def get_downtime_event(db: Session, downtime_id: str, current_user: User) -> Optional[DowntimeEntry]:
    """Get downtime event by ID"""
    db_downtime = db.query(DowntimeEntry).filter(DowntimeEntry.downtime_entry_id == downtime_id).first()

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
    client_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    downtime_reason: Optional[str] = None,
) -> List[DowntimeEntry]:
    """Get downtime events with filters"""
    query = db.query(DowntimeEntry)

    # Apply client filtering based on user role
    client_filter = build_client_filter_clause(current_user, DowntimeEntry.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    if client_id:
        query = query.filter(DowntimeEntry.client_id == client_id)

    if start_date:
        query = query.filter(DowntimeEntry.shift_date >= start_date)

    if end_date:
        query = query.filter(DowntimeEntry.shift_date <= end_date)

    if work_order_id:
        query = query.filter(DowntimeEntry.work_order_id == work_order_id)

    if downtime_reason:
        query = query.filter(DowntimeEntry.downtime_reason == downtime_reason)

    return query.order_by(DowntimeEntry.shift_date.desc()).offset(skip).limit(limit).all()


def update_downtime_event(
    db: Session, downtime_id: str, downtime_update: DowntimeEventUpdate, current_user: User
) -> Optional[DowntimeEventResponse]:
    """Update downtime event"""
    db_downtime = get_downtime_event(db, downtime_id, current_user)

    if not db_downtime:
        return None

    update_data = downtime_update.model_dump(exclude_unset=True)

    # Verify client_id if being updated
    if "client_id" in update_data:
        verify_client_access(current_user, update_data["client_id"])

    for field, value in update_data.items():
        setattr(db_downtime, field, value)

    db.commit()
    db.refresh(db_downtime)

    return DowntimeEventResponse.from_orm(db_downtime)


def delete_downtime_event(db: Session, downtime_id: str, current_user: User) -> bool:
    """Soft delete downtime event (sets is_active = False)"""
    db_downtime = get_downtime_event(db, downtime_id, current_user)

    if not db_downtime:
        return False

    # Soft delete - preserves data integrity
    return soft_delete(db, db_downtime)
