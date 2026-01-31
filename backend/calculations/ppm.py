"""
PPM (Parts Per Million) Calculation
PHASE 4: Quality metrics

PPM = (Total Defects / Total Units Inspected) * 1,000,000

Phase 1.2: Added pure calculation functions for service layer separation
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, cast, Date
from datetime import date
from decimal import Decimal
from typing import Optional

from backend.schemas.quality_entry import QualityEntry


# =============================================================================
# PURE CALCULATION FUNCTIONS (No Database Access)
# Phase 1.2: These functions can be unit tested without database
# =============================================================================

def calculate_ppm_pure(
    total_inspected: int,
    total_defects: int
) -> Decimal:
    """
    Pure PPM calculation - no database access.

    Formula: (Total Defects / Total Units Inspected) * 1,000,000

    Args:
        total_inspected: Total units inspected
        total_defects: Total defective units found

    Returns:
        PPM value as Decimal

    Examples:
        >>> calculate_ppm_pure(10000, 5)
        Decimal('500')  # 5 defects in 10000 = 500 PPM
    """
    if total_inspected <= 0:
        return Decimal("0")

    ppm = (Decimal(str(total_defects)) / Decimal(str(total_inspected))) * Decimal("1000000")
    return ppm.quantize(Decimal("0.01"))


def calculate_category_ppm_pure(
    category_defects: int,
    total_inspected: int
) -> Decimal:
    """
    Pure PPM calculation for a specific category - no database access.

    Args:
        category_defects: Defects in this category
        total_inspected: Total units inspected

    Returns:
        PPM value for this category
    """
    if total_inspected <= 0:
        return Decimal("0")

    ppm = (Decimal(str(category_defects)) / Decimal(str(total_inspected))) * Decimal("1000000")
    return ppm.quantize(Decimal("0.01"))


def calculate_defect_percentage_pure(
    defect_count: int,
    total_defects: int
) -> Decimal:
    """
    Pure defect percentage calculation for Pareto analysis.

    Args:
        defect_count: Count for this defect type
        total_defects: Total defects across all types

    Returns:
        Percentage of total defects
    """
    if total_defects <= 0:
        return Decimal("0")

    percentage = (Decimal(str(defect_count)) / Decimal(str(total_defects))) * 100
    return percentage.quantize(Decimal("0.01"))


def calculate_ppm(
    db: Session,
    work_order_id: str,
    start_date: date,
    end_date: date,
    client_id: Optional[str] = None
) -> tuple[Decimal, int, int]:
    """
    Calculate PPM (Parts Per Million) defect rate

    Args:
        db: Database session
        work_order_id: Work order to calculate PPM for
        start_date: Start of date range
        end_date: End of date range
        client_id: Optional client filter

    Returns: (ppm, total_inspected, total_defects)
    """

    # Build query for quality entries
    query = db.query(
        func.sum(QualityEntry.units_inspected).label('total_inspected'),
        func.sum(QualityEntry.units_defective).label('total_defects')
    ).filter(
        and_(
            QualityEntry.work_order_id == work_order_id,
            cast(QualityEntry.shift_date, Date) >= start_date,
            cast(QualityEntry.shift_date, Date) <= end_date
        )
    )

    if client_id:
        query = query.filter(QualityEntry.client_id == client_id)

    inspections = query.first()

    total_inspected = inspections.total_inspected or 0
    total_defects = inspections.total_defects or 0

    if total_inspected > 0:
        ppm = (Decimal(str(total_defects)) / Decimal(str(total_inspected))) * Decimal("1000000")
    else:
        ppm = Decimal("0")

    return (ppm, total_inspected, total_defects)


def calculate_ppm_by_category(
    db: Session,
    work_order_id: str,
    start_date: date,
    end_date: date,
    client_id: Optional[str] = None
) -> dict:
    """
    Calculate PPM broken down by inspection stage (replaces defect_category)
    """

    query = db.query(QualityEntry).filter(
        and_(
            QualityEntry.work_order_id == work_order_id,
            cast(QualityEntry.shift_date, Date) >= start_date,
            cast(QualityEntry.shift_date, Date) <= end_date,
            QualityEntry.inspection_stage.isnot(None)
        )
    )

    if client_id:
        query = query.filter(QualityEntry.client_id == client_id)

    inspections = query.all()

    # Calculate total inspected
    total_inspected = sum(i.units_inspected for i in inspections)

    # Group by inspection stage (instead of defect_category)
    categories = {}
    for insp in inspections:
        cat = insp.inspection_stage or "Uncategorized"
        if cat not in categories:
            categories[cat] = {"defects": 0, "ppm": Decimal("0")}

        categories[cat]["defects"] += insp.units_defective

    # Calculate PPM per category
    if total_inspected > 0:
        for cat in categories:
            defects = categories[cat]["defects"]
            categories[cat]["ppm"] = (Decimal(str(defects)) / Decimal(str(total_inspected))) * Decimal("1000000")

    return {
        "total_inspected": total_inspected,
        "categories": categories
    }


def identify_top_defects(
    db: Session,
    work_order_id: Optional[str] = None,
    start_date: date = None,
    end_date: date = None,
    client_id: Optional[str] = None,
    limit: int = 10
) -> list[dict]:
    """
    Identify top defect types by process step (Pareto analysis)
    Note: QualityEntry uses process_step instead of defect_type
    """

    query = db.query(QualityEntry).filter(
        QualityEntry.process_step.isnot(None)
    )

    if work_order_id:
        query = query.filter(QualityEntry.work_order_id == work_order_id)

    if client_id:
        query = query.filter(QualityEntry.client_id == client_id)

    if start_date and end_date:
        query = query.filter(
            and_(
                cast(QualityEntry.shift_date, Date) >= start_date,
                cast(QualityEntry.shift_date, Date) <= end_date
            )
        )

    inspections = query.all()

    # Group by process step (replaces defect_type)
    defect_types = {}
    total_defects = 0

    for insp in inspections:
        process_step = insp.process_step or "Unknown"
        if process_step not in defect_types:
            defect_types[process_step] = {
                "defect_type": process_step,
                "count": 0,
                "category": insp.inspection_stage
            }

        defect_types[process_step]["count"] += insp.units_defective
        total_defects += insp.units_defective

    # Convert to list and calculate percentages
    results = list(defect_types.values())

    if total_defects > 0:
        for item in results:
            item["percentage"] = (Decimal(str(item["count"])) / Decimal(str(total_defects))) * 100

    # Sort by count (highest first)
    results.sort(key=lambda x: x["count"], reverse=True)

    # Calculate cumulative percentage
    cumulative = Decimal("0")
    for item in results[:limit]:
        cumulative += item["percentage"]
        item["cumulative_percentage"] = cumulative

    return results[:limit]


def calculate_cost_of_quality(
    db: Session,
    work_order_id: str,
    start_date: date,
    end_date: date,
    client_id: Optional[str] = None,
    scrap_cost_per_unit: Optional[Decimal] = None,
    rework_cost_per_unit: Optional[Decimal] = None
) -> dict:
    """
    Calculate Cost of Quality (COQ)

    COQ = Scrap Cost + Rework Cost + Inspection Cost
    """

    query = db.query(QualityEntry).filter(
        and_(
            QualityEntry.work_order_id == work_order_id,
            cast(QualityEntry.shift_date, Date) >= start_date,
            cast(QualityEntry.shift_date, Date) <= end_date
        )
    )

    if client_id:
        query = query.filter(QualityEntry.client_id == client_id)

    inspections = query.all()

    total_scrap = sum(i.units_scrapped for i in inspections)
    total_rework = sum(i.units_reworked for i in inspections)

    # Use default costs if not provided
    if not scrap_cost_per_unit:
        scrap_cost_per_unit = Decimal("10.00")  # Default $10 per unit

    if not rework_cost_per_unit:
        rework_cost_per_unit = Decimal("3.00")  # Default $3 per unit

    scrap_cost = Decimal(str(total_scrap)) * scrap_cost_per_unit
    rework_cost = Decimal(str(total_rework)) * rework_cost_per_unit

    # Inspection cost (simplified)
    inspection_cost = Decimal(str(len(inspections))) * Decimal("50.00")  # $50 per inspection

    total_coq = scrap_cost + rework_cost + inspection_cost

    return {
        "total_scrap_units": total_scrap,
        "total_rework_units": total_rework,
        "scrap_cost": scrap_cost,
        "rework_cost": rework_cost,
        "inspection_cost": inspection_cost,
        "total_cost_of_quality": total_coq
    }
