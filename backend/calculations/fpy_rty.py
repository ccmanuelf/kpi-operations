"""
FPY (First Pass Yield) and RTY (Rolled Throughput Yield) Calculations
PHASE 4: Quality yield metrics

FPY = (Units Passed First Time / Total Units Processed) * 100
RTY = FPY1 × FPY2 × FPY3 × ... × FPYn (for all process steps)
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date
from decimal import Decimal
from typing import Optional, List
import math

from backend.schemas.quality_entry import QualityEntry
from backend.schemas.production_entry import ProductionEntry


def calculate_fpy(
    db: Session,
    product_id: int,
    start_date: date,
    end_date: date,
    inspection_stage: Optional[str] = None
) -> tuple[Decimal, int, int]:
    """
    Calculate First Pass Yield for a specific inspection stage

    FPY = (Units Passed / Units Inspected) * 100

    Returns: (fpy_percentage, first_pass_good, total_units)
    """
    from datetime import datetime

    # Convert date to datetime for comparison
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Note: QualityEntry doesn't have product_id - use work_order/job based filtering
    # For now, get all quality entries in date range
    query = db.query(QualityEntry).filter(
        and_(
            QualityEntry.shift_date >= start_datetime,
            QualityEntry.shift_date <= end_datetime
        )
    )

    if inspection_stage:
        query = query.filter(QualityEntry.inspection_stage == inspection_stage)

    inspections = query.all()

    if not inspections:
        return (Decimal("0"), 0, 0)

    total_units = sum(i.units_inspected or 0 for i in inspections)
    total_passed = sum(i.units_passed or 0 for i in inspections)
    total_rework = sum(i.units_reworked or 0 for i in inspections)

    # First pass good = units_passed (already calculated)
    first_pass_good = total_passed

    if total_units > 0:
        fpy = (Decimal(str(first_pass_good)) / Decimal(str(total_units))) * 100
    else:
        fpy = Decimal("0")

    return (fpy, first_pass_good, total_units)


def calculate_rty(
    db: Session,
    product_id: int,
    start_date: date,
    end_date: date,
    process_steps: Optional[List[str]] = None
) -> tuple[Decimal, List[dict]]:
    """
    Calculate Rolled Throughput Yield across all process steps

    RTY = FPY_step1 × FPY_step2 × ... × FPY_stepN

    process_steps: List of inspection stages (e.g., ['Incoming', 'In-Process', 'Final'])

    Returns: (rty_percentage, step_details)
    """

    if not process_steps:
        # Default apparel manufacturing stages
        process_steps = ['Incoming', 'In-Process', 'Final']

    step_yields = []
    rty = Decimal("1.0")  # Start at 100% (1.0)

    for step in process_steps:
        fpy, good, total = calculate_fpy(
            db, product_id, start_date, end_date, inspection_stage=step
        )

        # Convert percentage to decimal for multiplication
        fpy_decimal = fpy / 100

        # Multiply for RTY
        rty = rty * fpy_decimal

        step_yields.append({
            "step": step,
            "fpy_percentage": fpy,
            "first_pass_good": good,
            "total_units": total
        })

    # Convert RTY back to percentage
    rty_percentage = rty * 100

    return (rty_percentage, step_yields)


def calculate_process_yield(
    db: Session,
    product_id: int,
    start_date: date,
    end_date: date
) -> dict:
    """
    Calculate overall process yield including scrap rate

    Process Yield = ((Total Produced - Total Scrapped) / Total Produced) * 100
    """
    from datetime import datetime

    # Convert date to datetime for comparison
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Get production data
    production = db.query(ProductionEntry).filter(
        and_(
            ProductionEntry.product_id == product_id,
            ProductionEntry.production_date >= start_datetime,
            ProductionEntry.production_date <= end_datetime
        )
    ).all()

    total_produced = sum(p.units_produced or 0 for p in production)
    total_scrap = sum(p.scrap_count or 0 for p in production)
    total_defects = sum(p.defect_count or 0 for p in production)

    # Get quality entry data
    inspections = db.query(QualityEntry).filter(
        and_(
            QualityEntry.shift_date >= start_datetime,
            QualityEntry.shift_date <= end_datetime
        )
    ).all()

    inspection_scrap = sum(i.units_scrapped or 0 for i in inspections)
    total_scrap += inspection_scrap

    # Calculate yield
    if total_produced > 0:
        good_units = total_produced - total_scrap - total_defects
        process_yield = (Decimal(str(good_units)) / Decimal(str(total_produced))) * 100
        scrap_rate = (Decimal(str(total_scrap)) / Decimal(str(total_produced))) * 100
    else:
        process_yield = Decimal("0")
        scrap_rate = Decimal("0")
        good_units = 0

    return {
        "process_yield": process_yield,
        "scrap_rate": scrap_rate,
        "total_produced": total_produced,
        "good_units": good_units,
        "total_scrap": total_scrap,
        "total_defects": total_defects
    }


def calculate_defect_escape_rate(
    db: Session,
    product_id: int,
    start_date: date,
    end_date: date
) -> Decimal:
    """
    Calculate Defect Escape Rate

    Escape Rate = (Defects Found at Final / Total Defects Found) * 100

    Measures how many defects escape earlier inspection stages
    """
    from datetime import datetime

    # Convert date to datetime for comparison
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Get all quality entries
    all_inspections = db.query(QualityEntry).filter(
        and_(
            QualityEntry.shift_date >= start_datetime,
            QualityEntry.shift_date <= end_datetime
        )
    ).all()

    if not all_inspections:
        return Decimal("0")

    # Defects found at final inspection
    final_defects = sum(
        i.units_defective or 0 for i in all_inspections
        if i.inspection_stage == 'Final'
    )

    # Total defects found
    total_defects = sum(i.units_defective or 0 for i in all_inspections)

    if total_defects > 0:
        escape_rate = (Decimal(str(final_defects)) / Decimal(str(total_defects))) * 100
    else:
        escape_rate = Decimal("0")

    return escape_rate


def calculate_quality_score(
    db: Session,
    product_id: int,
    start_date: date,
    end_date: date
) -> dict:
    """
    Calculate comprehensive quality score (0-100)

    Weighted combination of:
    - FPY (40%)
    - RTY (30%)
    - Scrap Rate (20%)
    - Defect Escape Rate (10%)
    """

    # Get metrics
    fpy, _, _ = calculate_fpy(db, product_id, start_date, end_date)
    rty, _ = calculate_rty(db, product_id, start_date, end_date)
    process_data = calculate_process_yield(db, product_id, start_date, end_date)
    escape_rate = calculate_defect_escape_rate(db, product_id, start_date, end_date)

    # Scrap rate (inverse score - lower is better)
    scrap_score = max(Decimal("0"), 100 - process_data["scrap_rate"])

    # Escape rate (inverse score - lower is better)
    escape_score = max(Decimal("0"), 100 - escape_rate)

    # Weighted quality score
    quality_score = (
        fpy * Decimal("0.40") +
        rty * Decimal("0.30") +
        scrap_score * Decimal("0.20") +
        escape_score * Decimal("0.10")
    )

    # Determine grade
    if quality_score >= 95:
        grade = "A+"
        interpretation = "Excellent - World Class Quality"
    elif quality_score >= 90:
        grade = "A"
        interpretation = "Excellent Quality"
    elif quality_score >= 85:
        grade = "B+"
        interpretation = "Very Good Quality"
    elif quality_score >= 80:
        grade = "B"
        interpretation = "Good Quality"
    elif quality_score >= 75:
        grade = "C+"
        interpretation = "Acceptable Quality"
    elif quality_score >= 70:
        grade = "C"
        interpretation = "Needs Improvement"
    else:
        grade = "D"
        interpretation = "Poor Quality - Immediate Action Required"

    return {
        "quality_score": quality_score,
        "grade": grade,
        "interpretation": interpretation,
        "components": {
            "fpy": fpy,
            "rty": rty,
            "scrap_rate": process_data["scrap_rate"],
            "escape_rate": escape_rate
        }
    }
