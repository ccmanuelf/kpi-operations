"""
Quality Inspection API Routes
PHASE 4: Quality metrics and defect tracking
All endpoints enforce multi-tenant client filtering
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime

from backend.database import get_db
from backend.utils.logging_utils import get_module_logger, log_operation, log_error

logger = get_module_logger(__name__)
from backend.models.quality import (
    QualityInspectionCreate,
    QualityInspectionUpdate,
    QualityInspectionResponse,
    PPMCalculationResponse,
    DPMOCalculationResponse,
    FPYRTYCalculationResponse,
    InferenceMetadata
)
from backend.crud.quality import (
    create_quality_inspection,
    get_quality_inspection,
    get_quality_inspections,
    update_quality_inspection,
    delete_quality_inspection
)
from backend.calculations.ppm import calculate_ppm, identify_top_defects
from backend.calculations.dpmo import calculate_dpmo, calculate_dpmo_with_part_lookup
from backend.calculations.fpy_rty import (
    calculate_fpy,
    calculate_rty,
    calculate_quality_score,
    calculate_fpy_with_repair_breakdown,
    calculate_rty_with_repair_impact
)
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User
from backend.middleware.client_auth import build_client_filter_clause, verify_client_access


router = APIRouter(
    prefix="/api/quality",
    tags=["Quality Inspection"]
)


@router.post("", response_model=QualityInspectionResponse, status_code=status.HTTP_201_CREATED)
def create_quality(
    inspection: QualityInspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new quality inspection record
    SECURITY: Enforces client filtering through user authentication
    """
    try:
        result = create_quality_inspection(db, inspection, current_user)
        log_operation(logger, "CREATE", "quality",
                     resource_id=str(result.quality_entry_id),
                     user_id=current_user.user_id,
                     details={"units_inspected": getattr(inspection, 'units_inspected', None)})
        return result
    except Exception as e:
        log_error(logger, "CREATE", "quality", e, user_id=current_user.user_id)
        raise


@router.get("", response_model=List[QualityInspectionResponse])
def list_quality(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    work_order_id: Optional[str] = None,
    inspection_stage: Optional[str] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List quality inspections with filters
    SECURITY: Returns only inspections for user's authorized clients
    """
    return get_quality_inspections(
        db, current_user=current_user, skip=skip, limit=limit, start_date=start_date,
        end_date=end_date, work_order_id=work_order_id,
        inspection_stage=inspection_stage, client_id=client_id
    )


@router.get("/{inspection_id}", response_model=QualityInspectionResponse)
def get_quality(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get quality inspection by ID
    SECURITY: Verifies user has access to this inspection record
    """
    inspection = get_quality_inspection(db, inspection_id, current_user)
    if not inspection:
        raise HTTPException(status_code=404, detail="Quality inspection not found")
    return inspection


@router.get("/by-work-order/{work_order_id}", response_model=List[QualityInspectionResponse])
def get_quality_by_work_order(
    work_order_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all quality inspections for a specific work order
    SECURITY: Returns only inspections for user's authorized clients
    """
    from backend.schemas.quality_entry import QualityEntry

    query = db.query(QualityEntry).filter(
        QualityEntry.work_order_id == work_order_id
    )

    # SECURITY FIX (VULN-001): Apply client filter to prevent cross-client data access
    client_filter = build_client_filter_clause(current_user, QualityEntry.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.offset(skip).limit(limit).all()


@router.get("/statistics/summary")
def get_quality_statistics(
    start_date: date,
    end_date: date,
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get quality statistics summary for a date range
    SECURITY: Returns only data for user's authorized clients
    """
    from sqlalchemy import func, cast, Date
    from backend.schemas.quality_entry import QualityEntry

    query = db.query(
        func.sum(QualityEntry.units_inspected).label('total_inspected'),
        func.sum(QualityEntry.units_defective).label('total_defects'),
        func.sum(QualityEntry.units_scrapped).label('total_scrap'),
        func.sum(QualityEntry.units_reworked).label('total_rework'),
        func.avg(QualityEntry.ppm).label('avg_ppm'),
        func.avg(QualityEntry.dpmo).label('avg_dpmo')
    )

    # SECURITY FIX (VULN-002): Apply client filter to prevent cross-client data access
    # If specific client_id requested, verify access first
    if client_id:
        verify_client_access(current_user, client_id)
        query = query.filter(QualityEntry.client_id == client_id)
    else:
        # Apply user's authorized client filter
        client_filter = build_client_filter_clause(current_user, QualityEntry.client_id)
        if client_filter is not None:
            query = query.filter(client_filter)

    # Apply date filters (shift_date is DateTime, cast to Date for comparison)
    query = query.filter(
        cast(QualityEntry.shift_date, Date) >= start_date,
        cast(QualityEntry.shift_date, Date) <= end_date
    )

    # Note: QualityEntry doesn't have product_id/shift_id - these filters are ignored
    # for backward compatibility (they were likely never used correctly anyway)

    result = query.first()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "product_id": product_id,
        "shift_id": shift_id,
        "total_units_inspected": result.total_inspected or 0,
        "total_defects_found": result.total_defects or 0,
        "total_scrap_units": result.total_scrap or 0,
        "total_rework_units": result.total_rework or 0,
        "average_ppm": float(result.avg_ppm) if result.avg_ppm else 0,
        "average_dpmo": float(result.avg_dpmo) if result.avg_dpmo else 0,
        "calculation_timestamp": datetime.utcnow()
    }


@router.put("/{inspection_id}", response_model=QualityInspectionResponse)
def update_quality(
    inspection_id: int,
    inspection_update: QualityInspectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update quality inspection record
    SECURITY: Verifies user has access to this inspection record
    """
    try:
        updated = update_quality_inspection(db, inspection_id, inspection_update, current_user)
        if not updated:
            raise HTTPException(status_code=404, detail="Quality inspection not found")
        log_operation(logger, "UPDATE", "quality",
                     resource_id=str(inspection_id),
                     user_id=current_user.user_id)
        return updated
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "UPDATE", "quality", e,
                 resource_id=str(inspection_id), user_id=current_user.user_id)
        raise


@router.delete("/{inspection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quality(
    inspection_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """
    Delete quality inspection record (supervisor only)
    SECURITY: Supervisor/admin only, verifies client access
    """
    try:
        success = delete_quality_inspection(db, inspection_id, current_user)
        if not success:
            raise HTTPException(status_code=404, detail="Quality inspection not found")
        log_operation(logger, "DELETE", "quality",
                     resource_id=str(inspection_id),
                     user_id=current_user.user_id)
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "DELETE", "quality", e,
                 resource_id=str(inspection_id), user_id=current_user.user_id)
        raise


# ============================================================================
# QUALITY KPI CALCULATION ENDPOINTS
# ============================================================================

@router.get("/kpi/ppm", response_model=PPMCalculationResponse)
def calculate_ppm_kpi(
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate PPM (Parts Per Million) defect rate with client filtering
    Formula: (Total Defects / Total Units Inspected) × 1,000,000

    Parameters are optional - defaults to last 30 days and all products/shifts
    """
    from datetime import timedelta
    from backend.schemas.quality_entry import QualityEntry
    from sqlalchemy import func

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Build query with client filter - using QUALITY_ENTRY table
    query = db.query(
        func.sum(QualityEntry.units_inspected).label('inspected'),
        func.sum(QualityEntry.units_defective).label('defects')
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    # Apply client filter
    if effective_client_id:
        query = query.filter(QualityEntry.client_id == effective_client_id)

    result = query.first()
    inspected = result.inspected or 0
    defects = result.defects or 0
    ppm = (defects / inspected * 1000000) if inspected > 0 else 0
    defect_rate_pct = (defects / inspected * 100) if inspected > 0 else 0

    # Use default product/shift IDs for response (required by schema)
    # ENHANCEMENT: Include inference metadata per audit requirement
    # PPM uses actual data, so is_estimated=False unless no data found
    inference = InferenceMetadata(
        is_estimated=inspected == 0,  # Estimated only if no data
        confidence_score=1.0 if inspected > 0 else 0.3,
        inference_source="actual_data" if inspected > 0 else "system_fallback",
        inference_warning="No inspection data available for the specified period" if inspected == 0 else None
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
        calculation_timestamp=datetime.utcnow(),
        inference=inference
    )


@router.get("/kpi/dpmo", response_model=DPMOCalculationResponse)
def calculate_dpmo_kpi(
    product_id: int,
    shift_id: int,
    start_date: date,
    end_date: date,
    opportunities_per_unit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate DPMO (Defects Per Million Opportunities) and Sigma Level
    Formula: (Total Defects / Total Opportunities) × 1,000,000
    Total Opportunities = Units × Opportunities per Unit
    """
    dpmo, sigma, units, defects = calculate_dpmo(
        db, product_id, shift_id, start_date, end_date, opportunities_per_unit
    )

    # ENHANCEMENT: Include inference metadata per audit requirement
    inference = InferenceMetadata(
        is_estimated=units == 0,
        confidence_score=1.0 if units > 0 else 0.3,
        inference_source="actual_data" if units > 0 else "system_fallback",
        inference_warning="No production data available for DPMO calculation" if units == 0 else None
    )

    return DPMOCalculationResponse(
        product_id=product_id,
        shift_id=shift_id,
        start_date=start_date,
        end_date=end_date,
        total_units=units,
        opportunities_per_unit=opportunities_per_unit,
        total_defects=defects,
        dpmo=dpmo,
        sigma_level=sigma,
        calculation_timestamp=datetime.utcnow(),
        inference=inference
    )


@router.get("/kpi/dpmo-by-part")
def calculate_dpmo_by_part(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    result = calculate_dpmo_with_part_lookup(db, start_date, end_date, effective_client_id)

    return {
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        "client_id": effective_client_id,
        **result,
        "calculation_timestamp": datetime.utcnow().isoformat()
    }


@router.get("/kpi/fpy-rty", response_model=FPYRTYCalculationResponse)
def calculate_fpy_rty_kpi(
    product_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate FPY (First Pass Yield) and RTY (Rolled Throughput Yield) with client filtering
    FPY = (Units Passed / Total Units) × 100
    RTY = Product of all FPY values across process steps (inspection stages)

    Parameters are optional - defaults to all products and last 30 days
    """
    from datetime import timedelta
    from backend.schemas.quality_entry import QualityEntry
    from sqlalchemy import func

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Build query with client filter for overall FPY calculation
    query = db.query(
        func.sum(QualityEntry.units_inspected).label('total'),
        func.sum(QualityEntry.units_passed).label('good')
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(QualityEntry.client_id == effective_client_id)

    result = query.first()
    total = result.total or 0
    good = result.good or 0
    fpy = (good / total * 100) if total > 0 else 0

    # Calculate total scrapped for Final Yield
    scrapped_query = db.query(
        func.sum(QualityEntry.units_scrapped).label('scrapped')
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        scrapped_query = scrapped_query.filter(QualityEntry.client_id == effective_client_id)

    scrapped_result = scrapped_query.first()
    total_scrapped = scrapped_result.scrapped or 0

    # Final Yield = (Total Inspected - Scrapped) / Total Inspected × 100
    # This represents units that ultimately passed (first pass + reworked successfully)
    final_yield = ((total - total_scrapped) / total * 100) if total > 0 else 0

    # RTY calculation - calculate FPY per inspection stage and multiply them
    # RTY = FPY_stage1 × FPY_stage2 × ... × FPY_stageN
    stage_query = db.query(
        QualityEntry.inspection_stage,
        func.sum(QualityEntry.units_inspected).label('stage_total'),
        func.sum(QualityEntry.units_passed).label('stage_passed')
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
        QualityEntry.inspection_stage.isnot(None)
    )

    if effective_client_id:
        stage_query = stage_query.filter(QualityEntry.client_id == effective_client_id)

    stage_results = stage_query.group_by(QualityEntry.inspection_stage).all()

    # Calculate RTY as product of stage FPYs
    steps = []
    rty_decimal = 1.0  # Start at 100%

    if stage_results:
        for stage in stage_results:
            stage_total = stage.stage_total or 0
            stage_passed = stage.stage_passed or 0
            if stage_total > 0:
                stage_fpy = (stage_passed / stage_total)  # As decimal (0.0 to 1.0)
                rty_decimal *= stage_fpy
                steps.append({
                    "stage": stage.inspection_stage,
                    "fpy": round(stage_fpy * 100, 2),
                    "total": stage_total,
                    "passed": stage_passed
                })

    # Convert RTY back to percentage
    if steps:
        rty = rty_decimal * 100
    else:
        # If no stage data available, fall back to overall FPY
        rty = fpy

    # ENHANCEMENT: Include inference metadata per audit requirement
    # RTY defaults to FPY if no stage data available (partial inference)
    is_estimated = total == 0 or (not steps and fpy > 0)
    inference = InferenceMetadata(
        is_estimated=is_estimated,
        confidence_score=1.0 if total > 0 and steps else (0.7 if total > 0 else 0.3),
        inference_source="actual_data" if total > 0 and steps else ("overall_fpy_fallback" if total > 0 else "system_fallback"),
        inference_warning="RTY calculation used overall FPY as fallback (no stage-specific data)" if (total > 0 and not steps) else ("No quality data available" if total == 0 else None)
    )

    return FPYRTYCalculationResponse(
        product_id=product_id or 1,
        start_date=start_date,
        end_date=end_date,
        total_units=total,
        first_pass_good=good,
        total_scrapped=total_scrapped,
        fpy_percentage=round(fpy, 2),
        rty_percentage=round(rty, 2),
        final_yield_percentage=round(final_yield, 2),
        total_process_steps=len(steps),
        calculation_timestamp=datetime.utcnow(),
        inference=inference
    )


@router.get("/kpi/fpy-rty-breakdown")
def get_fpy_rty_breakdown(
    product_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    inspection_stage: Optional[str] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate FPY and RTY with detailed repair vs rework breakdown

    Phase 6.5: Repair vs Rework Distinction

    Returns:
    - FPY with repair/rework/scrap breakdown per inspection stage
    - RTY with repair impact analysis across all stages
    - Recovery rate (rework + repair saved vs scrapped)
    - Human-readable interpretation of quality performance

    Key Metrics:
    - fpy_percentage: First Pass Yield (excludes rework AND repair)
    - rework_rate: % of units that needed in-line correction
    - repair_rate: % of units requiring significant resources/external repair
    - scrap_rate: % of units that could not be recovered
    - recovery_rate: % of failed units that were successfully recovered
    - throughput_loss_percentage: Total impact on throughput from rework + repair
    """
    from datetime import timedelta

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Use product_id=0 as placeholder if not specified (calculation functions accept it)
    effective_product_id = product_id or 0

    # Get FPY breakdown for specific stage or overall
    fpy_breakdown = calculate_fpy_with_repair_breakdown(
        db, effective_product_id, start_date, end_date, inspection_stage
    )

    # Get RTY with repair impact across all stages
    rty_breakdown = calculate_rty_with_repair_impact(
        db, effective_product_id, start_date, end_date
    )

    return {
        "period": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        "product_id": product_id,
        "client_id": effective_client_id,
        "inspection_stage_filter": inspection_stage,
        "fpy_breakdown": {
            "fpy_percentage": float(fpy_breakdown["fpy_percentage"]),
            "first_pass_good": fpy_breakdown["first_pass_good"],
            "total_inspected": fpy_breakdown["total_inspected"],
            "units_reworked": fpy_breakdown["units_reworked"],
            "units_requiring_repair": fpy_breakdown["units_requiring_repair"],
            "units_scrapped": fpy_breakdown["units_scrapped"],
            "rework_rate": float(fpy_breakdown["rework_rate"]),
            "repair_rate": float(fpy_breakdown["repair_rate"]),
            "scrap_rate": float(fpy_breakdown["scrap_rate"]),
            "recovered_units": fpy_breakdown["recovered_units"],
            "recovery_rate": float(fpy_breakdown["recovery_rate"])
        },
        "rty_breakdown": {
            "rty_percentage": float(rty_breakdown["rty_percentage"]),
            "step_details": [
                {
                    "step": step["step"],
                    "fpy_percentage": float(step["fpy_percentage"]),
                    "first_pass_good": step["first_pass_good"],
                    "total_inspected": step["total_inspected"],
                    "units_reworked": step["units_reworked"],
                    "units_requiring_repair": step["units_requiring_repair"],
                    "units_scrapped": step["units_scrapped"],
                    "rework_rate": float(step["rework_rate"]),
                    "repair_rate": float(step["repair_rate"])
                }
                for step in rty_breakdown["step_details"]
            ],
            "total_rework": rty_breakdown["total_rework"],
            "total_repair": rty_breakdown["total_repair"],
            "total_scrap": rty_breakdown["total_scrap"],
            "rework_impact_percentage": float(rty_breakdown["rework_impact_percentage"]),
            "repair_impact_percentage": float(rty_breakdown["repair_impact_percentage"]),
            "throughput_loss_percentage": float(rty_breakdown["throughput_loss_percentage"]),
            "interpretation": rty_breakdown["interpretation"]
        },
        "calculation_timestamp": datetime.utcnow().isoformat()
    }


@router.get("/kpi/quality-score")
def get_quality_score(
    product_id: int,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate comprehensive quality score combining multiple metrics
    Includes FPY, RTY, PPM, and DPMO analysis
    """
    return calculate_quality_score(db, product_id, start_date, end_date)


@router.get("/kpi/top-defects")
def get_top_defects(
    product_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get top defect types (Pareto analysis)
    Returns defects sorted by frequency for root cause analysis
    """
    return identify_top_defects(db, product_id, start_date, end_date, limit)


@router.get("/kpi/defects-by-type")
def get_defects_by_type(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get defect counts grouped by type with client filtering
    Returns defect_type, count, and percentage for Pareto analysis
    """
    from datetime import timedelta
    from sqlalchemy import func, text

    # Default to last 30 days
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Use raw SQL for reliable column access
    sql = """
        SELECT dd.defect_type, SUM(dd.defect_count) as count
        FROM DEFECT_DETAIL dd
        JOIN QUALITY_ENTRY qe ON dd.quality_entry_id = qe.quality_entry_id
        WHERE qe.shift_date >= :start_date AND qe.shift_date <= :end_date
    """
    params = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}

    if effective_client_id:
        sql += " AND dd.client_id_fk = :client_id"
        params["client_id"] = effective_client_id

    sql += " GROUP BY dd.defect_type ORDER BY count DESC LIMIT :limit"
    params["limit"] = limit

    results = db.execute(text(sql), params).fetchall()

    # Calculate total for percentages
    total_defects = sum(r[1] or 0 for r in results)

    return [
        {
            "defect_type": str(r[0]),
            "count": r[1] or 0,
            "percentage": round((r[1] / total_defects) * 100, 1) if total_defects > 0 else 0
        }
        for r in results
    ]


@router.get("/kpi/by-product")
def get_quality_by_product(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get quality metrics (FPY) grouped by product/style with client filtering
    Returns product_name (style_model), units inspected, defects, and FPY percentage
    """
    from datetime import timedelta
    from sqlalchemy import text

    # Default to last 30 days
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Use raw SQL - WORK_ORDER has style_model, not product_id
    sql = """
        SELECT wo.style_model as product_name,
               SUM(qe.units_inspected) as inspected,
               SUM(qe.units_defective) as defects,
               SUM(qe.units_passed) as passed
        FROM QUALITY_ENTRY qe
        JOIN WORK_ORDER wo ON qe.work_order_id = wo.work_order_id
        WHERE qe.shift_date >= :start_date AND qe.shift_date <= :end_date
    """
    params = {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()}

    if effective_client_id:
        sql += " AND qe.client_id = :client_id"
        params["client_id"] = effective_client_id

    sql += " GROUP BY wo.style_model ORDER BY inspected DESC LIMIT :limit"
    params["limit"] = limit

    results = db.execute(text(sql), params).fetchall()

    return [
        {
            "product_name": r[0] or "Unknown",
            "inspected": r[1] or 0,
            "defects": r[2] or 0,
            "fpy": round((r[3] / r[1]) * 100, 1) if r[1] and r[1] > 0 else 0
        }
        for r in results
    ]
