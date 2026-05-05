"""
Downtime Service
Thin service layer wrapping Downtime CRUD operations.
Routes should import from this module instead of backend.crud.downtime directly.
"""

from typing import Any, Optional
from datetime import date
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.crud.downtime import (
    create_downtime_event,
    get_downtime_event,
    get_downtime_events,
    update_downtime_event,
    delete_downtime_event,
)


def create_event(db: Session, downtime_data: Any, current_user: User) -> Any:
    """Create a new downtime event."""
    return create_downtime_event(db, downtime_data, current_user)


def get_event(db: Session, downtime_id: str, current_user: User) -> Any:
    """Get a downtime event by ID."""
    return get_downtime_event(db, downtime_id, current_user)


def list_events(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    downtime_reason: Optional[str] = None,
) -> Any:
    """List downtime events with filters."""
    return get_downtime_events(
        db,
        current_user,
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        client_id=client_id,
        work_order_id=work_order_id,
        downtime_reason=downtime_reason,
    )


def update_event(db: Session, downtime_id: str, downtime_data: Any, current_user: User) -> Any:
    """Update a downtime event."""
    return update_downtime_event(db, downtime_id, downtime_data, current_user)


def delete_event(db: Session, downtime_id: str, current_user: User) -> bool:
    """Delete a downtime event."""
    return delete_downtime_event(db, downtime_id, current_user)
