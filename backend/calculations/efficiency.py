"""
KPI #3: Efficiency Calculation
Formula: (units_produced × ideal_cycle_time) / (employees_assigned × scheduled_hours) × 100

Includes inference engine for missing ideal_cycle_time
CORRECTED: Uses scheduled hours from shift, not actual run time
"""
from decimal import Decimal
from typing import Optional, Tuple
from datetime import time
from sqlalchemy.orm import Session
from backend.schemas.product import Product
from backend.schemas.production_entry import ProductionEntry
from backend.schemas.shift import Shift


DEFAULT_CYCLE_TIME = Decimal("0.25")  # 15 minutes per unit default
DEFAULT_SHIFT_HOURS = Decimal("8.0")  # 8 hours standard shift


def calculate_shift_hours(shift_start: time, shift_end: time) -> Decimal:
    """
    Calculate scheduled hours from shift start/end times
    Handles overnight shifts correctly

    Args:
        shift_start: Shift start time
        shift_end: Shift end time

    Returns:
        Decimal hours for the shift

    Examples:
        >>> calculate_shift_hours(time(7, 0), time(15, 30))  # 7am to 3:30pm
        Decimal('8.5')
        >>> calculate_shift_hours(time(23, 0), time(7, 0))   # 11pm to 7am (overnight)
        Decimal('8.0')
    """
    start_minutes = shift_start.hour * 60 + shift_start.minute
    end_minutes = shift_end.hour * 60 + shift_end.minute

    # Handle overnight shifts
    if end_minutes < start_minutes:
        total_minutes = (24 * 60 - start_minutes) + end_minutes
    else:
        total_minutes = end_minutes - start_minutes

    return Decimal(str(total_minutes / 60.0))


def infer_ideal_cycle_time(
    db: Session,
    product_id: int,
    current_entry_id: Optional[int] = None
) -> Tuple[Decimal, bool]:
    """
    Infer ideal cycle time from historical data or use default

    Args:
        db: Database session
        product_id: Product ID
        current_entry_id: Current entry ID to exclude from calculation

    Returns:
        Tuple of (cycle_time, was_inferred)
        was_inferred=True means historical avg was used
        was_inferred=False means default was used
    """
    # Get product's defined cycle time
    product = db.query(Product).filter(Product.product_id == product_id).first()

    if product and product.ideal_cycle_time is not None:
        return (Decimal(str(product.ideal_cycle_time)), False)

    # Try to calculate historical average for this product
    query = db.query(ProductionEntry).filter(
        ProductionEntry.product_id == product_id,
        ProductionEntry.efficiency_percentage.isnot(None),
        ProductionEntry.performance_percentage.isnot(None)
    )

    # Exclude current entry if updating
    if current_entry_id:
        query = query.filter(ProductionEntry.entry_id != current_entry_id)

    historical_entries = query.limit(10).all()

    if historical_entries:
        # Reverse-calculate ideal cycle time from past entries
        total_inferred = Decimal("0")
        count = 0

        for entry in historical_entries:
            # From efficiency: ideal_cycle_time = (efficiency/100 × employees × runtime) / units
            if entry.employees_assigned > 0 and entry.units_produced > 0:
                inferred = (
                    Decimal(str(entry.efficiency_percentage)) / 100
                    * entry.employees_assigned
                    * Decimal(str(entry.run_time_hours))
                ) / entry.units_produced
                total_inferred += inferred
                count += 1

        if count > 0:
            avg_cycle_time = total_inferred / count
            return (avg_cycle_time, True)

    # Use default if no historical data
    return (DEFAULT_CYCLE_TIME, False)


def calculate_efficiency(
    db: Session,
    entry: ProductionEntry,
    product: Optional[Product] = None
) -> Tuple[Decimal, Decimal, bool]:
    """
    Calculate efficiency percentage for a production entry

    CORRECTED FORMULA: Uses scheduled hours (from shift), not actual run time hours
    Formula: (units_produced × ideal_cycle_time) / (employees_assigned × scheduled_hours) × 100

    Args:
        db: Database session
        entry: Production entry
        product: Optional product object (fetched if not provided)

    Returns:
        Tuple of (efficiency_percentage, ideal_cycle_time_used, was_inferred)
    """
    # Get product if not provided
    if product is None:
        product = db.query(Product).filter(
            Product.product_id == entry.product_id
        ).first()

    # Get ideal cycle time (with inference if needed)
    if product and product.ideal_cycle_time is not None:
        ideal_cycle_time = Decimal(str(product.ideal_cycle_time))
        was_inferred = False
    else:
        ideal_cycle_time, was_inferred = infer_ideal_cycle_time(
            db, entry.product_id, entry.entry_id
        )

    # Get scheduled hours from shift
    shift = db.query(Shift).filter(Shift.shift_id == entry.shift_id).first()
    if shift and shift.start_time and shift.end_time:
        scheduled_hours = calculate_shift_hours(shift.start_time, shift.end_time)
    else:
        # Fallback to default 8-hour shift
        scheduled_hours = DEFAULT_SHIFT_HOURS

    # Calculate efficiency
    # CORRECTED Formula: (units_produced × ideal_cycle_time) / (employees_assigned × SCHEDULED_hours) × 100

    if entry.employees_assigned == 0 or scheduled_hours == 0:
        return (Decimal("0"), ideal_cycle_time, was_inferred)

    efficiency = (
        entry.units_produced * ideal_cycle_time
    ) / (
        entry.employees_assigned * scheduled_hours
    ) * 100

    # Cap at 150% (reasonable max efficiency accounting for learning/improvements)
    efficiency = min(efficiency, Decimal("150"))

    return (efficiency.quantize(Decimal("0.01")), ideal_cycle_time, was_inferred)


def update_efficiency_for_entry(
    db: Session,
    entry_id: int
) -> Optional[ProductionEntry]:
    """
    Update efficiency for a specific production entry

    Args:
        db: Database session
        entry_id: Production entry ID

    Returns:
        Updated production entry or None if not found
    """
    entry = db.query(ProductionEntry).filter(
        ProductionEntry.entry_id == entry_id
    ).first()

    if not entry:
        return None

    product = db.query(Product).filter(
        Product.product_id == entry.product_id
    ).first()

    efficiency, _, _ = calculate_efficiency(db, entry, product)

    entry.efficiency_percentage = efficiency
    db.commit()
    db.refresh(entry)

    return entry
