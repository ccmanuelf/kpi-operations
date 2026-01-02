"""
DPMO (Defects Per Million Opportunities) Calculation
PHASE 4: Six Sigma quality metrics

DPMO = (Total Defects / (Total Units × Opportunities per Unit)) * 1,000,000
Sigma Level = derived from DPMO using lookup table
"""
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import date
from typing import Optional
import math

from backend.schemas.quality import QualityInspection


# DPMO to Sigma Level lookup table
DPMO_TO_SIGMA = [
    (3.4, 6.0),
    (233, 5.0),
    (6210, 4.0),
    (66807, 3.0),
    (308537, 2.0),
    (690000, 1.0),
]


def calculate_dpmo(
    db: Session,
    product_id: int,
    shift_id: int,
    start_date: date,
    end_date: date,
    opportunities_per_unit: int = 10
) -> tuple[Decimal, Decimal, int, int]:
    """
    Calculate DPMO and Sigma Level

    opportunities_per_unit: Number of potential defect points per unit
    (e.g., for apparel: seams, buttons, zippers, fabric quality, etc.)

    Returns: (dpmo, sigma_level, total_units, total_defects)
    """

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
    total_opportunities = total_units * opportunities_per_unit

    # Calculate DPMO
    if total_opportunities > 0:
        dpmo = (Decimal(str(total_defects)) / Decimal(str(total_opportunities))) * Decimal("1000000")
    else:
        dpmo = Decimal("0")

    # Calculate Sigma Level
    sigma_level = calculate_sigma_level(dpmo)

    return (dpmo, sigma_level, total_units, total_defects)


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
