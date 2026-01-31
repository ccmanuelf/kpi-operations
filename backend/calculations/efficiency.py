"""
KPI #3: Efficiency Calculation
Formula: (units_produced × ideal_cycle_time) / (employees_assigned × scheduled_hours) × 100

Includes inference engine for missing ideal_cycle_time
CORRECTED: Uses scheduled hours from shift, not actual run time

Enhanced with employees_assigned fallback chain per audit requirement:
employees_assigned → employees_present → historical_shift_average → default

Phase 7.2: Enhanced with client-level configuration overrides
Phase 1.2: Added pure calculation functions for service layer separation
"""
from decimal import Decimal
from typing import Optional, Tuple
from datetime import time, date
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from backend.schemas.product import Product
from backend.schemas.production_entry import ProductionEntry
from backend.schemas.shift import Shift
from backend.schemas.coverage_entry import CoverageEntry
from backend.crud.client_config import get_client_config_or_defaults


# Fallback defaults (used only if client config lookup fails)
DEFAULT_CYCLE_TIME = Decimal("0.25")  # 15 minutes per unit default
DEFAULT_SHIFT_HOURS = Decimal("8.0")  # 8 hours standard shift
DEFAULT_EMPLOYEES = 1  # Minimum employees for calculation


# =============================================================================
# PURE CALCULATION FUNCTIONS (No Database Access)
# Phase 1.2: These functions can be unit tested without database
# =============================================================================

def calculate_efficiency_pure(
    units_produced: int,
    ideal_cycle_time: Decimal,
    employees_count: int,
    scheduled_hours: Decimal
) -> Decimal:
    """
    Pure efficiency calculation - no database access.

    Formula: (units_produced × ideal_cycle_time) / (employees × scheduled_hours) × 100

    Args:
        units_produced: Number of units produced
        ideal_cycle_time: Ideal cycle time in hours per unit
        employees_count: Number of employees assigned
        scheduled_hours: Total scheduled hours for the shift

    Returns:
        Efficiency percentage as Decimal (capped at 150%)

    Examples:
        >>> calculate_efficiency_pure(100, Decimal("0.1"), 5, Decimal("8"))
        Decimal('25.00')  # (100 × 0.1) / (5 × 8) × 100 = 25%
    """
    if employees_count <= 0 or scheduled_hours <= 0:
        return Decimal("0")

    efficiency = (
        Decimal(str(units_produced)) * ideal_cycle_time
    ) / (
        Decimal(str(employees_count)) * scheduled_hours
    ) * 100

    # Cap at 150% (reasonable max efficiency accounting for learning/improvements)
    efficiency = min(efficiency, Decimal("150"))

    return efficiency.quantize(Decimal("0.01"))


def calculate_shift_hours_pure(
    shift_start_hour: int,
    shift_start_minute: int,
    shift_end_hour: int,
    shift_end_minute: int
) -> Decimal:
    """
    Pure shift hours calculation from time components.

    Handles overnight shifts correctly.

    Args:
        shift_start_hour: Start hour (0-23)
        shift_start_minute: Start minute (0-59)
        shift_end_hour: End hour (0-23)
        shift_end_minute: End minute (0-59)

    Returns:
        Decimal hours for the shift

    Examples:
        >>> calculate_shift_hours_pure(7, 0, 15, 30)  # 7am to 3:30pm
        Decimal('8.5')
        >>> calculate_shift_hours_pure(23, 0, 7, 0)   # 11pm to 7am (overnight)
        Decimal('8.0')
    """
    start_minutes = shift_start_hour * 60 + shift_start_minute
    end_minutes = shift_end_hour * 60 + shift_end_minute

    # Handle overnight shifts
    if end_minutes < start_minutes:
        total_minutes = (24 * 60 - start_minutes) + end_minutes
    else:
        total_minutes = end_minutes - start_minutes

    return Decimal(str(total_minutes / 60.0))


def get_client_cycle_time_default(db: Session, client_id: Optional[str] = None) -> Decimal:
    """
    Get the default cycle time for a client from their configuration.
    Falls back to global default if no client config exists.

    Args:
        db: Database session
        client_id: Client ID (optional)

    Returns:
        Default cycle time in hours as Decimal
    """
    if not client_id:
        return DEFAULT_CYCLE_TIME

    try:
        config = get_client_config_or_defaults(db, client_id)
        return Decimal(str(config.get("default_cycle_time_hours", DEFAULT_CYCLE_TIME)))
    except Exception:
        return DEFAULT_CYCLE_TIME


# =============================================================================
# FloatingPool Integration (Audit Requirement)
# =============================================================================

def get_floating_pool_coverage_count(
    db: Session,
    client_id: str,
    shift_date: date,
    shift_id: Optional[int] = None
) -> int:
    """
    Get count of floating pool employees providing coverage on a specific shift date.

    This integrates FloatingPool into efficiency calculation per audit requirement.

    Args:
        db: Database session
        client_id: Client ID for tenant isolation
        shift_date: The shift date to check for coverage
        shift_id: Optional shift ID for more specific filtering

    Returns:
        Number of floating pool employees providing coverage
    """
    query = db.query(func.count(CoverageEntry.coverage_entry_id)).filter(
        and_(
            CoverageEntry.client_id == client_id,
            func.date(CoverageEntry.shift_date) == shift_date
        )
    )

    if shift_id:
        query = query.filter(CoverageEntry.shift_id == shift_id)

    coverage_count = query.scalar() or 0
    return coverage_count


# =============================================================================
# Employees Assigned Inference Chain (Audit Requirement)
# =============================================================================

@dataclass
class InferredEmployees:
    """Result of employees inference with metadata for ESTIMATED flag"""
    count: int
    is_inferred: bool
    inference_source: str  # "employees_assigned", "employees_present", "historical_avg", "default"
    confidence_score: float  # 1.0 for actual, 0.8 for present, 0.5 for historical, 0.3 for default


def infer_employees_count(
    db: Session,
    entry: ProductionEntry,
    include_floating_pool: bool = True
) -> InferredEmployees:
    """
    Infer the employees count using the specification fallback chain:
    employees_assigned → employees_present → historical_shift_average → default

    Enhanced with FloatingPool integration per audit requirement.
    When include_floating_pool=True, adds coverage employees to the count.

    Args:
        db: Database session
        entry: Production entry object
        include_floating_pool: Whether to add floating pool coverage to the count

    Returns:
        InferredEmployees with the resolved count and inference metadata
    """
    base_count = 0
    is_inferred = False
    inference_source = ""
    confidence_score = 0.0

    # Level 1: Use employees_assigned (highest confidence - explicit value)
    if entry.employees_assigned is not None and entry.employees_assigned > 0:
        base_count = entry.employees_assigned
        is_inferred = False
        inference_source = "employees_assigned"
        confidence_score = 1.0

    # Level 2: Fall back to employees_present (medium-high confidence)
    elif hasattr(entry, 'employees_present') and entry.employees_present is not None and entry.employees_present > 0:
        base_count = entry.employees_present
        is_inferred = True
        inference_source = "employees_present"
        confidence_score = 0.8

    # Level 3: Calculate historical average for this shift (medium confidence)
    elif entry.shift_id:
        historical_avg = db.query(func.avg(ProductionEntry.employees_assigned)).filter(
            ProductionEntry.shift_id == entry.shift_id,
            ProductionEntry.employees_assigned.isnot(None),
            ProductionEntry.employees_assigned > 0,
            ProductionEntry.production_entry_id != (entry.production_entry_id if hasattr(entry, 'production_entry_id') else None)
        ).scalar()

        if historical_avg is not None and historical_avg > 0:
            base_count = max(1, int(round(float(historical_avg))))
            is_inferred = True
            inference_source = "historical_shift_avg"
            confidence_score = 0.5
        else:
            base_count = DEFAULT_EMPLOYEES
            is_inferred = True
            inference_source = "default"
            confidence_score = 0.3
    else:
        # Level 4: Use default minimum (low confidence)
        base_count = DEFAULT_EMPLOYEES
        is_inferred = True
        inference_source = "default"
        confidence_score = 0.3

    # ENHANCEMENT: Add floating pool coverage employees (per audit requirement)
    floating_pool_count = 0
    if include_floating_pool and hasattr(entry, 'client_id') and hasattr(entry, 'shift_date'):
        try:
            shift_date_value = entry.shift_date.date() if hasattr(entry.shift_date, 'date') else entry.shift_date
            floating_pool_count = get_floating_pool_coverage_count(
                db,
                entry.client_id,
                shift_date_value,
                entry.shift_id if hasattr(entry, 'shift_id') else None
            )
        except Exception:
            # Silently ignore errors in floating pool lookup
            floating_pool_count = 0

    total_count = base_count + floating_pool_count

    # Update inference source if floating pool was used
    if floating_pool_count > 0:
        inference_source = f"{inference_source}+floating_pool({floating_pool_count})"
        # Slightly reduce confidence when using floating pool (workforce composition changed)
        confidence_score = min(confidence_score, 0.9)

    return InferredEmployees(
        count=total_count,
        is_inferred=is_inferred,
        inference_source=inference_source,
        confidence_score=confidence_score
    )


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
    current_entry_id: Optional[str] = None,
    client_id: Optional[str] = None
) -> Tuple[Decimal, bool]:
    """
    Infer ideal cycle time from historical data or use default

    Phase 7.2: Uses client-specific default cycle time when available

    Args:
        db: Database session
        product_id: Product ID
        current_entry_id: Current entry ID to exclude from calculation
        client_id: Client ID for client-specific defaults (optional)

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
        query = query.filter(ProductionEntry.production_entry_id != current_entry_id)

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

    # Use client-specific or global default if no historical data
    # Return True for was_inferred since this is a fallback value, not from product
    default_cycle_time = get_client_cycle_time_default(db, client_id)
    return (default_cycle_time, True)


def calculate_efficiency(
    db: Session,
    entry: ProductionEntry,
    product: Optional[Product] = None
) -> Tuple[Decimal, Decimal, bool]:
    """
    Calculate efficiency percentage for a production entry

    CORRECTED FORMULA: Uses scheduled hours (from shift), not actual run time hours
    Formula: (units_produced × ideal_cycle_time) / (employees_assigned × scheduled_hours) × 100

    Enhanced: Uses employees inference chain when employees_assigned is 0/missing
    employees_assigned → employees_present → historical_shift_avg → default

    Phase 7.2: Uses client-specific default cycle time when no product/historical data

    Args:
        db: Database session
        entry: Production entry
        product: Optional product object (fetched if not provided)

    Returns:
        Tuple of (efficiency_percentage, ideal_cycle_time_used, was_inferred)
        Note: was_inferred is True if EITHER cycle_time OR employees were inferred
    """
    # Get product if not provided
    if product is None:
        product = db.query(Product).filter(
            Product.product_id == entry.product_id
        ).first()

    # Get client_id from entry for client-specific defaults
    client_id = getattr(entry, 'client_id', None)

    # Get ideal cycle time (with inference if needed)
    if product and product.ideal_cycle_time is not None:
        ideal_cycle_time = Decimal(str(product.ideal_cycle_time))
        cycle_time_inferred = False
    else:
        ideal_cycle_time, cycle_time_inferred = infer_ideal_cycle_time(
            db, entry.product_id, entry.production_entry_id, client_id
        )

    # Get scheduled hours from shift
    shift = db.query(Shift).filter(Shift.shift_id == entry.shift_id).first()
    if shift and shift.start_time and shift.end_time:
        scheduled_hours = calculate_shift_hours(shift.start_time, shift.end_time)
    else:
        # Fallback to default 8-hour shift
        scheduled_hours = DEFAULT_SHIFT_HOURS

    # ENHANCED: Use inference chain for employees count
    inferred_employees = infer_employees_count(db, entry)
    employees_count = inferred_employees.count
    employees_inferred = inferred_employees.is_inferred

    # Combined inference flag - True if EITHER value was inferred
    was_inferred = cycle_time_inferred or employees_inferred

    # Calculate efficiency
    # Formula: (units_produced × ideal_cycle_time) / (employees × SCHEDULED_hours) × 100

    if scheduled_hours == 0:
        return (Decimal("0"), ideal_cycle_time, was_inferred)

    efficiency = (
        entry.units_produced * ideal_cycle_time
    ) / (
        employees_count * scheduled_hours
    ) * 100

    # Cap at 150% (reasonable max efficiency accounting for learning/improvements)
    efficiency = min(efficiency, Decimal("150"))

    return (efficiency.quantize(Decimal("0.01")), ideal_cycle_time, was_inferred)


def calculate_efficiency_with_metadata(
    db: Session,
    entry: ProductionEntry,
    product: Optional[Product] = None
) -> dict:
    """
    Calculate efficiency with full inference metadata for API responses.
    This exposes the ESTIMATED flag per audit requirement.

    Phase 7.2: Uses client-specific configuration for defaults

    Args:
        db: Database session
        entry: Production entry
        product: Optional product object

    Returns:
        Dict with efficiency result and detailed inference metadata
    """
    # Get product if not provided
    if product is None:
        product = db.query(Product).filter(
            Product.product_id == entry.product_id
        ).first()

    # Get client_id from entry for client-specific defaults
    client_id = getattr(entry, 'client_id', None)

    # Get ideal cycle time (with inference if needed)
    if product and product.ideal_cycle_time is not None:
        ideal_cycle_time = Decimal(str(product.ideal_cycle_time))
        cycle_time_inferred = False
        cycle_time_source = "product_standard"
        cycle_time_confidence = 1.0
    else:
        ideal_cycle_time, cycle_time_inferred = infer_ideal_cycle_time(
            db, entry.product_id, entry.production_entry_id, client_id
        )
        cycle_time_source = "historical_avg" if cycle_time_inferred else "client_default" if client_id else "global_default"
        cycle_time_confidence = 0.6 if cycle_time_inferred else 0.4 if client_id else 0.3

    # Get scheduled hours from shift
    shift = db.query(Shift).filter(Shift.shift_id == entry.shift_id).first()
    if shift and shift.start_time and shift.end_time:
        scheduled_hours = calculate_shift_hours(shift.start_time, shift.end_time)
        hours_inferred = False
    else:
        scheduled_hours = DEFAULT_SHIFT_HOURS
        hours_inferred = True

    # Get employees count with inference
    inferred_employees = infer_employees_count(db, entry)
    employees_count = inferred_employees.count

    # Calculate efficiency
    if scheduled_hours == 0:
        efficiency = Decimal("0")
    else:
        efficiency = (
            entry.units_produced * ideal_cycle_time
        ) / (
            employees_count * scheduled_hours
        ) * 100
        efficiency = min(efficiency, Decimal("150"))

    # Determine overall inference status
    any_inferred = cycle_time_inferred or inferred_employees.is_inferred or hours_inferred

    # Calculate minimum confidence score across all inferred values
    confidence_scores = []
    if cycle_time_inferred:
        confidence_scores.append(cycle_time_confidence)
    if inferred_employees.is_inferred:
        confidence_scores.append(inferred_employees.confidence_score)
    if hours_inferred:
        confidence_scores.append(0.5)  # Default shift hours has medium confidence

    min_confidence = min(confidence_scores) if confidence_scores else 1.0

    return {
        "efficiency_percentage": efficiency.quantize(Decimal("0.01")),
        "ideal_cycle_time_used": ideal_cycle_time,
        "employees_used": employees_count,
        "scheduled_hours_used": scheduled_hours,
        "inference": {
            "is_estimated": any_inferred,
            "confidence_score": min_confidence,
            "cycle_time": {
                "is_inferred": cycle_time_inferred,
                "source": cycle_time_source,
                "confidence": cycle_time_confidence
            },
            "employees": {
                "is_inferred": inferred_employees.is_inferred,
                "source": inferred_employees.inference_source,
                "confidence": inferred_employees.confidence_score
            },
            "scheduled_hours": {
                "is_inferred": hours_inferred,
                "source": "shift_times" if not hours_inferred else "default"
            }
        }
    }


def update_efficiency_for_entry(
    db: Session,
    entry_id: str
) -> Optional[ProductionEntry]:
    """
    Update efficiency for a specific production entry

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

    efficiency, _, _ = calculate_efficiency(db, entry, product)

    entry.efficiency_percentage = efficiency
    db.commit()
    db.refresh(entry)

    return entry
