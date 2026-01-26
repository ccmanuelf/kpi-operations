"""
DPMO (Defects Per Million Opportunities) Calculation
PHASE 4: Six Sigma quality metrics

DPMO = (Total Defects / (Total Units × Opportunities per Unit)) * 1,000,000
Sigma Level = derived from DPMO using lookup table

Phase 6.7 Enhancement: Uses PART_OPPORTUNITIES table for part-specific opportunities
"""
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date
from typing import Optional
import math

from backend.schemas.quality import QualityInspection
from backend.schemas.part_opportunities import PartOpportunities


# DPMO to Sigma Level lookup table
DPMO_TO_SIGMA = [
    (3.4, 6.0),
    (233, 5.0),
    (6210, 4.0),
    (66807, 3.0),
    (308537, 2.0),
    (690000, 1.0),
]

# Default opportunities per unit when no part-specific data exists
DEFAULT_OPPORTUNITIES_PER_UNIT = 10


def get_opportunities_for_part(
    db: Session,
    part_number: str,
    client_id: Optional[str] = None
) -> int:
    """
    Look up opportunities per unit from PART_OPPORTUNITIES table.

    Phase 6.7: Uses PART_OPPORTUNITIES table for part-specific opportunities.
    Falls back to DEFAULT_OPPORTUNITIES_PER_UNIT if part not configured.

    Args:
        db: Database session
        part_number: Part number to look up
        client_id: Optional client ID for multi-tenant filtering

    Returns:
        Opportunities per unit for the part (or default if not found)
    """
    if not part_number:
        return DEFAULT_OPPORTUNITIES_PER_UNIT

    query = db.query(PartOpportunities).filter(
        PartOpportunities.part_number == part_number
    )

    if client_id:
        query = query.filter(PartOpportunities.client_id_fk == client_id)

    part_opp = query.first()

    if part_opp and part_opp.opportunities_per_unit:
        return part_opp.opportunities_per_unit

    return DEFAULT_OPPORTUNITIES_PER_UNIT


def get_opportunities_for_parts(
    db: Session,
    part_numbers: list,
    client_id: Optional[str] = None
) -> dict:
    """
    Batch lookup of opportunities per unit for multiple parts.

    Phase 6.7: Efficient batch query for multiple parts.

    Args:
        db: Database session
        part_numbers: List of part numbers to look up
        client_id: Optional client ID for multi-tenant filtering

    Returns:
        Dictionary mapping part_number -> opportunities_per_unit
    """
    if not part_numbers:
        return {}

    query = db.query(PartOpportunities).filter(
        PartOpportunities.part_number.in_(part_numbers)
    )

    if client_id:
        query = query.filter(PartOpportunities.client_id_fk == client_id)

    results = query.all()

    # Build lookup dictionary
    opportunities_map = {
        po.part_number: po.opportunities_per_unit
        for po in results
        if po.opportunities_per_unit
    }

    # Fill in defaults for parts not found
    for part in part_numbers:
        if part not in opportunities_map:
            opportunities_map[part] = DEFAULT_OPPORTUNITIES_PER_UNIT

    return opportunities_map


def calculate_dpmo(
    db: Session,
    product_id: int,
    shift_id: int,
    start_date: date,
    end_date: date,
    opportunities_per_unit: int = None,
    part_number: Optional[str] = None,
    client_id: Optional[str] = None
) -> tuple[Decimal, Decimal, int, int]:
    """
    Calculate DPMO and Sigma Level

    Phase 6.7 Enhancement: Can look up opportunities from PART_OPPORTUNITIES table.

    Args:
        db: Database session
        product_id: Product ID to filter inspections
        shift_id: Shift ID to filter inspections
        start_date: Start of date range
        end_date: End of date range
        opportunities_per_unit: Manual override for opportunities (optional)
        part_number: Part number to look up opportunities from PART_OPPORTUNITIES table
        client_id: Client ID for multi-tenant filtering

    If part_number is provided and opportunities_per_unit is None,
    looks up opportunities from PART_OPPORTUNITIES table.
    Falls back to DEFAULT_OPPORTUNITIES_PER_UNIT (10) if not found.

    Returns: (dpmo, sigma_level, total_units, total_defects)
    """
    # Determine opportunities per unit
    if opportunities_per_unit is not None:
        # Manual override provided
        effective_opportunities = opportunities_per_unit
    elif part_number:
        # Look up from PART_OPPORTUNITIES table
        effective_opportunities = get_opportunities_for_part(db, part_number, client_id)
    else:
        # Use default
        effective_opportunities = DEFAULT_OPPORTUNITIES_PER_UNIT

    # Get all inspections for period
    inspections = db.query(QualityInspection).filter(
        and_(
            QualityInspection.product_id == product_id,
            QualityInspection.shift_id == shift_id,
            QualityInspection.inspection_date >= start_date,
            QualityInspection.inspection_date <= end_date
        )
    ).all()

    if not inspections:
        return (Decimal("0"), Decimal("0"), 0, 0)

    total_units = sum(i.units_inspected for i in inspections)
    total_defects = sum(i.defects_found for i in inspections)

    # Calculate total opportunities
    total_opportunities = total_units * effective_opportunities

    # Calculate DPMO
    if total_opportunities > 0:
        dpmo = (Decimal(str(total_defects)) / Decimal(str(total_opportunities))) * Decimal("1000000")
    else:
        dpmo = Decimal("0")

    # Calculate Sigma Level
    sigma_level = calculate_sigma_level(dpmo)

    return (dpmo, sigma_level, total_units, total_defects)


def calculate_dpmo_with_part_lookup(
    db: Session,
    start_date: date,
    end_date: date,
    client_id: Optional[str] = None
) -> dict:
    """
    Calculate DPMO using part-specific opportunities from PART_OPPORTUNITIES table.

    Phase 6.7: Enhanced DPMO calculation that:
    1. Groups quality entries by part_number (from work order or job)
    2. Looks up opportunities_per_unit for each part
    3. Calculates weighted DPMO across all parts

    Args:
        db: Database session
        start_date: Start of date range
        end_date: End of date range
        client_id: Client ID for multi-tenant filtering

    Returns:
        Dictionary with DPMO breakdown by part and overall metrics
    """
    from backend.schemas.quality_entry import QualityEntry
    from backend.schemas.job import Job
    from datetime import datetime

    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())

    # Get quality entries with job/part info
    query = db.query(QualityEntry).filter(
        and_(
            QualityEntry.shift_date >= start_datetime,
            QualityEntry.shift_date <= end_datetime
        )
    )

    if client_id:
        query = query.filter(QualityEntry.client_id == client_id)

    quality_entries = query.all()

    if not quality_entries:
        return {
            "overall_dpmo": Decimal("0"),
            "overall_sigma_level": Decimal("0"),
            "total_units": 0,
            "total_defects": 0,
            "total_opportunities": 0,
            "by_part": [],
            "using_part_specific_opportunities": False
        }

    # Collect unique job_ids to get part numbers
    job_ids = [qe.job_id for qe in quality_entries if qe.job_id]
    part_numbers = []

    if job_ids:
        jobs = db.query(Job).filter(Job.job_id.in_(job_ids)).all()
        part_numbers = [j.part_number for j in jobs if j.part_number]

    # Batch lookup opportunities
    opportunities_map = get_opportunities_for_parts(db, part_numbers, client_id)

    # Calculate per-part DPMO
    part_metrics = {}
    for qe in quality_entries:
        # Get part_number from job if available
        part_number = None
        if qe.job_id and job_ids:
            for j in jobs:
                if j.job_id == qe.job_id:
                    part_number = j.part_number
                    break

        key = part_number or "UNKNOWN"
        if key not in part_metrics:
            opportunities = opportunities_map.get(part_number, DEFAULT_OPPORTUNITIES_PER_UNIT)
            part_metrics[key] = {
                "part_number": key,
                "opportunities_per_unit": opportunities,
                "units_inspected": 0,
                "defects_found": 0
            }

        part_metrics[key]["units_inspected"] += qe.units_inspected or 0
        part_metrics[key]["defects_found"] += qe.total_defects_count or qe.units_defective or 0

    # Calculate DPMO per part and overall
    total_opportunities = 0
    total_defects = 0
    total_units = 0
    by_part = []

    for key, metrics in part_metrics.items():
        units = metrics["units_inspected"]
        defects = metrics["defects_found"]
        opps = metrics["opportunities_per_unit"]
        part_opportunities = units * opps

        total_units += units
        total_defects += defects
        total_opportunities += part_opportunities

        if part_opportunities > 0:
            part_dpmo = (Decimal(str(defects)) / Decimal(str(part_opportunities))) * Decimal("1000000")
        else:
            part_dpmo = Decimal("0")

        by_part.append({
            "part_number": key,
            "units_inspected": units,
            "defects_found": defects,
            "opportunities_per_unit": opps,
            "total_opportunities": part_opportunities,
            "dpmo": float(part_dpmo),
            "sigma_level": float(calculate_sigma_level(part_dpmo))
        })

    # Overall DPMO
    if total_opportunities > 0:
        overall_dpmo = (Decimal(str(total_defects)) / Decimal(str(total_opportunities))) * Decimal("1000000")
    else:
        overall_dpmo = Decimal("0")

    overall_sigma = calculate_sigma_level(overall_dpmo)

    return {
        "overall_dpmo": float(overall_dpmo),
        "overall_sigma_level": float(overall_sigma),
        "total_units": total_units,
        "total_defects": total_defects,
        "total_opportunities": total_opportunities,
        "by_part": by_part,
        "using_part_specific_opportunities": len(part_numbers) > 0
    }


def calculate_sigma_level(dpmo: Decimal) -> Decimal:
    """
    Convert DPMO to Sigma Level using lookup table
    """

    dpmo_float = float(dpmo)

    # Check lookup table
    for threshold, sigma in DPMO_TO_SIGMA:
        if dpmo_float <= threshold:
            return Decimal(str(sigma))

    # If worse than 1 sigma, return 0
    return Decimal("0")


def calculate_process_capability(
    db: Session,
    product_id: int,
    start_date: date,
    end_date: date,
    upper_spec_limit: Decimal,
    lower_spec_limit: Decimal,
    target_value: Decimal
) -> dict:
    """
    Calculate Process Capability Indices (Cp, Cpk)

    Cp = (USL - LSL) / (6 × σ)
    Cpk = min((USL - μ) / (3 × σ), (μ - LSL) / (3 × σ))

    Note: This requires actual measurement data (not just pass/fail)
    For MVP, we use defect rates as proxy
    """

    inspections = db.query(QualityInspection).filter(
        and_(
            QualityInspection.product_id == product_id,
            QualityInspection.inspection_date >= start_date,
            QualityInspection.inspection_date <= end_date
        )
    ).all()

    if not inspections:
        return {
            "cp": Decimal("0"),
            "cpk": Decimal("0"),
            "interpretation": "Insufficient data"
        }

    # Calculate defect rate as proxy for variation
    total_inspected = sum(i.units_inspected for i in inspections)
    total_defects = sum(i.defects_found for i in inspections)

    if total_inspected > 0:
        defect_rate = Decimal(str(total_defects)) / Decimal(str(total_inspected))

        # Simplified Cp calculation (using defect rate as proxy)
        if defect_rate > 0:
            # Approximate sigma from defect rate
            sigma_estimate = defect_rate * 3

            spec_range = upper_spec_limit - lower_spec_limit
            cp = spec_range / (6 * sigma_estimate) if sigma_estimate > 0 else Decimal("0")

            # Cpk (simplified)
            cpk = cp * Decimal("0.9")  # Assume 10% shift from center
        else:
            cp = Decimal("2.0")  # Perfect process
            cpk = Decimal("2.0")
    else:
        cp = Decimal("0")
        cpk = Decimal("0")

    # Interpretation
    if cpk >= Decimal("2.0"):
        interpretation = "Excellent (Six Sigma capable)"
    elif cpk >= Decimal("1.67"):
        interpretation = "Very Good (Five Sigma capable)"
    elif cpk >= Decimal("1.33"):
        interpretation = "Good (Four Sigma capable)"
    elif cpk >= Decimal("1.0"):
        interpretation = "Adequate (Three Sigma capable)"
    else:
        interpretation = "Poor (Process improvement needed)"

    return {
        "cp": cp,
        "cpk": cpk,
        "interpretation": interpretation,
        "total_inspected": total_inspected,
        "total_defects": total_defects
    }


def identify_quality_trends(
    db: Session,
    product_id: int,
    lookback_days: int = 30
) -> dict:
    """
    Analyze quality trends over time
    Returns trend direction and recommendations
    """

    from datetime import timedelta

    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)
    mid_date = start_date + timedelta(days=lookback_days // 2)

    # First half
    dpmo_first, sigma_first, _, _ = calculate_dpmo(
        db, product_id, None, start_date, mid_date
    )

    # Second half
    dpmo_second, sigma_second, _, _ = calculate_dpmo(
        db, product_id, None, mid_date, end_date
    )

    # Calculate trend
    if dpmo_first == 0:
        trend = "insufficient_data"
        recommendation = "Collect more quality data"
    elif dpmo_second < dpmo_first * Decimal("0.9"):
        trend = "improving"
        improvement_pct = ((dpmo_first - dpmo_second) / dpmo_first) * 100
        recommendation = f"Quality improving by {improvement_pct:.1f}%. Continue current practices."
    elif dpmo_second > dpmo_first * Decimal("1.1"):
        trend = "declining"
        decline_pct = ((dpmo_second - dpmo_first) / dpmo_first) * 100
        recommendation = f"Quality declining by {decline_pct:.1f}%. Investigate root causes immediately."
    else:
        trend = "stable"
        recommendation = "Quality stable. Monitor for changes."

    return {
        "trend": trend,
        "dpmo_first_half": dpmo_first,
        "dpmo_second_half": dpmo_second,
        "sigma_first_half": sigma_first,
        "sigma_second_half": sigma_second,
        "recommendation": recommendation
    }
