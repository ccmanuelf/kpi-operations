"""
CRUD operations for WIP hold tracking
PHASE 2
Enhanced with P2-001: Hold Duration Auto-Calculation
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from fastapi import HTTPException

from backend.schemas.hold_entry import HoldEntry as WIPHold, HoldStatus
from backend.models.hold import (
    WIPHoldCreate,
    WIPHoldUpdate,
    WIPHoldResponse,
    TotalHoldDurationResponse
)
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
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


def get_wip_holds(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    released: Optional[bool] = None,
    hold_reason_category: Optional[str] = None
) -> List[WIPHold]:
    """Get WIP holds with filters - uses HOLD_ENTRY schema"""
    query = db.query(WIPHold)

    # Apply client filtering based on user role
    client_filter = build_client_filter_clause(current_user, WIPHold.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Additional client filter if provided
    if client_id:
        query = query.filter(WIPHold.client_id == client_id)

    if start_date:
        query = query.filter(WIPHold.hold_date >= start_date)

    if end_date:
        query = query.filter(WIPHold.hold_date <= end_date)

    if work_order_id:
        query = query.filter(WIPHold.work_order_id == work_order_id)

    if released is not None:
        if released:
            query = query.filter(WIPHold.hold_status == HoldStatus.RESUMED)
        else:
            query = query.filter(WIPHold.hold_status == HoldStatus.ON_HOLD)

    if hold_reason_category:
        query = query.filter(WIPHold.hold_reason_category == hold_reason_category)

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


def bulk_update_aging(db: Session, current_user: User) -> int:
    """Update aging for all unreleased holds (batch job)"""
    query = db.query(WIPHold).filter(WIPHold.resume_date.is_(None))

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


# =============================================================================
# P2-001: Hold Duration Auto-Calculation Functions
# =============================================================================

def resume_hold(
    db: Session,
    hold_id: int,
    resumed_by: int,
    current_user: User,
    notes: Optional[str] = None
) -> Optional[WIPHoldResponse]:
    """
    Resume a hold and auto-calculate hold duration
    P2-001: Hold Duration Auto-Calculation

    Args:
        db: Database session
        hold_id: ID of the hold to resume
        resumed_by: User ID who is resuming
        current_user: Authenticated user for access control
        notes: Optional notes about resumption

    Returns:
        Updated WIPHoldResponse with calculated duration
    """
    # Get the hold record
    db_hold = db.query(WIPHold).filter(WIPHold.hold_entry_id == hold_id).first()

    if not db_hold:
        raise HTTPException(status_code=404, detail="WIP hold not found")

    # Verify user has access to this client
    verify_client_access(current_user, db_hold.client_id)

    # Check if hold is in ON_HOLD status
    if db_hold.hold_status != HoldStatus.ON_HOLD:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume hold with status {db_hold.hold_status}. Only ON_HOLD status can be resumed."
        )

    # Set resume timestamp
    db_hold.resume_timestamp = datetime.now()
    db_hold.resumed_by = resumed_by
    db_hold.hold_status = HoldStatus.RESUMED

    # AUTO-CALCULATE hold duration (P2-001)
    if db_hold.hold_timestamp:
        delta = db_hold.resume_timestamp - db_hold.hold_timestamp
        db_hold.total_hold_duration_hours = Decimal(str(delta.total_seconds() / 3600))
    else:
        # Fallback: Calculate from hold_date if no timestamp available
        # Use midnight of hold_date as start
        hold_start = datetime.combine(db_hold.hold_date, datetime.min.time())
        delta = db_hold.resume_timestamp - hold_start
        db_hold.total_hold_duration_hours = Decimal(str(delta.total_seconds() / 3600))

    # Update notes if provided
    if notes:
        existing_notes = db_hold.notes or ""
        db_hold.notes = f"{existing_notes}\n[RESUMED] {notes}".strip()

    db.commit()
    db.refresh(db_hold)

    return WIPHoldResponse.model_validate(db_hold)


def get_total_hold_duration(
    db: Session,
    work_order_number: str,
    current_user: Optional[User] = None
) -> TotalHoldDurationResponse:
    """
    Get total hold duration for a work order across all holds
    P2-001: Required for WIP aging adjustment

    Args:
        db: Database session
        work_order_number: Work order number to query
        current_user: Optional user for access filtering

    Returns:
        TotalHoldDurationResponse with aggregated duration
    """
    query = db.query(WIPHold).filter(
        WIPHold.work_order_id == work_order_number
    )

    # Apply client filtering if user provided
    if current_user:
        client_filter = build_client_filter_clause(current_user, WIPHold.client_id)
        if client_filter is not None:
            query = query.filter(client_filter)

    holds = query.all()

    total_duration = Decimal("0")
    active_holds = 0
    hold_count = len(holds)

    for hold in holds:
        # Count active (ON_HOLD) holds
        if hold.hold_status == HoldStatus.ON_HOLD:
            active_holds += 1
            # For active holds, calculate duration from hold_timestamp to now
            if hold.hold_timestamp:
                delta = datetime.now() - hold.hold_timestamp
                total_duration += Decimal(str(delta.total_seconds() / 3600))
            elif hold.hold_date:
                # Fallback to hold_date
                hold_start = datetime.combine(hold.hold_date, datetime.min.time())
                delta = datetime.now() - hold_start
                total_duration += Decimal(str(delta.total_seconds() / 3600))
        else:
            # For completed holds, use stored duration
            if hold.total_hold_duration_hours:
                total_duration += hold.total_hold_duration_hours

    return TotalHoldDurationResponse(
        work_order_number=work_order_number,
        total_hold_duration_hours=total_duration.quantize(Decimal("0.0001")),
        hold_count=hold_count,
        active_holds=active_holds
    )


def get_holds_by_work_order(
    db: Session,
    work_order_number: str,
    current_user: User
) -> List[WIPHoldResponse]:
    """
    Get all holds for a specific work order
    P2-001: Helper function for WIP aging

    Args:
        db: Database session
        work_order_number: Work order number
        current_user: Authenticated user

    Returns:
        List of WIPHoldResponse for the work order
    """
    query = db.query(WIPHold).filter(
        WIPHold.work_order_id == work_order_number
    )

    # Apply client filtering
    client_filter = build_client_filter_clause(current_user, WIPHold.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    holds = query.order_by(WIPHold.hold_date.desc()).all()

    return [WIPHoldResponse.model_validate(h) for h in holds]


def release_hold(
    db: Session,
    hold_id: int,
    current_user: User,
    quantity_released: Optional[int] = None,
    quantity_scrapped: Optional[int] = None,
    notes: Optional[str] = None
) -> Optional[WIPHoldResponse]:
    """
    Release a hold (marks as RELEASED status)
    P2-001: Ensures duration is calculated before release

    Args:
        db: Database session
        hold_id: ID of the hold to release
        current_user: Authenticated user
        quantity_released: Quantity being released
        quantity_scrapped: Quantity being scrapped
        notes: Optional notes

    Returns:
        Updated WIPHoldResponse
    """
    db_hold = db.query(WIPHold).filter(WIPHold.hold_entry_id == hold_id).first()

    if not db_hold:
        raise HTTPException(status_code=404, detail="WIP hold not found")

    verify_client_access(current_user, db_hold.client_id)

    # Set release info
    db_hold.resume_date = date.today()
    db_hold.hold_status = HoldStatus.RESUMED
    db_hold.actual_resolution_date = date.today()

    if quantity_released is not None:
        db_hold.quantity_released = quantity_released
    if quantity_scrapped is not None:
        db_hold.quantity_scrapped = quantity_scrapped

    # Calculate final duration if not already calculated
    if db_hold.total_hold_duration_hours is None:
        now = datetime.now()
        if db_hold.hold_timestamp:
            delta = now - db_hold.hold_timestamp
            db_hold.total_hold_duration_hours = Decimal(str(delta.total_seconds() / 3600))
        elif db_hold.hold_date:
            hold_start = datetime.combine(db_hold.hold_date, datetime.min.time())
            delta = now - hold_start
            db_hold.total_hold_duration_hours = Decimal(str(delta.total_seconds() / 3600))

    # Update aging
    db_hold.aging_days = (db_hold.resume_date - db_hold.hold_date).days

    if notes:
        existing_notes = db_hold.notes or ""
        db_hold.notes = f"{existing_notes}\n[RELEASED] {notes}".strip()

    db.commit()
    db.refresh(db_hold)

    return WIPHoldResponse.model_validate(db_hold)
