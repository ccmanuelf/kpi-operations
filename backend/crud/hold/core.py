"""
CRUD core operations for WIP hold tracking
PHASE 2 - Enhanced with P2-001: Hold Duration Auto-Calculation
"""
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from fastapi import HTTPException

from backend.schemas.hold_entry import HoldEntry as WIPHold, HoldStatus
from backend.models.hold import (
    WIPHoldCreate,
    WIPHoldUpdate,
    WIPHoldResponse,
)
from backend.middleware.client_auth import verify_client_access
from backend.schemas.user import User
from backend.utils.soft_delete import soft_delete


def create_wip_hold(
    db: Session,
    hold: WIPHoldCreate,
    current_user: User
) -> WIPHoldResponse:
    """
    Create new WIP hold record with P2-001 hold timestamp tracking.
    Phase 6.2: Approval workflow enforcement.
    - Operators create with PENDING_HOLD_APPROVAL status
    - Supervisors/Admins create with ON_HOLD status (auto-approved)
    """
    # Verify user has access to this client
    verify_client_access(current_user, hold.client_id)

    # Calculate initial aging
    aging_days = (date.today() - hold.hold_date).days

    # P2-001: Set hold_timestamp to now if not provided
    hold_data = hold.model_dump()
    if hold_data.get('hold_timestamp') is None:
        hold_data['hold_timestamp'] = datetime.now()

    # Phase 6.2: Determine initial status based on user role
    # Supervisors and admins can auto-approve holds
    is_supervisor_or_admin = current_user.role in ['admin', 'supervisor', 'leader', 'poweruser']

    if is_supervisor_or_admin:
        initial_status = HoldStatus.ON_HOLD
        hold_approved_by = current_user.user_id  # Auto-approved
    else:
        initial_status = HoldStatus.PENDING_HOLD_APPROVAL
        hold_approved_by = None  # Pending approval

    db_hold = WIPHold(
        **hold_data,
        aging_days=aging_days,
        entered_by=current_user.user_id,
        status=initial_status,
        hold_approved_by=hold_approved_by
    )

    db.add(db_hold)
    db.commit()
    db.refresh(db_hold)

    return WIPHoldResponse.model_validate(db_hold)


def get_wip_hold(
    db: Session,
    hold_id: str,
    current_user: User
) -> Optional[WIPHold]:
    """Get WIP hold by ID"""
    db_hold = db.query(WIPHold).filter(WIPHold.hold_entry_id == hold_id).first()

    if not db_hold:
        raise HTTPException(status_code=404, detail="WIP hold not found")

    # Verify user has access to this client
    verify_client_access(current_user, db_hold.client_id)

    return db_hold


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

    # Update aging if resume date is set
    if 'resume_date' in update_data and update_data['resume_date']:
        update_data['aging_days'] = (
            update_data['resume_date'] - db_hold.hold_date
        ).days
    elif not db_hold.resume_date:
        # Update aging for unresumed holds
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
    """Soft delete WIP hold record (sets is_active = False)"""
    db_hold = get_wip_hold(db, hold_id, current_user)

    if not db_hold:
        return False

    # Soft delete - preserves data integrity
    return soft_delete(db, db_hold)
