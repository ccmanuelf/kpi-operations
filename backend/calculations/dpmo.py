"""
DPMO (Defects Per Million Opportunities) Calculation
PHASE 4: Six Sigma quality metrics

DPMO = (Total Defects / (Total Units × Opportunities per Unit)) * 1,000,000
Sigma Level = derived from DPMO using lookup table

Phase 6.7 Enhancement: Uses PART_OPPORTUNITIES table for part-specific opportunities
Phase 7.2 Enhancement: Uses client config for default opportunities per unit
"""
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date
from typing import Optional
import math

from backend.schemas.quality_entry import QualityEntry
from backend.schemas.part_opportunities import PartOpportunities
from backend.crud.client_config import get_client_config_or_defaults


# DPMO to Sigma Level lookup table
DPMO_TO_SIGMA = [
    (3.4, 6.0),
    (233, 5.0),
    (6210, 4.0),
    (66807, 3.0),
    (308537, 2.0),
    (690000, 1.0),
]

# Fallback default opportunities per unit when no part-specific data exists
DEFAULT_OPPORTUNITIES_PER_UNIT = 10


def get_client_opportunities_default(db: Session, client_id: Optional[str] = None) -> int:
    """
    Get the default opportunities per unit for a client from their configuration.
    Falls back to global default if no client config exists.

    Phase 7.2: Client-level configuration overrides

    Args:
        db: Database session
        client_id: Client ID (optional)

    Returns:
        Default opportunities per unit
    """
    if not client_id:
        return DEFAULT_OPPORTUNITIES_PER_UNIT

    try:
        config = get_client_config_or_defaults(db, client_id)
        return config.get("dpmo_opportunities_default", DEFAULT_OPPORTUNITIES_PER_UNIT)
    except Exception:
        return DEFAULT_OPPORTUNITIES_PER_UNIT


def get_opportunities_for_part(
    db: Session,
    part_number: str,
    client_id: Optional[str] = None
) -> int:
    """
    Look up opportunities per unit from PART_OPPORTUNITIES table.

    Phase 6.7: Uses PART_OPPORTUNITIES table for part-specific opportunities.
    Phase 7.2: Falls back to client-specific default, then global default.

    Args:
        db: Database session
        part_number: Part number to look up
        client_id: Optional client ID for multi-tenant filtering

    Returns:
        Opportunities per unit for the part (or client/global default if not found)
    """
    # Get client-specific default (or global default)
    client_default = get_client_opportunities_default(db, client_id)

    if not part_number:
        return client_default

    query = db.query(PartOpportunities).filter(
        PartOpportunities.part_number == part_number
    )

    if client_id:
        query = query.filter(PartOpportunities.client_id_fk == client_id)

    part_opp = query.first()

    if part_opp and part_opp.opportunities_per_unit:
        return part_opp.opportunities_per_unit

    return client_default


def get_opportunities_for_parts(
    db: Session,
    part_numbers: list,
    client_id: Optional[str] = None
) -> dict:
    """
    Batch lookup of opportunities per unit for multiple parts.

    Phase 6.7: Efficient batch query for multiple parts.
    Phase 7.2: Uses client-specific default for parts not found.

    Args:
        db: Database session
        part_numbers: List of part numbers to look up
        client_id: Optional client ID for multi-tenant filtering

    Returns:
        Dictionary mapping part_number -> opportunities_per_unit
    """
    if not part_numbers:
        return {}

    # Get client-specific default (or global default)
    client_default = get_client_opportunities_default(db, client_id)

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

    # Fill in client defaults for parts not found
    for part in part_numbers:
        if part not in opportunities_map:
            opportunities_map[part] = client_default

    return opportunities_map


def calculate_dpmo(
    db: Session,
    work_order_id: str,
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
        work_order_id: Work order ID to filter inspections
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
    from sqlalchemy import cast, Date

    # Determine opportunities per unit
    if opportunities_per_unit is not None:
        # Manual override provided
        effective_opportunities = opportunities_per_unit
    elif part_number:
        # Look up from PART_OPPORTUNITIES table (includes client default fallback)
        effective_opportunities = get_opportunities_for_part(db, part_number, client_id)
    else:
        # Use client-specific default (or global default)
        effective_opportunities = get_client_opportunities_default(db, client_id)

    # Get all inspections for period (using correct QualityEntry fields)
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

    if not inspections:
        return (Decimal("0"), Decimal("0"), 0, 0)

    total_units = sum(i.units_inspected for i in inspections)
    # Use total_defects_count for DPMO (counts each defect, not just defective units)
    total_defects = sum(i.total_defects_count or i.units_defective or 0 for i in inspections)

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
            # Use client-specific default for parts not in opportunities_map
            client_default = get_client_opportunities_default(db, client_id)
            opportunities = opportunities_map.get(part_number, client_default)
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
    work_order_id: str,
    start_date: date,
    end_date: date,
    upper_spec_limit: Decimal,
    lower_spec_limit: Decimal,
    target_value: Decimal,
    client_id: Optional[str] = None
) -> dict:
    """
    Calculate Process Capability Indices (Cp, Cpk)

    Cp = (USL - LSL) / (6 × σ)
    Cpk = min((USL - μ) / (3 × σ), (μ - LSL) / (3 × σ))

    Note: This requires actual measurement data (not just pass/fail)
    For MVP, we use defect rates as proxy
    """
    from sqlalchemy import cast, Date

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

    if not inspections:
        return {
            "cp": Decimal("0"),
            "cpk": Decimal("0"),
            "interpretation": "Insufficient data"
        }

    # Calculate defect rate as proxy for variation
    total_inspected = sum(i.units_inspected for i in inspections)
    # Use total_defects_count for process capability (counts each defect)
    total_defects = sum(i.total_defects_count or i.units_defective or 0 for i in inspections)

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
    work_order_id: str,
    lookback_days: int = 30,
    client_id: Optional[str] = None
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
        db, work_order_id=work_order_id, start_date=start_date, end_date=mid_date, client_id=client_id
    )

    # Second half
    dpmo_second, sigma_second, _, _ = calculate_dpmo(
        db, work_order_id=work_order_id, start_date=mid_date, end_date=end_date, client_id=client_id
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
