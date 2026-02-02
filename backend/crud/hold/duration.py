"""
CRUD operations for Hold Duration calculations
P2-001: Hold Duration Auto-Calculation functions
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal
from fastapi import HTTPException

from backend.schemas.hold_entry import HoldEntry as WIPHold, HoldStatus
from backend.models.hold import (
    WIPHoldResponse,
    TotalHoldDurationResponse
)
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.schemas.user import User


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
