"""
WIP Aging Calculation
PHASE 2: Work-in-process aging analysis
Enhanced with P2-001: Hold-Time Adjusted WIP Aging
Phase 7.2: Enhanced with client-level configuration overrides

Tracks how long inventory sits in hold status
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_, select
from sqlalchemy.sql.elements import ColumnElement
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Sequence, Tuple
import logging

from backend.orm.hold_entry import HoldEntry, HoldStatus
from backend.orm.hold_status_transition import HoldStatusTransition
from backend.orm.work_order import WorkOrder
from backend.crud.client_config import get_client_config_or_defaults

logger = logging.getLogger(__name__)


# Fallback default thresholds
DEFAULT_AGING_THRESHOLD_DAYS = 7
DEFAULT_CRITICAL_THRESHOLD_DAYS = 14


# =============================================================================
# "Is this hold aging WIP right now?" — the ONE definition
#
# Lives here, in the calculation layer, because both the WIP-aging endpoints
# (backend/routes/holds.py) and identify_chronic_holds below must answer it
# identically. It previously lived in the routes module while
# identify_chronic_holds kept its own `hold_status == ON_HOLD` filter, so the
# chronic list and the aging KPI disagreed about which holds were active.
# Routes import from here; nothing here imports routes.
# =============================================================================

# Statuses that are never aging WIP, for two DIFFERENT reasons.
#
# Left WIP without ever stamping `resume_date` -- `resume_date IS NULL` means
# "never resumed", which equals "still on hold" only on a live path. A
# SCRAPPED or CANCELLED hold never resumes and would otherwise age forever.
# No writer sets these today; they are declared in HOLD_STATUS_CATALOG, so
# this closes the hole rather than relying on no such rows existing.
#
# Never ENTERED hold -- PENDING_HOLD_APPROVAL is a hold *requested* and not
# yet approved, so the material is still in normal flow and nothing has
# stopped. Owner ruling 2026-08-10, made against live VM data where counting
# it took the headline WIP-aging figure from 8 holds to 12. The opposite call
# from PENDING_RESUME_APPROVAL, which DOES count: there the work has genuinely
# stopped and is waiting for permission to restart.
#
# Deliberately an exclusion list, not an allow-list of (ON_HOLD,
# PENDING_RESUME_APPROVAL): on the no-history fallback path (see
# active_as_of's BOUNDARY paragraph), `hold_status` is CURRENT state, so a
# hold that reads RESUMED today was still on hold at a past `as_of`. An
# allow-list would drop it from every historical snapshot; the `resume_date`
# comparison is what dates that correctly.
NON_WIP_HOLD_STATUSES = (
    HoldStatus.CANCELLED,
    HoldStatus.RELEASED,
    HoldStatus.SCRAPPED,
    HoldStatus.PENDING_HOLD_APPROVAL,
)


def snapshot_cutoff(as_of: date) -> datetime:
    """EXCLUSIVE upper bound for as-of scoping: midnight starting the day
    after `as_of`.

    Every WIP-aging consumer scopes against this single cutoff so their
    boundaries cannot drift: a hold is active as of date D iff
    `hold_date < cutoff` AND (`resume_date IS NULL` OR
    `resume_date >= cutoff`) -- i.e. both sides settle at the END of day D.

    Both sides deliberately cover the whole of day D. An earlier revision
    compared `resume_date` against the START of the day (a bare `date` binds
    to midnight in SQL), which made the boundaries asymmetric: a hold opened
    at any hour of D counted, but a hold *resumed* at any hour of D also
    still counted -- so a hold opened and resumed within D reported as
    active with age 0. At the end of day D that hold is not on hold, and WIP
    aging asks what is sitting on hold at the snapshot instant.

    Exclusive-next-midnight rather than an inclusive `23:59:59.999999`:
    MariaDB DATETIME columns are declared without fractional seconds, so a
    microsecond-bearing bound risks dialect-dependent rounding at exactly
    the boundary this predicate exists to define (cross-model review
    finding). Midnight is representable exactly in both dialects, and the
    two forms are otherwise equivalent -- every instant within day D is
    strictly before the next midnight.
    """
    return datetime.combine(as_of + timedelta(days=1), datetime.min.time())


def active_as_of(as_of: date) -> ColumnElement[bool]:
    """SQL predicate for "this hold was still on hold at the `as_of` instant".

    The single source of truth for WIP-aging scoping: the aggregate, top-N,
    trend and chronic-hold queries all filter on this, so their notions of
    "active" cannot drift apart. Expressed in SQL (not Python) so callers
    keep index-assisted ORDER BY ... LIMIT instead of loading every candidate
    hold into memory, and so aggregates transfer only rows they will count.

    Active means: opened on or before `as_of`, not yet resumed as of then,
    and in a status that is actually aging WIP -- see `NON_WIP_HOLD_STATUSES`
    for the two reasons a status is excluded. PENDING_RESUME_APPROVAL counts
    (work has stopped, awaiting permission to restart); PENDING_HOLD_APPROVAL
    does not (the hold is only requested, so nothing has stopped).

    Portable by construction: plain comparisons against a bound datetime, no
    dialect-specific date arithmetic and no fractional seconds.

    Status is read from HOLD_STATUS_TRANSITION -- the `to_status` of the
    latest transition before the cutoff -- so a past `as_of` is judged by what
    the hold actually was then, not by what it looks like today.

    BOUNDARY (no backfill). Holds with no recorded transition before the
    cutoff fall back to their current `hold_status`, which is the pre-PR-C1
    behaviour: correct for live holds, approximate for history that predates
    the table. `hold_status_history_started_at` reports where exactness
    begins. Backfill was ruled out deliberately (2026-08-12); do not
    reconstruct history retroactively.

    OPERATIONAL CONSEQUENCE: for a hold that already has history rows,
    HOLD_ENTRY.hold_status no longer decides WIP-aging by itself -- not even
    at as_of=today -- so a manual/runbook status correction on such a hold
    must insert a paired HOLD_STATUS_TRANSITION row or the KPI will not move.
    """
    cutoff = snapshot_cutoff(as_of)

    # The hold's status AS OF the cutoff: the `to_status` of its latest
    # transition strictly before the cutoff. Ordered by (transitioned_at,
    # transition_id) because MariaDB DATETIME stores whole seconds -- two
    # transitions can share an instant, and the later-inserted row wins.
    status_as_of = (
        select(HoldStatusTransition.to_status)
        .where(
            HoldStatusTransition.hold_entry_id == HoldEntry.hold_entry_id,
            HoldStatusTransition.transitioned_at < cutoff,
        )
        .correlate(HoldEntry)
        .order_by(
            HoldStatusTransition.transitioned_at.desc(),
            HoldStatusTransition.transition_id.desc(),
        )
        .limit(1)
        .scalar_subquery()
    )

    # No backfill: holds predating this table have no transitions, so they
    # fall back to current status -- exactly the pre-PR-C1 behaviour, rather
    # than vanishing from history entirely.
    effective_status = func.coalesce(status_as_of, HoldEntry.hold_status)

    return and_(
        HoldEntry.hold_date < cutoff,
        or_(HoldEntry.resume_date.is_(None), HoldEntry.resume_date >= cutoff),
        effective_status.notin_(NON_WIP_HOLD_STATUSES),
    )


def hold_status_history_started_at(db: Session) -> Optional[datetime]:
    """Earliest recorded hold-status transition, or None when none exist.

    `active_as_of` is exact from a hold's first recorded transition onward and
    falls back to current status before it (there is no backfill, by owner
    ruling). Callers that present historical series use this to say honestly
    from when the series is exact -- the same role `_trail_started_at` plays
    for the audit read API in backend/routes/audit.py.
    """
    result = db.query(func.min(HoldStatusTransition.transitioned_at)).scalar()
    return result if isinstance(result, datetime) else None


def get_client_wip_thresholds(db: Session, client_id: Optional[str] = None) -> Tuple[int, int]:
    """
    Get WIP aging thresholds for a client from their configuration.
    Falls back to global defaults if no client config exists.

    Phase 7.2: Client-level configuration overrides

    Args:
        db: Database session
        client_id: Client ID (optional)

    Returns:
        Tuple of (aging_threshold_days, critical_threshold_days)
    """
    if not client_id:
        return (DEFAULT_AGING_THRESHOLD_DAYS, DEFAULT_CRITICAL_THRESHOLD_DAYS)

    try:
        config = get_client_config_or_defaults(db, client_id)
        aging = config.get("wip_aging_threshold_days", DEFAULT_AGING_THRESHOLD_DAYS)
        critical = config.get("wip_critical_threshold_days", DEFAULT_CRITICAL_THRESHOLD_DAYS)
        return (aging, critical)
    except Exception as e:
        logger.warning(f"Error in WIP aging calculation: {e}")
        return (DEFAULT_AGING_THRESHOLD_DAYS, DEFAULT_CRITICAL_THRESHOLD_DAYS)


def _to_date(value: Optional[datetime]) -> Optional[date]:
    """Coerce an Optional[datetime] to Optional[date].

    HoldEntry.hold_date is Mapped[Optional[datetime]] in the ORM, so the
    legacy `hasattr(value, "date")` pattern made mypy think the variable
    could still be None when later used in `(today - hold_date).days`.
    Centralised here so the null check happens once.
    """
    if value is None:
        return None
    return value.date() if isinstance(value, datetime) else value


def calculate_wip_aging(
    db: Session,
    product_id: Optional[int] = None,
    as_of_date: Optional[date] = None,
    client_id: Optional[str] = None,
) -> Dict:
    """
    Calculate WIP aging analysis

    Phase 7.2: Uses client-specific thresholds for aging/critical buckets

    Returns aging buckets based on client config:
    - 0 to aging_threshold days (default 7)
    - aging_threshold+1 to critical_threshold days (default 14)
    - critical_threshold+1 to 30 days
    - Over 30 days
    """

    if as_of_date is None:
        as_of_date = date.today()

    # Get client-specific thresholds
    aging_threshold, critical_threshold = get_client_wip_thresholds(db, client_id)

    # Base query - only active holds (not resumed)
    query = db.query(HoldEntry).filter(HoldEntry.hold_status == HoldStatus.ON_HOLD)

    # Filter by client_id if provided
    if client_id:
        query = query.filter(HoldEntry.client_id == client_id)

    # Note: HoldEntry doesn't have product_id - skip filter for now
    # if product_id:
    #     query = query.filter(HoldEntry.product_id == product_id)

    holds = query.all()

    # Initialize buckets with client-specific threshold labels
    aging_buckets = {
        f"0-{aging_threshold}": {"quantity": 0, "count": 0},
        f"{aging_threshold + 1}-{critical_threshold}": {"quantity": 0, "count": 0},
        f"{critical_threshold + 1}-30": {"quantity": 0, "count": 0},
        "over_30": {"quantity": 0, "count": 0},
    }

    total_quantity = 0
    total_aging_days = 0
    flagged_aging = 0  # Items past aging threshold
    flagged_critical = 0  # Items past critical threshold

    for hold in holds:
        # Calculate aging - hold_date is DateTime, need to convert to date
        hold_date = _to_date(hold.hold_date)
        if hold_date is None:
            continue
        aging_days = (as_of_date - hold_date).days
        quantity = 1  # Each hold counts as 1 since HoldEntry doesn't track quantity

        total_quantity += quantity
        total_aging_days += aging_days * quantity

        # Categorize using client thresholds
        if aging_days <= aging_threshold:
            aging_buckets[f"0-{aging_threshold}"]["quantity"] += quantity
            aging_buckets[f"0-{aging_threshold}"]["count"] += 1
        elif aging_days <= critical_threshold:
            aging_buckets[f"{aging_threshold + 1}-{critical_threshold}"]["quantity"] += quantity
            aging_buckets[f"{aging_threshold + 1}-{critical_threshold}"]["count"] += 1
            flagged_aging += quantity
        elif aging_days <= 30:
            aging_buckets[f"{critical_threshold + 1}-30"]["quantity"] += quantity
            aging_buckets[f"{critical_threshold + 1}-30"]["count"] += 1
            flagged_aging += quantity
            flagged_critical += quantity
        else:
            aging_buckets["over_30"]["quantity"] += quantity
            aging_buckets["over_30"]["count"] += 1
            flagged_aging += quantity
            flagged_critical += quantity

    # Calculate average aging
    avg_aging = Decimal("0")
    if total_quantity > 0:
        avg_aging = Decimal(str(total_aging_days)) / Decimal(str(total_quantity))

    return {
        "total_held_quantity": total_quantity,
        "average_aging_days": avg_aging,
        "aging_buckets": aging_buckets,
        # Legacy fields for backward compatibility
        "aging_0_7_days": aging_buckets.get(f"0-{aging_threshold}", {}).get("quantity", 0),
        "aging_8_14_days": aging_buckets.get(f"{aging_threshold + 1}-{critical_threshold}", {}).get("quantity", 0),
        "aging_15_30_days": aging_buckets.get(f"{critical_threshold + 1}-30", {}).get("quantity", 0),
        "aging_over_30_days": aging_buckets["over_30"]["quantity"],
        "total_hold_events": len(holds),
        # New fields for client config awareness
        "flagged_aging_count": flagged_aging,
        "flagged_critical_count": flagged_critical,
        "config": {"aging_threshold_days": aging_threshold, "critical_threshold_days": critical_threshold},
    }


def calculate_hold_resolution_rate(
    db: Session, start_date: date, end_date: date, product_id: Optional[int] = None, client_id: Optional[str] = None
) -> Dict:
    """
    Calculate what percentage of holds are resolved within target time

    Phase 7.2: Uses client-specific aging threshold as resolution target
    """

    # Get client-specific threshold
    aging_threshold, _ = get_client_wip_thresholds(db, client_id)

    query = db.query(HoldEntry).filter(
        and_(
            HoldEntry.hold_date >= datetime.combine(start_date, datetime.min.time()),
            HoldEntry.hold_date <= datetime.combine(end_date, datetime.max.time()),
            HoldEntry.hold_status == HoldStatus.RESUMED,
        )
    )

    # Filter by client_id if provided
    if client_id:
        query = query.filter(HoldEntry.client_id == client_id)

    # Note: HoldEntry doesn't have product_id - skip filter
    # if product_id:
    #     query = query.filter(HoldEntry.product_id == product_id)

    holds = query.all()

    if not holds:
        return {
            "resolution_rate": Decimal("0"),
            "resolved_on_time": 0,
            "total_resolved": 0,
            "target_days": aging_threshold,
        }

    # Count how many resolved within client threshold days
    resolved_on_time = 0
    for hold in holds:
        hold_date = _to_date(hold.hold_date)
        resume_date = _to_date(hold.resume_date)
        if hold_date is None or resume_date is None:
            continue
        resolution_days = (resume_date - hold_date).days
        if resolution_days <= aging_threshold:
            resolved_on_time += 1

    resolution_rate = (Decimal(str(resolved_on_time)) / Decimal(str(len(holds)))) * 100

    return {
        "resolution_rate": resolution_rate,
        "resolved_on_time": resolved_on_time,
        "total_resolved": len(holds),
        "target_days": aging_threshold,
    }


def identify_chronic_holds(
    db: Session,
    threshold_days: Optional[int] = None,
    client_id: Optional[str] = None,
    client_ids: Optional[Sequence[str]] = None,
) -> List[Dict]:
    """
    Identify holds that have been open longer than threshold

    Phase 7.2: Uses client-specific critical threshold if threshold_days not provided

    Args:
        client_id: Scalar client filter, also used for the per-client threshold
            lookup when threshold_days is not provided.
        client_ids: List/tuple of client ids to filter by (multi-client scope,
            e.g. a leader with several assigned clients). Coexists with
            client_id; when only client_ids is supplied, client_id stays None
            and its scalar filter is a no-op.
    """

    today = date.today()

    # Use client config if threshold not explicitly provided
    if threshold_days is None:
        _, critical_threshold = get_client_wip_thresholds(db, client_id)
        threshold_days = critical_threshold * 2  # Chronic = 2x critical threshold (default 28 days)

    threshold_date = today - timedelta(days=threshold_days)

    # "Chronic" = active WIP (the shared `active_as_of` definition) that has
    # additionally been on hold at least `threshold_days`. The active arm was
    # previously a bare `hold_status == ON_HOLD`, which disagreed with the
    # WIP-aging endpoints: it dropped PENDING_RESUME_APPROVAL holds (work
    # stopped, awaiting restart -- chronic if old) and would have kept a
    # CANCELLED/SCRAPPED hold had one ever carried that status.
    #
    # The age arm uses `snapshot_cutoff(threshold_date)` -- the END of the
    # threshold day -- for the same reason the rest of this family does. It
    # was `<= midnight of threshold_date`, which silently dropped any hold
    # opened later in the day on the threshold date even though `aging_days`
    # computed below reports it as exactly `threshold_days` old: the row
    # qualified by the function's own arithmetic and was filtered out by the
    # query (cross-model review finding; pre-existing, and inconsistent with
    # the end-of-day convention once the predicates were unified). Boundary
    # is therefore `aging_days >= threshold_days`, stated rather than
    # accidental. Date comparison, not datediff, keeps it SQLite-compatible.
    query = db.query(HoldEntry).filter(and_(active_as_of(today), HoldEntry.hold_date < snapshot_cutoff(threshold_date)))

    # Filter by client_id if provided
    if client_id:
        query = query.filter(HoldEntry.client_id == client_id)

    # Filter by client_ids (multi-client scope) if provided
    if client_ids is not None:
        query = query.filter(HoldEntry.client_id.in_(client_ids))

    chronic_holds = query.all()

    results: List[Dict] = []
    for hold in chronic_holds:
        hold_date = _to_date(hold.hold_date)
        if hold_date is None:
            continue
        aging_days = (today - hold_date).days
        results.append(
            {
                "hold_id": hold.hold_entry_id,
                "work_order": hold.work_order_id,
                "product_id": None,  # HoldEntry doesn't have product_id
                "quantity": 1,
                "aging_days": aging_days,
                "hold_reason": str(hold.hold_reason) if hold.hold_reason else hold.hold_reason_category,
                "hold_category": hold.hold_reason_category,
                "threshold_days_used": threshold_days,
            }
        )

    # Sort by aging (oldest first). aging_days is always int from the
    # comprehension above, but the dict value union includes None
    # (product_id), so cast at the sort key to keep mypy happy.
    results.sort(key=lambda x: int(x["aging_days"] or 0), reverse=True)

    return results


# =============================================================================
# P2-001: Hold-Time Adjusted WIP Aging Calculations
# =============================================================================


def get_total_hold_duration_hours(db: Session, work_order_number: str) -> Decimal:
    """
    Get total hold duration in hours for a work order
    P2-001: Core function for WIP aging adjustment

    Sums all hold durations for the work order:
    - For completed holds: uses stored total_hold_duration_hours
    - For active holds: calculates from hold_timestamp to now

    Args:
        db: Database session
        work_order_number: Work order number

    Returns:
        Total hold duration in hours as Decimal
    """
    holds = db.query(HoldEntry).filter(HoldEntry.work_order_id == work_order_number).all()

    total_duration = Decimal("0")

    for hold in holds:
        if hold.hold_status == HoldStatus.ON_HOLD:
            # Active hold - calculate from hold_timestamp to now
            if hold.hold_date:
                hold_date = hold.hold_date if hold.hold_date.tzinfo else hold.hold_date.replace(tzinfo=timezone.utc)
                delta = datetime.now(tz=timezone.utc) - hold_date
                total_duration += Decimal(str(delta.total_seconds() / 3600))
        else:
            # Completed hold - use stored duration
            if hold.total_hold_duration_hours:
                total_duration += hold.total_hold_duration_hours

    return total_duration


def calculate_wip_age_adjusted(db: Session, work_order_number: str, work_order_created_at: datetime) -> Dict:
    """
    Calculate TRUE WIP age by subtracting hold time
    P2-001: WIP Aging Adjustment

    Formula: Adjusted Age = Raw Age - Total Hold Duration

    Args:
        db: Database session
        work_order_number: Work order number
        work_order_created_at: When the work order was created

    Returns:
        Dict with raw age, hold duration, adjusted age, and hold count
    """
    # Get total hold duration for this work order
    total_hold_hours = get_total_hold_duration_hours(db, work_order_number)

    # Calculate raw age in hours — normalize naive DB datetimes to UTC
    now = datetime.now(tz=timezone.utc)
    created_at = (
        work_order_created_at if work_order_created_at.tzinfo else work_order_created_at.replace(tzinfo=timezone.utc)
    )
    raw_age_seconds = (now - created_at).total_seconds()
    raw_age_hours = Decimal(str(raw_age_seconds / 3600))

    # Subtract hold time for TRUE WIP age
    adjusted_age_hours = raw_age_hours - total_hold_hours
    adjusted_age_hours = max(Decimal("0"), adjusted_age_hours)  # Cannot be negative

    # Count holds
    hold_count = db.query(HoldEntry).filter(HoldEntry.work_order_id == work_order_number).count()

    # Check if currently on hold
    active_holds = (
        db.query(HoldEntry)
        .filter(and_(HoldEntry.work_order_id == work_order_number, HoldEntry.hold_status == HoldStatus.ON_HOLD))
        .count()
    )

    return {
        "work_order_number": work_order_number,
        "raw_age_hours": raw_age_hours.quantize(Decimal("0.01")),
        "total_hold_duration_hours": total_hold_hours.quantize(Decimal("0.0001")),
        "adjusted_age_hours": adjusted_age_hours.quantize(Decimal("0.01")),
        "hold_count": hold_count,
        "is_currently_on_hold": active_holds > 0,
    }


def calculate_work_order_wip_age(db: Session, work_order_id: str) -> Optional[Dict]:
    """
    Calculate WIP age for a specific work order with hold-time adjustment
    P2-001: Main entry point for adjusted WIP aging

    Args:
        db: Database session
        work_order_id: Work order ID

    Returns:
        Dict with aging metrics or None if work order not found
    """
    # Get the work order
    work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == work_order_id).first()

    if not work_order:
        return None

    # Use actual_start_date if available, otherwise created_at
    start_time = work_order.actual_start_date or work_order.created_at

    if not start_time:
        return None

    return calculate_wip_age_adjusted(db=db, work_order_number=work_order_id, work_order_created_at=start_time)


def calculate_wip_aging_with_hold_adjustment(
    db: Session,
    product_id: Optional[int] = None,
    client_id: Optional[str] = None,
    as_of_date: Optional[date] = None,
) -> Dict:
    """
    Enhanced WIP aging analysis with hold-time adjustment
    P2-001: Extension of standard WIP aging

    Returns aging buckets with both raw and adjusted ages

    Args:
        db: Database session
        product_id: Optional product filter
        client_id: Optional client filter
        as_of_date: Date for calculation

    Returns:
        Dict with aging buckets and adjustment metrics
    """
    if as_of_date is None:
        as_of_date = date.today()

    # Base query - only active holds
    query = db.query(HoldEntry).filter(HoldEntry.hold_status == HoldStatus.ON_HOLD)

    # Note: HoldEntry doesn't have product_id
    # if product_id:
    #     query = query.filter(HoldEntry.product_id == product_id)

    if client_id:
        query = query.filter(HoldEntry.client_id == client_id)

    holds = query.all()

    # Initialize buckets for both raw and adjusted aging
    aging_buckets = {
        "0-7": {"quantity": 0, "count": 0, "adjusted_quantity": 0},
        "8-14": {"quantity": 0, "count": 0, "adjusted_quantity": 0},
        "15-30": {"quantity": 0, "count": 0, "adjusted_quantity": 0},
        "over_30": {"quantity": 0, "count": 0, "adjusted_quantity": 0},
    }

    total_quantity = 0
    total_raw_aging_days = 0
    # adjusted aging mixes float days (from hold_duration_days) with int
    # raw aging, so the running total must be float — was inferred as int
    # and rejected the float assignment below.
    total_adjusted_aging_days: float = 0.0
    total_hold_duration_hours = Decimal("0")

    # Group holds by work order for adjustment calculation
    work_order_holds: Dict[str, List] = {}
    for hold in holds:
        wo = hold.work_order_id
        if wo not in work_order_holds:
            work_order_holds[wo] = []
        work_order_holds[wo].append(hold)

    for hold in holds:
        # Calculate raw aging - handle DateTime
        hold_date = _to_date(hold.hold_date)
        if hold_date is None:
            continue
        raw_aging_days = (as_of_date - hold_date).days
        quantity = 1  # HoldEntry doesn't track quantity

        # Get hold duration for this work order
        hold_duration = get_total_hold_duration_hours(db, hold.work_order_id)
        hold_duration_days = float(hold_duration) / 24.0

        # Calculate adjusted aging
        adjusted_aging_days = max(0, raw_aging_days - hold_duration_days)

        total_quantity += quantity
        total_raw_aging_days += raw_aging_days * quantity
        total_adjusted_aging_days += adjusted_aging_days * quantity
        total_hold_duration_hours += hold_duration

        # Categorize by RAW aging
        if raw_aging_days <= 7:
            aging_buckets["0-7"]["quantity"] += quantity
            aging_buckets["0-7"]["count"] += 1
        elif raw_aging_days <= 14:
            aging_buckets["8-14"]["quantity"] += quantity
            aging_buckets["8-14"]["count"] += 1
        elif raw_aging_days <= 30:
            aging_buckets["15-30"]["quantity"] += quantity
            aging_buckets["15-30"]["count"] += 1
        else:
            aging_buckets["over_30"]["quantity"] += quantity
            aging_buckets["over_30"]["count"] += 1

        # Categorize by ADJUSTED aging
        if adjusted_aging_days <= 7:
            aging_buckets["0-7"]["adjusted_quantity"] += quantity
        elif adjusted_aging_days <= 14:
            aging_buckets["8-14"]["adjusted_quantity"] += quantity
        elif adjusted_aging_days <= 30:
            aging_buckets["15-30"]["adjusted_quantity"] += quantity
        else:
            aging_buckets["over_30"]["adjusted_quantity"] += quantity

    # Calculate averages
    avg_raw_aging = Decimal("0")
    avg_adjusted_aging = Decimal("0")
    if total_quantity > 0:
        avg_raw_aging = Decimal(str(total_raw_aging_days)) / Decimal(str(total_quantity))
        avg_adjusted_aging = Decimal(str(total_adjusted_aging_days)) / Decimal(str(total_quantity))

    return {
        # Standard aging metrics
        "total_held_quantity": total_quantity,
        "average_aging_days": avg_raw_aging,
        "aging_0_7_days": aging_buckets["0-7"]["quantity"],
        "aging_8_14_days": aging_buckets["8-14"]["quantity"],
        "aging_15_30_days": aging_buckets["15-30"]["quantity"],
        "aging_over_30_days": aging_buckets["over_30"]["quantity"],
        "total_hold_events": len(holds),
        # P2-001: Adjusted aging metrics
        "average_adjusted_aging_days": avg_adjusted_aging,
        "adjusted_aging_0_7_days": aging_buckets["0-7"]["adjusted_quantity"],
        "adjusted_aging_8_14_days": aging_buckets["8-14"]["adjusted_quantity"],
        "adjusted_aging_15_30_days": aging_buckets["15-30"]["adjusted_quantity"],
        "adjusted_aging_over_30_days": aging_buckets["over_30"]["adjusted_quantity"],
        "total_hold_duration_hours": total_hold_duration_hours.quantize(Decimal("0.01")),
        # Work order count
        "unique_work_orders": len(work_order_holds),
    }
