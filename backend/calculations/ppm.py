"""
PPM (Parts Per Million) Calculation
PHASE 4: Quality metrics

PPM = (Total Defects / Total Units Inspected) * 1,000,000
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date
from decimal import Decimal
from typing import Optional

from backend.schemas.quality import QualityInspection


def calculate_ppm(
    db: Session,
    product_id: int,
    shift_id: int,
    start_date: date,
    end_date: date
) -> tuple[Decimal, int, int]:
    """
    Calculate PPM (Parts Per Million) defect rate

    Returns: (ppm, total_inspected, total_defects)
    """

    # Sum all inspections for period
    inspections = db.query(
        func.sum(QualityInspection.units_inspected).label('total_inspected'),
        func.sum(QualityInspection.defects_found).label('total_defects')
    ).filter(
        and_(
            QualityInspection.product_id == product_id,
            QualityInspection.shift_id == shift_id,
            QualityInspection.inspection_date >= start_date,
            QualityInspection.inspection_date <= end_date
        )
    ).first()

    total_inspected = inspections.total_inspected or 0
    total_defects = inspections.total_defects or 0

    if total_inspected > 0:
        ppm = (Decimal(str(total_defects)) / Decimal(str(total_inspected))) * Decimal("1000000")
    else:
        ppm = Decimal("0")

    return (ppm, total_inspected, total_defects)


def calculate_ppm_by_category(
    db: Session,
    product_id: int,
    start_date: date,
    end_date: date
) -> dict:
    """
    Calculate PPM broken down by defect category
    """

    inspections = db.query(QualityInspection).filter(
        and_(
            QualityInspection.product_id == product_id,
            QualityInspection.inspection_date >= start_date,
            QualityInspection.inspection_date <= end_date,
            QualityInspection.defect_category.isnot(None)
        )
    ).all()

    # Calculate total inspected
    total_inspected = sum(i.units_inspected for i in inspections)

    # Group by category
    categories = {}
    for insp in inspections:
        cat = insp.defect_category or "Uncategorized"
        if cat not in categories:
            categories[cat] = {"defects": 0, "ppm": Decimal("0")}

        categories[cat]["defects"] += insp.defects_found

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
    product_id: Optional[int] = None,
    start_date: date = None,
    end_date: date = None,
    limit: int = 10
) -> list[dict]:
    """
    Identify top defect types by frequency (Pareto analysis)
    """

    query = db.query(QualityInspection).filter(
        QualityInspection.defect_type.isnot(None)
    )

    if product_id:
        query = query.filter(QualityInspection.product_id == product_id)

    if start_date and end_date:
        query = query.filter(
            and_(
                QualityInspection.inspection_date >= start_date,
                QualityInspection.inspection_date <= end_date
            )
        )

    inspections = query.all()

    # Group by defect type
    defect_types = {}
    total_defects = 0

    for insp in inspections:
        defect_type = insp.defect_type or "Unknown"
        if defect_type not in defect_types:
            defect_types[defect_type] = {
                "defect_type": defect_type,
                "count": 0,
                "category": insp.defect_category
            }

        defect_types[defect_type]["count"] += insp.defects_found
        total_defects += insp.defects_found

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
    product_id: int,
    start_date: date,
    end_date: date,
    scrap_cost_per_unit: Optional[Decimal] = None,
    rework_cost_per_unit: Optional[Decimal] = None
) -> dict:
    """
    Calculate Cost of Quality (COQ)

    COQ = Scrap Cost + Rework Cost + Inspection Cost
    """

    inspections = db.query(QualityInspection).filter(
        and_(
            QualityInspection.product_id == product_id,
            QualityInspection.inspection_date >= start_date,
            QualityInspection.inspection_date <= end_date
        )
    ).all()

    total_scrap = sum(i.scrap_units for i in inspections)
    total_rework = sum(i.rework_units for i in inspections)

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
