"""
KPI #9: Performance Calculation
Formula: (ideal_cycle_time × units_produced) / run_time_hours × 100

Includes inference engine for missing ideal_cycle_time

Phase 1.2: Added pure calculation functions for service layer separation
"""
from decimal import Decimal
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from backend.schemas.product import Product
from backend.schemas.production_entry import ProductionEntry
from backend.calculations.efficiency import infer_ideal_cycle_time


# =============================================================================
# PURE CALCULATION FUNCTIONS (No Database Access)
# Phase 1.2: These functions can be unit tested without database
# =============================================================================

def calculate_performance_pure(
    units_produced: int,
    run_time_hours: Decimal,
    ideal_cycle_time: Decimal
) -> Tuple[Decimal, Decimal]:
    """
    Pure performance calculation - no database access.

    Formula: (ideal_cycle_time × units_produced) / run_time_hours × 100

    Args:
        units_produced: Number of units produced
        run_time_hours: Actual run time in hours
        ideal_cycle_time: Ideal cycle time in hours per unit

    Returns:
        Tuple of (performance_percentage, actual_rate)
        - performance_percentage: Performance as percentage (capped at 150%)
        - actual_rate: Actual units per hour achieved

    Examples:
        >>> calculate_performance_pure(100, Decimal("8"), Decimal("0.1"))
        (Decimal('125.00'), Decimal('12.50'))
    """
    if run_time_hours <= 0:
        return (Decimal("0"), Decimal("0"))

    # Calculate actual rate (units per hour)
    actual_rate = Decimal(str(units_produced)) / run_time_hours

    # Calculate performance percentage
    performance = (
        ideal_cycle_time * Decimal(str(units_produced))
    ) / run_time_hours * 100

    # Cap at 150% (reasonable max performance)
    performance = min(performance, Decimal("150"))

    return (performance.quantize(Decimal("0.01")), actual_rate.quantize(Decimal("0.01")))


def calculate_quality_rate_pure(
    units_produced: int,
    defect_count: int,
    scrap_count: int
) -> Tuple[Decimal, int]:
    """
    Pure quality rate calculation - no database access.

    Formula: ((units_produced - defects - scrap) / units_produced) × 100

    Args:
        units_produced: Total units produced
        defect_count: Number of defective units
        scrap_count: Number of scrapped units

    Returns:
        Tuple of (quality_rate_percentage, good_units)

    Examples:
        >>> calculate_quality_rate_pure(100, 5, 3)
        (Decimal('92.00'), 92)
    """
    if units_produced == 0:
        return (Decimal("0"), 0)

    good_units = units_produced - defect_count - scrap_count
    good_units = max(0, good_units)  # Ensure non-negative

    quality_rate = Decimal(str(good_units)) / Decimal(str(units_produced)) * Decimal("100")

    return (max(Decimal("0"), quality_rate.quantize(Decimal("0.01"))), good_units)


def calculate_oee_pure(
    availability: Decimal,
    performance: Decimal,
    quality: Decimal
) -> Decimal:
    """
    Pure OEE calculation - no database access.

    Formula: Availability × Performance × Quality (all as percentages)

    Args:
        availability: Availability percentage (0-100)
        performance: Performance percentage (0-100)
        quality: Quality rate percentage (0-100)

    Returns:
        OEE percentage

    Examples:
        >>> calculate_oee_pure(Decimal("95"), Decimal("85"), Decimal("99"))
        Decimal('79.92')
    """
    oee = (availability / 100) * (performance / 100) * (quality / 100) * 100
    return oee.quantize(Decimal("0.01"))


def calculate_performance(
    db: Session,
    entry: ProductionEntry,
    product: Optional[Product] = None
) -> Tuple[Decimal, Decimal, bool]:
    """
    Calculate performance percentage for a production entry

    Args:
        db: Database session
        entry: Production entry
        product: Optional product object (fetched if not provided)

    Returns:
        Tuple of (performance_percentage, ideal_cycle_time_used, was_inferred)
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
            db, entry.product_id, entry.production_entry_id
        )

    # Calculate performance
    # Formula: (ideal_cycle_time × units_produced) / run_time_hours × 100

    if entry.run_time_hours == 0:
        return (Decimal("0"), ideal_cycle_time, was_inferred)

    performance = (
        ideal_cycle_time * entry.units_produced
    ) / Decimal(str(entry.run_time_hours)) * 100

    # Cap at 150% (reasonable max performance)
    performance = min(performance, Decimal("150"))

    return (performance.quantize(Decimal("0.01")), ideal_cycle_time, was_inferred)


def update_performance_for_entry(
    db: Session,
    entry_id: str
) -> Optional[ProductionEntry]:
    """
    Update performance for a specific production entry

    Args:
        db: Database session
        entry_id: Production entry ID (string)

    Returns:
        Updated production entry or None if not found
    """
    entry = db.query(ProductionEntry).filter(
        ProductionEntry.production_entry_id == entry_id
    ).first()

    if not entry:
        return None

    product = db.query(Product).filter(
        Product.product_id == entry.product_id
    ).first()

    performance, _, _ = calculate_performance(db, entry, product)

    entry.performance_percentage = performance
    db.commit()
    db.refresh(entry)

    return entry


def calculate_quality_rate(entry: ProductionEntry) -> Decimal:
    """
    Calculate quality rate percentage
    Formula: ((units_produced - defects - scrap) / units_produced) × 100

    Args:
        entry: Production entry

    Returns:
        Quality rate as percentage
    """
    if entry.units_produced == 0:
        return Decimal("0")

    good_units = entry.units_produced - (entry.defect_count or 0) - (entry.scrap_count or 0)
    # Use Decimal for precise calculation
    quality_rate = Decimal(str(good_units)) / Decimal(str(entry.units_produced)) * Decimal("100")

    return max(Decimal("0"), quality_rate.quantize(Decimal("0.01")))


def calculate_oee(
    db: Session,
    entry: ProductionEntry,
    product: Optional[Product] = None
) -> Tuple[Decimal, dict]:
    """
    Calculate Overall Equipment Effectiveness (OEE)
    Formula: Availability × Performance × Quality

    For Phase 1, we focus on Performance × Quality
    (Availability requires downtime tracking - Phase 2)

    Args:
        db: Database session
        entry: Production entry
        product: Optional product object

    Returns:
        Tuple of (oee_percentage, components_dict)
    """
    # Get performance
    performance, _, _ = calculate_performance(db, entry, product)

    # Get quality rate
    quality = calculate_quality_rate(entry)

    # Simplified OEE (assuming 100% availability for Phase 1)
    availability = Decimal("100")

    oee = (availability / 100) * (performance / 100) * (quality / 100) * 100

    components = {
        "availability": availability,
        "performance": performance,
        "quality": quality,
        "oee": oee.quantize(Decimal("0.01"))
    }

    return (oee.quantize(Decimal("0.01")), components)
