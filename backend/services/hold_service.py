"""
Hold Service
Thin service layer wrapping WIP Hold CRUD operations.
Routes should import from this module instead of backend.crud.hold directly.
"""

from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.crud.hold import (
    create_wip_hold,
    get_wip_hold,
    get_wip_holds,
    update_wip_hold,
    delete_wip_hold,
)
from backend.crud.hold_catalog import (
    validate_hold_status_for_client,
    validate_hold_reason_for_client,
)


def create_hold(db: Session, hold_data, current_user: User):
    """Create a new WIP hold."""
    return create_wip_hold(db, hold_data, current_user)


def get_hold(db: Session, hold_id: str, current_user: User):
    """Get a WIP hold by ID."""
    return get_wip_hold(db, hold_id, current_user)


def list_holds(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    released: Optional[bool] = None,
    hold_reason_category: Optional[str] = None,
):
    """List WIP holds with filters."""
    return get_wip_holds(
        db,
        current_user,
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        client_id=client_id,
        work_order_id=work_order_id,
        released=released,
        hold_reason_category=hold_reason_category,
    )


def update_hold(db: Session, hold_id: str, hold_data: dict, current_user: User):
    """Update a WIP hold."""
    return update_wip_hold(db, hold_id, hold_data, current_user)


def delete_hold(db: Session, hold_id: str, current_user: User) -> bool:
    """Delete a WIP hold."""
    return delete_wip_hold(db, hold_id, current_user)


def validate_status_for_client(db: Session, client_id: str, status_code: str) -> bool:
    """Validate a hold status exists for a client."""
    return validate_hold_status_for_client(db, client_id, status_code)


def validate_reason_for_client(db: Session, client_id: str, reason_code: str) -> bool:
    """Validate a hold reason exists for a client."""
    return validate_hold_reason_for_client(db, client_id, reason_code)
