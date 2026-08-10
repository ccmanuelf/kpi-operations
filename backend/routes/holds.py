"""
WIP Hold Tracking API Routes
All holds CRUD and WIP aging KPI endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime, timedelta, timezone

from backend.database import get_db
from backend.db.sql_functions import date_diff_days
from backend.orm.hold_entry import HoldEntry
from backend.schemas.hold import WIPHoldCreate, WIPHoldUpdate, WIPHoldResponse, WIPAgingResponse
from backend.services.hold_service import (
    create_hold as create_wip_hold,
    get_hold as get_wip_hold,
    list_holds as get_wip_holds,
    update_hold as update_wip_hold,
    delete_hold as delete_wip_hold,
    validate_reason_for_client as validate_hold_reason_for_client,
)
from backend.calculations.wip_aging import identify_chronic_holds
from backend.auth.jwt import (
    get_current_active_supervisor,
    get_current_contributor,
    get_current_user,
    ClientScope,
    resolve_client_scope,
)
from backend.middleware.client_auth import verify_client_access
from backend.orm.user import User
from backend.constants import DEFAULT_PAGE_SIZE, SMALL_PAGE_SIZE, LOOKBACK_MONTHLY_DAYS
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/holds", tags=["WIP Holds"])


@router.post("", response_model=WIPHoldResponse, status_code=status.HTTP_201_CREATED)
def create_hold(
    hold: WIPHoldCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_contributor)
) -> WIPHoldResponse:
    """
    Create WIP hold record.

    Creates a new hold entry for a work order, recording the hold reason
    and initiating the approval workflow.
    Validates hold_status and hold_reason against the client's catalog.

    SECURITY: Requires authentication; client access verified in CRUD layer.
    """
    # Validate hold_reason against catalog (if provided)
    if hold.hold_reason and not validate_hold_reason_for_client(db, hold.client_id, hold.hold_reason):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Reason '{hold.hold_reason}' not found in client catalog",
        )

    result = create_wip_hold(db, hold, current_user)
    db.commit()
    return result


@router.get("", response_model=List[WIPHoldResponse])
def list_holds(
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    released: Optional[bool] = None,
    hold_reason_category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[HoldEntry]:
    """List WIP holds with filters - uses HOLD_ENTRY schema"""
    from backend.utils.date_range import validate_date_range

    # Reject reversed range (Run-6 audit R6-D-001) before defaulting.
    validate_date_range(start_date, end_date)
    return get_wip_holds(
        db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        client_id=client_id,
        work_order_id=work_order_id,
        released=released,
        hold_reason_category=hold_reason_category,
    )


@router.get("/active", response_model=List[WIPHoldResponse])
def list_active_holds(
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[HoldEntry]:
    """List all active (unreleased) WIP holds"""
    return get_wip_holds(db, current_user=current_user, skip=skip, limit=limit, client_id=client_id, released=False)


@router.get("/{hold_id}", response_model=WIPHoldResponse)
def get_hold(
    hold_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> WIPHoldResponse:
    """
    Get WIP hold by ID.

    Returns the full hold record including status, dates, and approval details.

    SECURITY: Requires authentication; client access verified in CRUD layer.
    """
    hold = get_wip_hold(db, hold_id, current_user)
    if not hold:
        raise HTTPException(status_code=404, detail="WIP hold not found")
    return hold


@router.put("/{hold_id}", response_model=WIPHoldResponse)
def update_hold(
    hold_id: str,
    hold_update: WIPHoldUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_contributor),
) -> WIPHoldResponse:
    """Update WIP hold record. Validates hold_reason against catalog if provided."""
    # Validate hold_reason against catalog when updating
    if hold_update.hold_reason:
        # Need to resolve client_id from the existing hold
        existing = get_wip_hold(db, hold_id, current_user)
        if existing and not validate_hold_reason_for_client(db, existing.client_id, hold_update.hold_reason):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Reason '{hold_update.hold_reason}' not found in client catalog",
            )

    updated = update_wip_hold(db, hold_id, hold_update, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="WIP hold not found")
    db.commit()
    return updated


@router.delete("/{hold_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hold(
    hold_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_supervisor)
) -> None:
    """Delete WIP hold (supervisor only)"""
    success = delete_wip_hold(db, hold_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="WIP hold not found")
    db.commit()


# =============================================================================
# Hold/Resume Approval Workflow Endpoints (Phase 6.2)
# =============================================================================


@router.post("/{hold_id}/approve-hold", response_model=WIPHoldResponse)
def approve_hold(
    hold_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_supervisor)
) -> WIPHoldResponse:
    """
    Approve a pending hold request (supervisor only).
    Transitions hold from PENDING_HOLD_APPROVAL to ON_HOLD.
    """
    from backend.orm.hold_entry import HoldEntry, HoldStatus

    db_hold = db.query(HoldEntry).filter(HoldEntry.hold_entry_id == hold_id).first()
    if not db_hold:
        raise HTTPException(status_code=404, detail="WIP hold not found")

    # Verify caller has access to this hold's client
    verify_client_access(current_user, db_hold.client_id, db)

    # Validate status transition
    if db_hold.hold_status != HoldStatus.PENDING_HOLD_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot approve hold with status {db_hold.hold_status}. " "Only PENDING_HOLD_APPROVAL can be approved."
            ),
        )

    # Approve the hold
    db_hold.hold_status = HoldStatus.ON_HOLD
    db_hold.hold_approved_by = current_user.user_id
    db_hold.updated_by = current_user.user_id

    db.commit()
    db.refresh(db_hold)

    return db_hold


@router.post("/{hold_id}/request-resume", response_model=WIPHoldResponse)
def request_resume(
    hold_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_contributor)
) -> WIPHoldResponse:
    """
    Request to resume a hold (any user can request).
    Transitions hold from ON_HOLD to PENDING_RESUME_APPROVAL.
    """
    from backend.orm.hold_entry import HoldEntry, HoldStatus

    db_hold = db.query(HoldEntry).filter(HoldEntry.hold_entry_id == hold_id).first()
    if not db_hold:
        raise HTTPException(status_code=404, detail="WIP hold not found")

    # Verify caller has access to this hold's client
    verify_client_access(current_user, db_hold.client_id, db)

    # Validate status transition
    if db_hold.hold_status != HoldStatus.ON_HOLD:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot request resume for hold with status {db_hold.hold_status}. Only ON_HOLD can be resumed.",
        )

    # Request resume
    db_hold.hold_status = HoldStatus.PENDING_RESUME_APPROVAL
    db_hold.resumed_by = current_user.user_id  # Track who requested
    db_hold.updated_by = current_user.user_id

    db.commit()
    db.refresh(db_hold)

    return db_hold


@router.post("/{hold_id}/approve-resume", response_model=WIPHoldResponse)
def approve_resume(
    hold_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_supervisor)
) -> WIPHoldResponse:
    """
    Approve a resume request (supervisor only).
    Transitions hold from PENDING_RESUME_APPROVAL to RESUMED.
    Auto-calculates hold duration.
    """
    from backend.orm.hold_entry import HoldEntry, HoldStatus
    from decimal import Decimal

    db_hold = db.query(HoldEntry).filter(HoldEntry.hold_entry_id == hold_id).first()
    if not db_hold:
        raise HTTPException(status_code=404, detail="WIP hold not found")

    # Verify caller has access to this hold's client
    verify_client_access(current_user, db_hold.client_id, db)

    # Validate status transition
    if db_hold.hold_status != HoldStatus.PENDING_RESUME_APPROVAL:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot approve resume for hold with status {db_hold.hold_status}. "
                "Only PENDING_RESUME_APPROVAL can be approved."
            ),
        )

    # Approve the resume
    db_hold.hold_status = HoldStatus.RESUMED
    db_hold.resume_date = datetime.now(tz=timezone.utc)
    db_hold.updated_by = current_user.user_id

    # Auto-calculate hold duration
    if db_hold.hold_date:
        hold_start = db_hold.hold_date
        if hasattr(hold_start, "date"):
            hold_start = datetime.combine(hold_start.date(), datetime.min.time())
        elif isinstance(hold_start, str):
            hold_start = datetime.strptime(hold_start.split()[0], "%Y-%m-%d")

        if not hold_start.tzinfo:
            hold_start = hold_start.replace(tzinfo=timezone.utc)
        delta = datetime.now(tz=timezone.utc) - hold_start
        db_hold.total_hold_duration_hours = Decimal(str(delta.total_seconds() / 3600))

    db.commit()
    db.refresh(db_hold)

    return db_hold


@router.get("/pending-approvals", response_model=List[WIPHoldResponse])
def get_pending_approvals(
    approval_type: Optional[str] = None,  # "hold" or "resume"
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
    scope: ClientScope = Depends(resolve_client_scope),
) -> List[HoldEntry]:
    """
    Get all holds pending approval (supervisor only).
    Returns holds with PENDING_HOLD_APPROVAL or PENDING_RESUME_APPROVAL status.
    """
    from backend.orm.hold_entry import HoldEntry, HoldStatus

    query = db.query(HoldEntry)

    # Client-scope authorization for supervisors
    query = query.filter(scope.filter(HoldEntry.client_id))

    # Filter by approval type
    if approval_type == "hold":
        query = query.filter(HoldEntry.hold_status == HoldStatus.PENDING_HOLD_APPROVAL)
    elif approval_type == "resume":
        query = query.filter(HoldEntry.hold_status == HoldStatus.PENDING_RESUME_APPROVAL)
    else:
        # Return both types
        query = query.filter(
            HoldEntry.hold_status.in_([HoldStatus.PENDING_HOLD_APPROVAL, HoldStatus.PENDING_RESUME_APPROVAL])
        )

    return query.order_by(HoldEntry.hold_date.desc()).all()


# WIP Aging KPI endpoints (separate prefix for /api/kpi namespace)
wip_aging_router = APIRouter(prefix="/api/kpi", tags=["WIP Holds"])


def _hold_column_to_date(raw_value: object) -> Optional[date]:
    """Coerce a HOLD_ENTRY DateTime column value (hold_date/resume_date) to
    a plain date. hold_date/resume_date are typed DateTime in the ORM, but
    this stays defensive about date/str shapes the way the original
    hold_date parsing in calculate_wip_aging_kpi did (SQLite can hand back
    a str in some raw-query paths)."""
    if raw_value is None:
        return None
    if isinstance(raw_value, datetime):
        return raw_value.date()
    if isinstance(raw_value, date):
        return raw_value
    if isinstance(raw_value, str):
        return datetime.strptime(raw_value.split()[0], "%Y-%m-%d").date()
    return None


def _snapshot_cutoff(as_of: date) -> datetime:
    """End-of-day instant for as-of snapshot scoping.

    ALL THREE WIP-aging endpoints scope against this single cutoff so their
    boundaries cannot drift: a hold is active as of date D iff
    `hold_date <= end_of_day(D)` AND (`resume_date IS NULL` OR
    `resume_date > end_of_day(D)`).

    Both sides deliberately use END of day. An earlier revision compared
    `resume_date` against the START of the day (a bare `date` binds to
    midnight in SQL), which made the two boundaries asymmetric: a hold
    opened at any hour of D counted, but a hold *resumed* at any hour of D
    also still counted -- so a hold opened and resumed within D reported as
    active with age 0. At end-of-day D that hold is not on hold, and WIP
    aging asks what is sitting on hold at the snapshot instant.
    """
    return datetime.combine(as_of, datetime.max.time())


def _resumed_by(resume_value: object, as_of: date) -> bool:
    """True iff a hold had already resumed at the `as_of` snapshot instant.

    Date-granular counterpart of the SQL `resume_date > end_of_day(as_of)`
    predicate used by the trend endpoint -- equivalent because a resume
    stamped anywhere within day `as_of` is at or before that day's end.
    """
    resume_date_only = _hold_column_to_date(resume_value)
    return resume_date_only is not None and resume_date_only <= as_of


@wip_aging_router.get("/wip-aging", response_model=WIPAgingResponse)
def calculate_wip_aging_kpi(
    product_id: Optional[int] = None,
    as_of_date: Optional[date] = None,
    client_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> WIPAgingResponse:
    """
    Calculate WIP aging analysis with client filtering.

    AS-OF SNAPSHOT SEMANTICS (owner ruling 2026-08-07): a windowed call
    answers "what did WIP aging look like as of `end_date`", not "which
    holds were opened during [start_date, end_date]". Filtering by
    opened-in-window systematically excludes the oldest, worst holds --
    they were opened long before any trailing window -- which is exactly
    the bug this fixes (live evidence: a trailing-30-day window returned
    all-zeros while 4 chronic holds sat at 60-70 days). `start_date` is
    accepted for API compatibility only and is IGNORED: scoping is
    entirely a function of `as_of`.

    A hold is in scope iff it was still active as of `as_of` (= `end_date`,
    falling back to `as_of_date`, falling back to today):
    `hold_date <= end_of_day(as_of)` AND (`resume_date IS NULL` OR
    `resume_date > end_of_day(as_of)`) -- see `_snapshot_cutoff`, which all
    three WIP-aging endpoints share. Age is measured from `hold_date` to
    `as_of` -- NOT real-world today -- so a historical `end_date` reproduces
    the same snapshot on every call (same clamping principle as
    backend/pivot/hooks.py's fetch_holds).

    Returns aging bucket distribution (0-7, 8-14, 15-30, 30+ days),
    average aging days, and total active hold count.

    SECURITY: Requires authentication; non-admin users see only their assigned client.
    """
    from backend.orm.hold_entry import HoldEntry
    from backend.utils.date_range import validate_date_range

    # Reject reversed range (Run-6 audit R6-D-001) before defaulting. Kept
    # for API compatibility even though start_date no longer scopes the query.
    validate_date_range(start_date, end_date)

    as_of = end_date or as_of_date or date.today()

    # Holds that existed by `as_of` -- resume-state is filtered in Python
    # below (avoids dialect-specific date-diff SQL; matches
    # backend/pivot/hooks.py's fetch_holds, which computes ages in Python
    # for the same portability reason -- see the SQLite-only date-diff
    # regression guarded by tests/test_db/test_no_sqlite_only_funcs.py,
    # which is why this comment cannot name that function literally).
    query = db.query(HoldEntry).filter(HoldEntry.hold_date <= _snapshot_cutoff(as_of))

    # Apply client filter
    query = query.filter(scope.filter(HoldEntry.client_id))

    candidates = query.all()

    total_held = 0
    total_age = 0
    aging_0_7 = 0
    aging_8_14 = 0
    aging_15_30 = 0
    aging_over_30 = 0

    for hold in candidates:
        hold_date_only = _hold_column_to_date(hold.hold_date)
        if hold_date_only is None:
            continue

        if _resumed_by(hold.resume_date, as_of):
            continue  # already resumed at the snapshot instant -- not active WIP

        total_held += 1
        age_days = (as_of - hold_date_only).days
        total_age += age_days

        if age_days <= 7:
            aging_0_7 += 1
        elif age_days <= 14:
            aging_8_14 += 1
        elif age_days <= 30:
            aging_15_30 += 1
        else:
            aging_over_30 += 1

    avg_aging = total_age / total_held if total_held > 0 else 0

    return WIPAgingResponse(
        total_held_quantity=total_held,
        average_aging_days=round(avg_aging, 1),
        aging_0_7_days=aging_0_7,
        aging_8_14_days=aging_8_14,
        aging_15_30_days=aging_15_30,
        aging_over_30_days=aging_over_30,
        total_hold_events=total_held,
        calculation_timestamp=datetime.now(tz=timezone.utc),
    )


@wip_aging_router.get("/wip-aging/top")
def get_top_aging_items(
    limit: int = SMALL_PAGE_SIZE,
    client_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> list[dict]:
    """Get top aging WIP items - for WIP Aging view table.

    Same as-of snapshot semantics as GET /api/kpi/wip-aging (owner ruling
    2026-08-07): `as_of` = `end_date` (default today); `start_date` is
    accepted for API compatibility only and is IGNORED. Scoping is the
    shared `_snapshot_cutoff` predicate -- `hold_date <= end_of_day(as_of)`
    and not yet resumed at that instant. Age is computed in Python from
    `hold_date` to `as_of`, not the DB's current time, so a historical
    `end_date` reproduces the same top-N list on every call (mirrors
    calculate_wip_aging_kpi; avoids dialect-specific date-diff SQL for the
    snapshot cutoff).
    """
    from backend.orm.hold_entry import HoldEntry
    from backend.orm.work_order import WorkOrder
    from backend.utils.date_range import validate_date_range

    # Reject reversed range (Run-6 audit R6-D-001) before defaulting. Kept
    # for API compatibility even though start_date no longer scopes the query.
    validate_date_range(start_date, end_date)

    as_of = end_date or date.today()

    query = (
        db.query(
            HoldEntry.work_order_id,
            WorkOrder.style_model,
            HoldEntry.hold_date,
            HoldEntry.resume_date,
        )
        .outerjoin(WorkOrder, HoldEntry.work_order_id == WorkOrder.work_order_id)
        .filter(HoldEntry.hold_date <= _snapshot_cutoff(as_of))
    )

    # Apply client filter
    query = query.filter(scope.filter(HoldEntry.client_id))

    items = []
    for work_order_id, style_model, hold_date_raw, resume_date_raw in query.all():
        hold_date_only = _hold_column_to_date(hold_date_raw)
        if hold_date_only is None:
            continue

        if _resumed_by(resume_date_raw, as_of):
            continue  # already resumed at the snapshot instant -- not active WIP

        items.append(
            {
                "work_order": work_order_id,
                "product": style_model or "N/A",
                "age": (as_of - hold_date_only).days,
                "quantity": 1,  # Placeholder - HOLD_ENTRY doesn't track quantity
            }
        )

    items.sort(key=lambda item: item["age"], reverse=True)
    return items[:limit]


@wip_aging_router.get("/wip-aging/trend")
def get_wip_aging_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> list[dict]:
    """Get WIP aging trend data - for WIP Aging view chart"""
    from backend.orm.hold_entry import HoldEntry
    from backend.utils.date_range import validate_date_range

    # Reject reversed range (Run-6 audit R6-D-001) before defaulting.
    validate_date_range(start_date, end_date)

    if not start_date:
        start_date = date.today() - timedelta(days=LOOKBACK_MONTHLY_DAYS)
    if not end_date:
        end_date = date.today()

    # Get daily average aging for the date range
    # We calculate for each day how old the active holds were on that day
    trend_data = []
    current_date = start_date

    while current_date <= end_date:
        # Query holds active as of this date, using the SAME end-of-day
        # boundary as GET /wip-aging and /wip-aging/top (`_snapshot_cutoff`)
        # so a point on this trend line equals the snapshot those endpoints
        # would report for the same date. Previously `current_date` bound as
        # a bare date (= midnight), which put the resume boundary at the
        # START of the day while hold_date sat at the end -- the asymmetry
        # documented in `_snapshot_cutoff`.
        cutoff = _snapshot_cutoff(current_date)
        query = db.query(func.avg(date_diff_days(current_date, HoldEntry.hold_date))).filter(
            HoldEntry.hold_date <= cutoff,
            (HoldEntry.resume_date.is_(None)) | (HoldEntry.resume_date > cutoff),
        )

        # Apply client filter
        query = query.filter(scope.filter(HoldEntry.client_id))

        result = query.scalar()
        avg_age = float(result) if result else 0

        trend_data.append({"date": current_date.isoformat(), "value": round(avg_age, 1)})

        current_date += timedelta(days=1)

    return trend_data


@wip_aging_router.get("/chronic-holds")
def get_chronic_holds(
    threshold_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> list:
    """
    Identify chronic WIP holds.

    Returns holds that have been active longer than the threshold (default 30 days).
    Useful for identifying systemic issues in the production pipeline.

    SECURITY: Requires authentication; client filtering applied in identify_chronic_holds.
    A multi-client leader sees chronic holds across all their assigned clients
    (list-based filter) rather than being rejected by the scalar as_single() check.
    """
    threshold_client = scope.client_ids[0] if scope.client_ids is not None and len(scope.client_ids) == 1 else None
    return identify_chronic_holds(db, threshold_days, client_id=threshold_client, client_ids=scope.client_ids)
