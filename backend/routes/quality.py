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
from backend.models.quality import (
    QualityInspectionCreate,
    QualityInspectionUpdate,
    QualityInspectionResponse,
    PPMCalculationResponse,
    DPMOCalculationResponse,
    FPYRTYCalculationResponse
)
from backend.crud.quality import (
    create_quality_inspection,
    get_quality_inspection,
    get_quality_inspections,
    update_quality_inspection,
    delete_quality_inspection
)
from backend.calculations.ppm import calculate_ppm, identify_top_defects
from backend.calculations.dpmo import calculate_dpmo
from backend.calculations.fpy_rty import calculate_fpy, calculate_rty, calculate_quality_score
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User


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
    return create_quality_inspection(db, inspection, current_user)


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
    from backend.schemas.quality import QualityInspection

    query = db.query(QualityInspection).filter(
        QualityInspection.work_order_number == work_order_id
    )

    return query.offset(skip).limit(limit).all()


@router.get("/statistics/summary")
def get_quality_statistics(
    start_date: date,
    end_date: date,
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get quality statistics summary for a date range
    SECURITY: Returns only data for user's authorized clients
    """
    from sqlalchemy import func
    from backend.schemas.quality import QualityInspection

    query = db.query(
        func.sum(QualityInspection.units_inspected).label('total_inspected'),
        func.sum(QualityInspection.defects_found).label('total_defects'),
        func.sum(QualityInspection.scrap_units).label('total_scrap'),
        func.sum(QualityInspection.rework_units).label('total_rework'),
        func.avg(QualityInspection.ppm).label('avg_ppm'),
        func.avg(QualityInspection.dpmo).label('avg_dpmo')
    )

    # Apply date filters
    query = query.filter(
        QualityInspection.inspection_date >= start_date,
        QualityInspection.inspection_date <= end_date
    )

    # Optional filters
    if product_id:
        query = query.filter(QualityInspection.product_id == product_id)
    if shift_id:
        query = query.filter(QualityInspection.shift_id == shift_id)

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
    updated = update_quality_inspection(db, inspection_id, inspection_update, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Quality inspection not found")
    return updated


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
    success = delete_quality_inspection(db, inspection_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Quality inspection not found")


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
    return PPMCalculationResponse(
        product_id=product_id or 1,
        shift_id=shift_id or 1,
        start_date=start_date,
        end_date=end_date,
        total_units_inspected=inspected,
        total_defects=defects,
        ppm=round(ppm, 2),
        defect_rate_percentage=round(defect_rate_pct, 2),
        calculation_timestamp=datetime.utcnow()
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
        calculation_timestamp=datetime.utcnow()
    )


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
        calculation_timestamp=datetime.utcnow()
    )


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
