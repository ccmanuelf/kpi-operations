"""
WIP Aging Calculation
PHASE 2: Work-in-process aging analysis
Enhanced with P2-001: Hold-Time Adjusted WIP Aging

Tracks how long inventory sits in hold status
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

from backend.schemas.hold import WIPHold, HoldStatus
from backend.schemas.work_order import WorkOrder


def calculate_wip_aging(
    db: Session,
    product_id: Optional[int] = None,
    as_of_date: date = None
) -> Dict:
    """
    Calculate WIP aging analysis

    Returns aging buckets:
    - 0-7 days
    - 8-14 days
    - 15-30 days
    - Over 30 days
    """

    if as_of_date is None:
        as_of_date = date.today()

    # Base query - only unreleased holds
    query = db.query(WIPHold).filter(
        WIPHold.release_date.is_(None)
    )

    if product_id:
        query = query.filter(WIPHold.product_id == product_id)

    holds = query.all()

    # Initialize buckets
    aging_buckets = {
        "0-7": {"quantity": 0, "count": 0},
        "8-14": {"quantity": 0, "count": 0},
        "15-30": {"quantity": 0, "count": 0},
        "over_30": {"quantity": 0, "count": 0}
    }

    total_quantity = 0
    total_aging_days = 0

    for hold in holds:
        # Calculate aging
        aging_days = (as_of_date - hold.hold_date).days
        quantity = hold.quantity_held - (hold.quantity_released or 0) - (hold.quantity_scrapped or 0)

        total_quantity += quantity
        total_aging_days += aging_days * quantity  # Weighted by quantity

        # Categorize
        if aging_days <= 7:
            aging_buckets["0-7"]["quantity"] += quantity
            aging_buckets["0-7"]["count"] += 1
        elif aging_days <= 14:
            aging_buckets["8-14"]["quantity"] += quantity
            aging_buckets["8-14"]["count"] += 1
        elif aging_days <= 30:
            aging_buckets["15-30"]["quantity"] += quantity
            aging_buckets["15-30"]["count"] += 1
        else:
            aging_buckets["over_30"]["quantity"] += quantity
            aging_buckets["over_30"]["count"] += 1

    # Calculate average aging
    avg_aging = Decimal("0")
    if total_quantity > 0:
        avg_aging = Decimal(str(total_aging_days)) / Decimal(str(total_quantity))

    return {
        "total_held_quantity": total_quantity,
        "average_aging_days": avg_aging,
        "aging_0_7_days": aging_buckets["0-7"]["quantity"],
        "aging_8_14_days": aging_buckets["8-14"]["quantity"],
        "aging_15_30_days": aging_buckets["15-30"]["quantity"],
        "aging_over_30_days": aging_buckets["over_30"]["quantity"],
        "total_hold_events": len(holds)
    }


def calculate_hold_resolution_rate(
    db: Session,
    start_date: date,
    end_date: date,
    product_id: Optional[int] = None
) -> Decimal:
    """
    Calculate what percentage of holds are resolved within target time

    Target: 7 days
    """

    query = db.query(WIPHold).filter(
        and_(
            WIPHold.hold_date >= start_date,
            WIPHold.hold_date <= end_date,
            WIPHold.release_date.isnot(None)
        )
    )

    if product_id:
        query = query.filter(WIPHold.product_id == product_id)

    holds = query.all()

    if not holds:
        return Decimal("0")

    # Count how many resolved within 7 days
    resolved_on_time = 0
    for hold in holds:
        resolution_days = (hold.release_date - hold.hold_date).days
        if resolution_days <= 7:
            resolved_on_time += 1

    resolution_rate = (Decimal(str(resolved_on_time)) / Decimal(str(len(holds)))) * 100
    return resolution_rate


def identify_chronic_holds(
    db: Session,
    threshold_days: int = 30
) -> List[Dict]:
    """
    Identify holds that have been open longer than threshold
    """

    today = date.today()

    chronic_holds = db.query(WIPHold).filter(
        and_(
            WIPHold.release_date.is_(None),
            func.datediff(today, WIPHold.hold_date) > threshold_days
        )
    ).all()

    results = []
    for hold in chronic_holds:
        aging_days = (today - hold.hold_date).days
        results.append({
            "hold_id": hold.hold_id,
            "work_order": hold.work_order_number,
            "product_id": hold.product_id,
            "quantity": hold.quantity_held,
            "aging_days": aging_days,
            "hold_reason": hold.hold_reason,
            "hold_category": hold.hold_category
        })

    # Sort by aging (oldest first)
    results.sort(key=lambda x: x["aging_days"], reverse=True)

    return results


# =============================================================================
# P2-001: Hold-Time Adjusted WIP Aging Calculations
# =============================================================================

def get_total_hold_duration_hours(
    db: Session,
    work_order_number: str
) -> Decimal:
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
    holds = db.query(WIPHold).filter(
        WIPHold.work_order_number == work_order_number
    ).all()

    total_duration = Decimal("0")

    for hold in holds:
        if hold.status == HoldStatus.ON_HOLD:
            # Active hold - calculate from hold_timestamp to now
            if hold.hold_timestamp:
                delta = datetime.now() - hold.hold_timestamp
                total_duration += Decimal(str(delta.total_seconds() / 3600))
            elif hold.hold_date:
                # Fallback to hold_date
                hold_start = datetime.combine(hold.hold_date, datetime.min.time())
                delta = datetime.now() - hold_start
                total_duration += Decimal(str(delta.total_seconds() / 3600))
        else:
            # Completed hold - use stored duration
            if hold.total_hold_duration_hours:
                total_duration += hold.total_hold_duration_hours

    return total_duration


def calculate_wip_age_adjusted(
    db: Session,
    work_order_number: str,
    work_order_created_at: datetime
) -> Dict:
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

    # Calculate raw age in hours
    now = datetime.now()
    if work_order_created_at.tzinfo:
        # Make timezone-aware comparison
        from datetime import timezone
        now = datetime.now(timezone.utc)

    raw_age_seconds = (now - work_order_created_at).total_seconds()
    raw_age_hours = Decimal(str(raw_age_seconds / 3600))

    # Subtract hold time for TRUE WIP age
    adjusted_age_hours = raw_age_hours - total_hold_hours
    adjusted_age_hours = max(Decimal("0"), adjusted_age_hours)  # Cannot be negative

    # Count holds
    hold_count = db.query(WIPHold).filter(
        WIPHold.work_order_number == work_order_number
    ).count()

    # Check if currently on hold
    active_holds = db.query(WIPHold).filter(
        and_(
            WIPHold.work_order_number == work_order_number,
            WIPHold.status == HoldStatus.ON_HOLD
        )
    ).count()

    return {
        "work_order_number": work_order_number,
        "raw_age_hours": raw_age_hours.quantize(Decimal("0.01")),
        "total_hold_duration_hours": total_hold_hours.quantize(Decimal("0.0001")),
        "adjusted_age_hours": adjusted_age_hours.quantize(Decimal("0.01")),
        "hold_count": hold_count,
        "is_currently_on_hold": active_holds > 0
    }


def calculate_work_order_wip_age(
    db: Session,
    work_order_id: str
) -> Optional[Dict]:
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
    work_order = db.query(WorkOrder).filter(
        WorkOrder.work_order_id == work_order_id
    ).first()

    if not work_order:
        return None

    # Use actual_start_date if available, otherwise created_at
    start_time = work_order.actual_start_date or work_order.created_at

    if not start_time:
        return None

    return calculate_wip_age_adjusted(
        db=db,
        work_order_number=work_order_id,
        work_order_created_at=start_time
    )


def calculate_wip_aging_with_hold_adjustment(
    db: Session,
    product_id: Optional[int] = None,
    client_id: Optional[str] = None,
    as_of_date: date = None
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

    # Base query - only unreleased holds
    query = db.query(WIPHold).filter(
        WIPHold.release_date.is_(None)
    )

    if product_id:
        query = query.filter(WIPHold.product_id == product_id)

    if client_id:
        query = query.filter(WIPHold.client_id == client_id)

    holds = query.all()

    # Initialize buckets for both raw and adjusted aging
    aging_buckets = {
        "0-7": {"quantity": 0, "count": 0, "adjusted_quantity": 0},
        "8-14": {"quantity": 0, "count": 0, "adjusted_quantity": 0},
        "15-30": {"quantity": 0, "count": 0, "adjusted_quantity": 0},
        "over_30": {"quantity": 0, "count": 0, "adjusted_quantity": 0}
    }

    total_quantity = 0
    total_raw_aging_days = 0
    total_adjusted_aging_days = 0
    total_hold_duration_hours = Decimal("0")

    # Group holds by work order for adjustment calculation
    work_order_holds: Dict[str, List] = {}
    for hold in holds:
        wo = hold.work_order_number
        if wo not in work_order_holds:
            work_order_holds[wo] = []
        work_order_holds[wo].append(hold)

    for hold in holds:
        # Calculate raw aging
        raw_aging_days = (as_of_date - hold.hold_date).days
        quantity = hold.quantity_held - (hold.quantity_released or 0) - (hold.quantity_scrapped or 0)

        # Get hold duration for this work order
        hold_duration = get_total_hold_duration_hours(db, hold.work_order_number)
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
        "unique_work_orders": len(work_order_holds)
    }
