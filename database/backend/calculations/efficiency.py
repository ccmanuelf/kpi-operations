"""
Efficiency Calculation Module (KPI #3)

FORMULA PER CSV REQUIREMENT:
Efficiency = (Units Produced × Ideal Cycle Time) / (Employees Assigned × SCHEDULED Hours) × 100

CRITICAL: Uses SCHEDULED hours from shift definition, NOT actual runtime hours.
- Runtime hours = actual time machine/line was running (used for performance)
- Scheduled hours = planned shift duration (used for efficiency)

This measures how efficiently the workforce utilized their SCHEDULED time,
not how fast the machine ran during actual operation.
"""

from typing import Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import select


def calculate_shift_hours(shift_start: str, shift_end: str) -> float:
    """
    Calculate scheduled shift hours from start and end times.

    Args:
        shift_start: Shift start time (HH:MM:SS format)
        shift_end: Shift end time (HH:MM:SS format)

    Returns:
        Scheduled shift duration in hours

    Example:
        >>> calculate_shift_hours("07:00:00", "15:00:00")
        8.0
        >>> calculate_shift_hours("22:00:00", "06:00:00")  # Overnight shift
        8.0
    """
    from datetime import datetime, timedelta

    # Parse time strings
    start = datetime.strptime(shift_start, "%H:%M:%S")
    end = datetime.strptime(shift_end, "%H:%M:%S")

    # Handle overnight shifts (end time < start time)
    if end < start:
        end += timedelta(days=1)

    # Calculate duration in hours
    duration = (end - start).total_seconds() / 3600
    return round(duration, 2)


def calculate_efficiency(
    units_produced: int,
    ideal_cycle_time: float,
    employees_assigned: int,
    shift_hours: float,
    as_percentage: bool = True
) -> Optional[float]:
    """
    Calculate workforce efficiency using SCHEDULED hours (not runtime).

    FORMULA:
    Efficiency = (Units × Cycle Time) / (Employees × SCHEDULED Hours)

    Args:
        units_produced: Number of units produced
        ideal_cycle_time: Standard time per unit in hours
        employees_assigned: Number of employees on shift
        shift_hours: SCHEDULED shift duration in hours (NOT runtime)
        as_percentage: Return as percentage (default True)

    Returns:
        Efficiency value (0-100+ if percentage, 0-1+ if ratio)
        Returns None if invalid inputs

    Example:
        >>> calculate_efficiency(1000, 0.01, 5, 8.0)
        25.0  # 25% efficiency

        >>> calculate_efficiency(2000, 0.01, 5, 8.0)
        50.0  # 50% efficiency (2x more productive)
    """
    # Validation
    if employees_assigned <= 0:
        return None

    if shift_hours <= 0:
        return None

    if units_produced < 0 or ideal_cycle_time < 0:
        return None

    # FORMULA PER CSV REQUIREMENT:
    # Efficiency = (Units × Cycle Time) / (Employees × SCHEDULED Hours)
    # NOT (Employees × Runtime) - that would measure machine performance, not workforce efficiency

    total_standard_hours = units_produced * ideal_cycle_time
    total_available_hours = employees_assigned * shift_hours

    efficiency_ratio = total_standard_hours / total_available_hours

    if as_percentage:
        return round(efficiency_ratio * 100, 4)
    else:
        return round(efficiency_ratio, 6)


def calculate_efficiency_from_db(db: Session, entry_id: int) -> Optional[float]:
    """
    Calculate efficiency for a production entry from database.

    This function:
    1. Fetches production entry data
    2. Calculates shift hours from shift start/end times
    3. Computes efficiency using scheduled hours (NOT runtime)

    Args:
        db: Database session
        entry_id: Production entry ID

    Returns:
        Efficiency percentage or None if entry not found
    """
    # Import models (assumes SQLAlchemy models exist)
    try:
        from backend.models import ProductionEntry, Product, Shift
    except ImportError:
        # Models not yet created - return None for now
        return None

    # Fetch production entry with related data
    query = select(
        ProductionEntry.units_produced,
        ProductionEntry.employees_assigned,
        Product.ideal_cycle_time,
        Shift.start_time,
        Shift.end_time
    ).join(
        Product, ProductionEntry.product_id == Product.product_id
    ).join(
        Shift, ProductionEntry.shift_id == Shift.shift_id
    ).where(
        ProductionEntry.entry_id == entry_id
    )

    result = db.execute(query).first()

    if not result:
        return None

    units_produced, employees, ideal_cycle_time, shift_start, shift_end = result

    # Calculate scheduled shift hours
    shift_hours = calculate_shift_hours(
        str(shift_start),
        str(shift_end)
    )

    # Calculate efficiency using SCHEDULED hours
    return calculate_efficiency(
        units_produced=units_produced,
        ideal_cycle_time=ideal_cycle_time,
        employees_assigned=employees,
        shift_hours=shift_hours,  # SCHEDULED, not runtime!
        as_percentage=True
    )


def update_efficiency_in_db(db: Session, entry_id: int) -> bool:
    """
    Calculate and update efficiency for a production entry.

    Args:
        db: Database session
        entry_id: Production entry ID

    Returns:
        True if updated successfully, False otherwise
    """
    efficiency = calculate_efficiency_from_db(db, entry_id)

    if efficiency is None:
        return False

    try:
        from backend.models import ProductionEntry

        db.query(ProductionEntry).filter(
            ProductionEntry.entry_id == entry_id
        ).update({
            'efficiency_percentage': efficiency
        })
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
