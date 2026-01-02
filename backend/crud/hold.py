"""
CRUD operations for WIP hold tracking
PHASE 2
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date
from fastapi import HTTPException

from backend.schemas.hold import WIPHold
from backend.models.hold import (
    WIPHoldCreate,
    WIPHoldUpdate,
    WIPHoldResponse
)
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.schemas.user import User


def create_wip_hold(
    db: Session,
    hold: WIPHoldCreate,
    current_user: User
) -> WIPHoldResponse:
    """Create new WIP hold record"""
    # Verify user has access to this client
    verify_client_access(current_user, hold.client_id)

    # Calculate initial aging
    aging_days = (date.today() - hold.hold_date).days

    db_hold = WIPHold(
        **hold.dict(),
        aging_days=aging_days,
        entered_by=current_user.user_id
    )

    db.add(db_hold)
    db.commit()
    db.refresh(db_hold)

    return WIPHoldResponse.from_orm(db_hold)


def get_wip_hold(
    db: Session,
    hold_id: int,
    current_user: User
) -> Optional[WIPHold]:
    """Get WIP hold by ID"""
    db_hold = db.query(WIPHold).filter(WIPHold.hold_id == hold_id).first()

    if not db_hold:
        raise HTTPException(status_code=404, detail="WIP hold not found")

    # Verify user has access to this client
    verify_client_access(current_user, db_hold.client_id)

    return db_hold


def get_wip_holds(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    released: Optional[bool] = None,
    hold_category: Optional[str] = None
) -> List[WIPHold]:
    """Get WIP holds with filters"""
    query = db.query(WIPHold)

    # Apply client filtering based on user role
    client_filter = build_client_filter_clause(current_user, WIPHold.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    if start_date:
        query = query.filter(WIPHold.hold_date >= start_date)

    if end_date:
        query = query.filter(WIPHold.hold_date <= end_date)

    if product_id:
        query = query.filter(WIPHold.product_id == product_id)

    if shift_id:
        query = query.filter(WIPHold.shift_id == shift_id)

    if released is not None:
        if released:
            query = query.filter(WIPHold.release_date.isnot(None))
        else:
            query = query.filter(WIPHold.release_date.is_(None))

    if hold_category:
        query = query.filter(WIPHold.hold_category == hold_category)

    return query.order_by(
        WIPHold.hold_date.desc()
    ).offset(skip).limit(limit).all()


def update_wip_hold(
    db: Session,
    hold_id: int,
    hold_update: WIPHoldUpdate,
    current_user: User
) -> Optional[WIPHoldResponse]:
    """Update WIP hold record"""
    db_hold = get_wip_hold(db, hold_id, current_user)

    if not db_hold:
        return None

    update_data = hold_update.dict(exclude_unset=True)

    # Verify client_id if being updated
    if 'client_id' in update_data:
        verify_client_access(current_user, update_data['client_id'])

    # Update aging if release date is set
    if 'release_date' in update_data and update_data['release_date']:
        update_data['aging_days'] = (
            update_data['release_date'] - db_hold.hold_date
        ).days
    elif not db_hold.release_date:
        # Update aging for unreleased holds
        update_data['aging_days'] = (date.today() - db_hold.hold_date).days

    for field, value in update_data.items():
        setattr(db_hold, field, value)

    db.commit()
    db.refresh(db_hold)

    return WIPHoldResponse.from_orm(db_hold)


def delete_wip_hold(
    db: Session,
    hold_id: int,
    current_user: User
) -> bool:
    """Delete WIP hold record"""
    db_hold = get_wip_hold(db, hold_id, current_user)

    if not db_hold:
        return False

    db.delete(db_hold)
    db.commit()

    return True


def bulk_update_aging(db: Session, current_user: User) -> int:
    """Update aging for all unreleased holds (batch job)"""
    query = db.query(WIPHold).filter(WIPHold.release_date.is_(None))

    # Apply client filtering based on user role
    client_filter = build_client_filter_clause(current_user, WIPHold.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    holds = query.all()

    count = 0
    for hold in holds:
        hold.aging_days = (date.today() - hold.hold_date).days
        count += 1

    db.commit()
    return count
