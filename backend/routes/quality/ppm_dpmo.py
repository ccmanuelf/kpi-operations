"""
Quality Inspection - PPM and DPMO Calculation Endpoints

Parts Per Million (PPM) and Defects Per Million Opportunities (DPMO)
KPI calculation endpoints with client filtering and inference metadata.
"""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.orm.user import User
from backend.schemas.quality import (
    PPMCalculationResponse,
    DPMOCalculationResponse,
    InferenceMetadata,
)
from backend.calculations.dpmo import calculate_dpmo_with_part_lookup
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

ppm_dpmo_router = APIRouter()


@ppm_dpmo_router.get("/kpi/ppm", response_model=PPMCalculationResponse)
def calculate_ppm_kpi(
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PPMCalculationResponse:
    """
    Calculate PPM (Parts Per Million) defect rate with client filtering
    Formula: (Total Defects / Total Units Inspected) × 1,000,000

    Parameters are optional - defaults to last 30 days and all products/shifts
    """
    from datetime import timedelta
    from backend.orm.quality_entry import QualityEntry
    from sqlalchemy import func

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Build query with client filter - using QUALITY_ENTRY table
    query = db.query(
        func.sum(QualityEntry.units_inspected).label("inspected"),
        func.sum(QualityEntry.units_defective).label("defects"),
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
    )

    if effective_client_id:
        query = query.filter(QualityEntry.client_id == effective_client_id)

    result = query.first()
    # query.first() on an aggregate is None when no QualityEntry rows
    # match — treat that the same as zero rows.
    inspected = (result.inspected or 0) if result is not None else 0
    defects = (result.defects or 0) if result is not None else 0
    ppm = (defects / inspected * 1000000) if inspected > 0 else 0
    defect_rate_pct = (defects / inspected * 100) if inspected > 0 else 0

    # ENHANCEMENT: Include inference metadata per audit requirement
    inference = InferenceMetadata(
        is_estimated=inspected == 0,
        confidence_score=1.0 if inspected > 0 else 0.3,
        inference_source="actual_data" if inspected > 0 else "system_fallback",
        inference_warning=("No inspection data available for the specified period" if inspected == 0 else None),
    )

    return PPMCalculationResponse(
        product_id=product_id or 1,
        shift_id=shift_id or 1,
        start_date=start_date,
        end_date=end_date,
        total_units_inspected=inspected,
        total_defects=defects,
        ppm=round(ppm, 2),
        defect_rate_percentage=round(defect_rate_pct, 2),
        calculation_timestamp=datetime.now(tz=timezone.utc),
        inference=inference,
    )


@ppm_dpmo_router.get("/kpi/dpmo", response_model=DPMOCalculationResponse)
def calculate_dpmo_kpi(
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    opportunities_per_unit: int = 10,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DPMOCalculationResponse:
    """
    Calculate DPMO (Defects Per Million Opportunities) and Sigma Level
    Formula: (Total Defects / Total Opportunities) × 1,000,000
    Total Opportunities = Units × Opportunities per Unit

    Parameters are optional - defaults to last 30 days, all products/shifts.
    Mirrors the calculate_ppm_kpi route's aggregate-query pattern (rather
    than calling backend.calculations.dpmo.calculate_dpmo, whose signature
    requires a specific work_order_id and would 422 the dashboard's
    parameterless GET).
    """
    from datetime import timedelta
    from backend.orm.quality_entry import QualityEntry
    from sqlalchemy import func

    # Default window if not specified
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Effective client filter (admin can pass through, others scoped)
    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = db.query(
        func.sum(QualityEntry.units_inspected).label("inspected"),
        func.sum(func.coalesce(QualityEntry.total_defects_count, QualityEntry.units_defective, 0)).label("defects"),
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
    )

    if effective_client_id:
        query = query.filter(QualityEntry.client_id == effective_client_id)

    result = query.first()
    units = int(result.inspected) if result is not None and result.inspected else 0
    defects = int(result.defects) if result is not None and result.defects else 0

    total_opportunities = units * opportunities_per_unit
    if total_opportunities > 0:
        dpmo_value = (defects / total_opportunities) * 1_000_000
    else:
        dpmo_value = 0.0

    # Sigma level approximation from DPMO (Six Sigma standard table).
    # Reuse the calculation helper rather than redoing the math here.
    from backend.calculations.dpmo import calculate_sigma_level
    from decimal import Decimal as _Decimal

    sigma = calculate_sigma_level(_Decimal(str(dpmo_value)))

    inference = InferenceMetadata(
        is_estimated=units == 0,
        confidence_score=1.0 if units > 0 else 0.3,
        inference_source="actual_data" if units > 0 else "system_fallback",
        inference_warning="No production data available for DPMO calculation" if units == 0 else None,
    )

    return DPMOCalculationResponse(
        product_id=product_id or 1,
        shift_id=shift_id or 1,
        start_date=start_date,
        end_date=end_date,
        total_units=units,
        opportunities_per_unit=opportunities_per_unit,
        total_defects=defects,
        dpmo=round(dpmo_value, 2),
        sigma_level=sigma,
        calculation_timestamp=datetime.now(tz=timezone.utc),
        inference=inference,
    )


@ppm_dpmo_router.get("/kpi/dpmo-by-part")
def calculate_dpmo_by_part(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Calculate DPMO using part-specific opportunities from PART_OPPORTUNITIES table.

    Phase 6.7: Enhanced DPMO calculation that:
    1. Groups quality entries by part_number (from job/work order)
    2. Looks up opportunities_per_unit for each part from PART_OPPORTUNITIES table
    3. Calculates weighted DPMO across all parts
    4. Falls back to default (10) if part not configured

    Returns:
    - Overall DPMO and Sigma level
    - Per-part DPMO breakdown
    - Whether part-specific opportunities were used
    """
    from datetime import timedelta

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    result = calculate_dpmo_with_part_lookup(db, start_date, end_date, effective_client_id)

    return {
        "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        "client_id": effective_client_id,
        **result,
        "calculation_timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
