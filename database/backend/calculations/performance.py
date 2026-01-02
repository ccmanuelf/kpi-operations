"""
Performance Calculation Module (KPI #9)

FORMULA:
Performance = (Ideal Cycle Time × Units Produced) / Run Time Hours × 100

This measures how fast the machine/line ran during ACTUAL operation time,
not workforce efficiency during scheduled time.
"""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select


def calculate_performance(
    units_produced: int,
    ideal_cycle_time: float,
    run_time_hours: float,
    as_percentage: bool = True
) -> Optional[float]:
    """
    Calculate production line performance based on actual runtime.

    FORMULA:
    Performance = (Ideal Cycle Time × Units) / Runtime Hours × 100

    Args:
        units_produced: Number of units produced
        ideal_cycle_time: Standard time per unit in hours
        run_time_hours: ACTUAL runtime (machine operating time)
        as_percentage: Return as percentage (default True)

    Returns:
        Performance value (0-100+ if percentage)
        Returns None if invalid inputs
    """
    if run_time_hours <= 0:
        return None

    if units_produced < 0 or ideal_cycle_time < 0:
        return None

    ideal_production_time = ideal_cycle_time * units_produced
    performance_ratio = ideal_production_time / run_time_hours

    if as_percentage:
        return round(performance_ratio * 100, 4)
    else:
        return round(performance_ratio, 6)


def calculate_performance_from_db(db: Session, entry_id: int) -> Optional[float]:
    """
    Calculate performance for a production entry from database.

    Args:
        db: Database session
        entry_id: Production entry ID

    Returns:
        Performance percentage or None if entry not found
    """
    try:
        from backend.models import ProductionEntry, Product
    except ImportError:
        return None

    query = select(
        ProductionEntry.units_produced,
        ProductionEntry.run_time_hours,
        Product.ideal_cycle_time
    ).join(
        Product, ProductionEntry.product_id == Product.product_id
    ).where(
        ProductionEntry.entry_id == entry_id
    )

    result = db.execute(query).first()

    if not result:
        return None

    units_produced, run_time_hours, ideal_cycle_time = result

    return calculate_performance(
        units_produced=units_produced,
        ideal_cycle_time=ideal_cycle_time,
        run_time_hours=run_time_hours,
        as_percentage=True
    )
