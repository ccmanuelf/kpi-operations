"""
On-Time Delivery (OTD) KPI Calculation
PHASE 3: Delivery performance tracking

OTD% = (Orders Delivered On Time / Total Orders) * 100
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date
from decimal import Decimal
from typing import Optional

from backend.schemas.production_entry import ProductionEntry


def calculate_otd(
    db: Session,
    start_date: date,
    end_date: date,
    product_id: Optional[int] = None
) -> tuple[Decimal, int, int]:
    """
    Calculate On-Time Delivery percentage

    Note: This is a simplified calculation based on production entries.
    In a full system, this would use order/shipment data.

    For MVP, we consider production completed on time if:
    - Production date <= planned completion date (stored in work_order metadata)

    Returns: (otd_percentage, on_time_count, total_count)
    """

    query = db.query(ProductionEntry).filter(
        and_(
            ProductionEntry.production_date >= start_date,
            ProductionEntry.production_date <= end_date
        )
    )

    if product_id:
        query = query.filter(ProductionEntry.product_id == product_id)

    entries = query.all()

    if not entries:
        return (Decimal("0"), 0, 0)

    # For MVP: Assume orders with confirmation are on-time
    # In production, this would check against delivery dates
    on_time_count = sum(1 for e in entries if e.confirmed_by is not None)
    total_count = len(entries)

    if total_count > 0:
        otd_percentage = (Decimal(str(on_time_count)) / Decimal(str(total_count))) * 100
    else:
        otd_percentage = Decimal("0")

    return (otd_percentage, on_time_count, total_count)


def calculate_lead_time(
    db: Session,
    work_order_number: str
) -> Optional[int]:
    """
    Calculate actual lead time for a work order

    Lead Time = Completion Date - Start Date (in days)

    In MVP, we calculate from first to last production entry
    """

    entries = db.query(ProductionEntry).filter(
        ProductionEntry.work_order_number == work_order_number
    ).order_by(ProductionEntry.production_date).all()

    if not entries or len(entries) < 1:
        return None

    start_date = entries[0].production_date
    end_date = entries[-1].production_date

    lead_time_days = (end_date - start_date).days + 1  # Include both days

    return lead_time_days


def calculate_cycle_time(
    db: Session,
    work_order_number: str
) -> Optional[Decimal]:
    """
    Calculate total cycle time (production hours) for work order
    """

    total_hours = db.query(
        func.sum(ProductionEntry.run_time_hours)
    ).filter(
        ProductionEntry.work_order_number == work_order_number
    ).scalar()

    if total_hours:
        return Decimal(str(total_hours))

    return None


def calculate_delivery_variance(
    db: Session,
    start_date: date,
    end_date: date,
    product_id: Optional[int] = None
) -> dict:
    """
    Calculate variance between planned and actual delivery

    Returns metrics on early/late deliveries
    """

    # This would be implemented with actual order/delivery data
    # For MVP, returning placeholder structure

    return {
        "total_orders": 0,
        "early_deliveries": 0,
        "on_time_deliveries": 0,
        "late_deliveries": 0,
        "average_variance_days": Decimal("0"),
        "worst_variance_days": 0,
        "best_variance_days": 0
    }


def identify_late_orders(
    db: Session,
    as_of_date: date = None
) -> list[dict]:
    """
    Identify work orders that are potentially late

    In MVP: Orders without confirmation that are older than 7 days
    """

    if not as_of_date:
        as_of_date = date.today()

    from datetime import timedelta
    threshold_date = as_of_date - timedelta(days=7)

    late_entries = db.query(ProductionEntry).filter(
        and_(
            ProductionEntry.production_date <= threshold_date,
            ProductionEntry.confirmed_by.is_(None),
            ProductionEntry.work_order_number.isnot(None)
        )
    ).all()

    # Group by work order
    work_orders = {}
    for entry in late_entries:
        wo = entry.work_order_number
        if wo not in work_orders:
            work_orders[wo] = {
                "work_order": wo,
                "product_id": entry.product_id,
                "start_date": entry.production_date,
                "days_pending": (as_of_date - entry.production_date).days,
                "total_units": 0
            }
        work_orders[wo]["total_units"] += entry.units_produced

    # Convert to list and sort by days pending
    results = list(work_orders.values())
    results.sort(key=lambda x: x["days_pending"], reverse=True)

    return results
