"""
WIP Aging Calculation
PHASE 2: Work-in-process aging analysis
Enhanced with P2-001: Hold-Time Adjusted WIP Aging
Phase 7.2: Enhanced with client-level configuration overrides

Tracks how long inventory sits in hold status
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging

from backend.schemas.hold_entry import HoldEntry, HoldStatus
from backend.schemas.work_order import WorkOrder
from backend.crud.client_config import get_client_config_or_defaults

logger = logging.getLogger(__name__)


# Fallback default thresholds
DEFAULT_AGING_THRESHOLD_DAYS = 7
DEFAULT_CRITICAL_THRESHOLD_DAYS = 14


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


def calculate_wip_aging(
    db: Session, product_id: Optional[int] = None, as_of_date: date = None, client_id: Optional[str] = None
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
        hold_date = hold.hold_date.date() if hasattr(hold.hold_date, "date") else hold.hold_date
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
        if hold.resume_date and hold.hold_date:
            hold_date = hold.hold_date.date() if hasattr(hold.hold_date, "date") else hold.hold_date
            resume_date = hold.resume_date.date() if hasattr(hold.resume_date, "date") else hold.resume_date
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


def identify_chronic_holds(db: Session, threshold_days: int = None, client_id: Optional[str] = None) -> List[Dict]:
    """
    Identify holds that have been open longer than threshold

    Phase 7.2: Uses client-specific critical threshold if threshold_days not provided
    """

    today = date.today()

    # Use client config if threshold not explicitly provided
    if threshold_days is None:
        _, critical_threshold = get_client_wip_thresholds(db, client_id)
        threshold_days = critical_threshold * 2  # Chronic = 2x critical threshold (default 28 days)

    threshold_date = today - timedelta(days=threshold_days)

    # Use date comparison instead of datediff (SQLite compatible)
    threshold_datetime = datetime.combine(threshold_date, datetime.min.time())
    query = db.query(HoldEntry).filter(
        and_(HoldEntry.hold_status == HoldStatus.ON_HOLD, HoldEntry.hold_date <= threshold_datetime)
    )

    # Filter by client_id if provided
    if client_id:
        query = query.filter(HoldEntry.client_id == client_id)

    chronic_holds = query.all()

    results = []
    for hold in chronic_holds:
        hold_date = hold.hold_date.date() if hasattr(hold.hold_date, "date") else hold.hold_date
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

    # Sort by aging (oldest first)
    results.sort(key=lambda x: x["aging_days"], reverse=True)

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
    created_at = work_order_created_at if work_order_created_at.tzinfo else work_order_created_at.replace(tzinfo=timezone.utc)
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
    db: Session, product_id: Optional[int] = None, client_id: Optional[str] = None, as_of_date: date = None
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
    total_adjusted_aging_days = 0
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
        hold_date = hold.hold_date.date() if hasattr(hold.hold_date, "date") else hold.hold_date
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
