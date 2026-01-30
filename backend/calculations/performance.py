"""
KPI #9: Performance Calculation
Formula: (ideal_cycle_time × units_produced) / run_time_hours × 100

Includes inference engine for missing ideal_cycle_time
"""
from decimal import Decimal
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from backend.schemas.product import Product
from backend.schemas.production_entry import ProductionEntry
from backend.calculations.efficiency import infer_ideal_cycle_time


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
