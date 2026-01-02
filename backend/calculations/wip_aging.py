"""
WIP Aging Calculation
PHASE 2: Work-in-process aging analysis

Tracks how long inventory sits in hold status
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional

from backend.schemas.hold import WIPHold


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
