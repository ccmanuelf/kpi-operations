"""
CRUD core operations for WIP hold tracking
PHASE 2 - Enhanced with P2-001: Hold Duration Auto-Calculation
"""

import uuid
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, datetime, timezone
from fastapi import HTTPException

from backend.orm.hold_entry import HoldEntry as WIPHold, HoldStatus
from backend.schemas.hold import (
    WIPHoldCreate,
    WIPHoldUpdate,
    WIPHoldResponse,
)
from backend.crud.hold.transition_log import record_hold_transition
from backend.middleware.client_auth import verify_client_access
from backend.orm.user import User
from backend.db.soft_delete_service import soft_delete_record


def create_wip_hold(db: Session, hold: WIPHoldCreate, current_user: User) -> WIPHoldResponse:
    """
    Create new WIP hold record with P2-001 hold timestamp tracking.
    Phase 6.2: Approval workflow enforcement.
    - Operators create with PENDING_HOLD_APPROVAL status
    - Supervisors/Admins create with ON_HOLD status (auto-approved)
    """
    # Verify user has access to this client
    verify_client_access(current_user, hold.client_id)

    hold_data = hold.model_dump()

    # Generate hold_entry_id (String PK — no auto-increment)
    hold_data["hold_entry_id"] = f"HOLD-{uuid.uuid4().hex[:8].upper()}"

    # Convert hold_date from date to datetime for the DateTime column
    if hold_data.get("hold_date") is not None:
        hd = hold_data["hold_date"]
        if isinstance(hd, date) and not isinstance(hd, datetime):
            hold_data["hold_date"] = datetime.combine(hd, datetime.min.time())
    else:
        hold_data["hold_date"] = datetime.now(tz=timezone.utc)

    # Convert expected_resolution_date if present
    if hold_data.get("expected_resolution_date") is not None:
        erd = hold_data["expected_resolution_date"]
        if isinstance(erd, date) and not isinstance(erd, datetime):
            hold_data["expected_resolution_date"] = datetime.combine(erd, datetime.min.time())

    # Phase 6.2: Determine initial status based on user role
    # Supervisors and admins can auto-approve holds
    is_supervisor_or_admin = current_user.role in ["admin", "supervisor", "leader", "poweruser"]

    if is_supervisor_or_admin:
        hold_data["hold_status"] = HoldStatus.ON_HOLD
        hold_data["hold_approved_by"] = current_user.user_id  # Auto-approved
    else:
        hold_data["hold_status"] = HoldStatus.PENDING_HOLD_APPROVAL
        hold_data["hold_approved_by"] = None  # Pending approval

    # Normalize hold_reason to a plain string (catalog-driven, no enum conversion)
    if hold_data.get("hold_reason") is not None:
        reason_val = hold_data["hold_reason"]
        if hasattr(reason_val, "value"):
            reason_val = reason_val.value
        hold_data["hold_reason"] = str(reason_val)

    hold_data["hold_initiated_by"] = current_user.user_id

    db_hold = WIPHold(**hold_data)

    db.add(db_hold)
    db.flush()
    db.refresh(db_hold)

    # Stamp the OPENING transition at hold_date, not import time: the CSV
    # importer routinely supplies a past hold_date for back-dated holds, and
    # an append-only history that claims 500 back-dated holds all entered
    # hold "now" is factually false -- every as-of date before the import
    # would then miss them and silently fall into active_as_of's no-history
    # COALESCE fallback. Falls back to the current instant only if hold_date
    # somehow ended up None (it should always be populated above).
    record_hold_transition(
        db,
        db_hold,
        to_status=db_hold.hold_status,
        current_user=current_user,
        from_status=None,
        notes="Hold created",
        transitioned_at=db_hold.hold_date or datetime.now(tz=timezone.utc),
    )

    return WIPHoldResponse.model_validate(db_hold)


def get_wip_hold(db: Session, hold_id: str, current_user: User) -> Optional[WIPHold]:
    """Get WIP hold by ID"""
    db_hold = db.query(WIPHold).filter(WIPHold.hold_entry_id == hold_id).first()

    if not db_hold:
        raise HTTPException(status_code=404, detail="WIP hold not found")

    # Verify user has access to this client
    verify_client_access(current_user, db_hold.client_id)

    return db_hold


def update_wip_hold(
    db: Session, hold_id: str, hold_update: WIPHoldUpdate, current_user: User
) -> Optional[WIPHoldResponse]:
    """Update WIP hold record"""
    db_hold = get_wip_hold(db, hold_id, current_user)

    if not db_hold:
        return None

    update_data = hold_update.model_dump(exclude_unset=True)

    # Verify client_id if being updated
    if "client_id" in update_data:
        verify_client_access(current_user, update_data["client_id"])

    # Update aging if resume date is set. hold_date is Optional[datetime]
    # in the ORM, so guard before computing the delta — the column should
    # always be populated by create_wip_hold, but a partial fixture could
    # carry None and we don't want a TypeError surfacing as a 500.
    if db_hold.hold_date is not None:
        if "resume_date" in update_data and update_data["resume_date"]:
            update_data["aging_days"] = (update_data["resume_date"] - db_hold.hold_date).days
        elif not db_hold.resume_date:
            # Update aging for unresumed holds. Compare on hold_date itself
            # (datetime - datetime) so we don't trip the date-vs-datetime
            # subtype mismatch the previous code had.
            update_data["aging_days"] = (datetime.now(tz=db_hold.hold_date.tzinfo) - db_hold.hold_date).days

    # No record_hold_transition call here: WIPHoldUpdate has no field that
    # maps to hold_status, so this loop can never write that column. If a
    # future WIPHoldUpdate field ever does map to hold_status, this dynamic
    # setattr would write it silently -- the static write-site guard
    # (test_every_hold_status_write_site_is_instrumented) does not scan
    # dynamic setattr-over-dict loops like this one, so it would not catch
    # the gap either.
    for field, value in update_data.items():
        setattr(db_hold, field, value)

    db.flush()
    db.refresh(db_hold)

    return WIPHoldResponse.model_validate(db_hold)


def delete_wip_hold(db: Session, hold_id: str, current_user: User) -> bool:
    """Soft delete WIP hold record (sets is_active = False)"""
    db_hold = get_wip_hold(db, hold_id, current_user)

    if not db_hold:
        return False

    # Soft delete - preserves data integrity (commit=False: route handler commits)
    return soft_delete_record(db, db_hold, current_user, commit=False)
