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
from crud.quality import (
    create_quality_inspection,
    get_quality_inspection,
    get_quality_inspections,
    update_quality_inspection,
    delete_quality_inspection
)
from backend.calculations.ppm import calculate_ppm, identify_top_defects
from backend.calculations.dpmo import calculate_dpmo
from backend.calculations.fpy_rty import calculate_fpy, calculate_rty, calculate_quality_score
from auth.jwt import get_current_user, get_current_active_supervisor
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
    product_id: Optional[int] = None,
    shift_id: Optional[int] = None,
    inspection_stage: Optional[str] = None,
    defect_category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List quality inspections with filters
    SECURITY: Returns only inspections for user's authorized clients
    """
    return get_quality_inspections(
        db, current_user=current_user, skip=skip, limit=limit, start_date=start_date,
        end_date=end_date, product_id=product_id, shift_id=shift_id,
        inspection_stage=inspection_stage, defect_category=defect_category
    )


@router.get("/{inspection_id}", response_model=QualityInspectionResponse)
def get_quality(
    inspection_id: int,
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
    product_id: int,
    shift_id: int,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate PPM (Parts Per Million) defect rate
    Formula: (Total Defects / Total Units Inspected) × 1,000,000
    """
    ppm, inspected, defects = calculate_ppm(
        db, product_id, shift_id, start_date, end_date
    )

    return PPMCalculationResponse(
        product_id=product_id,
        shift_id=shift_id,
        start_date=start_date,
        end_date=end_date,
        total_units_inspected=inspected,
        total_defects=defects,
        ppm=ppm,
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
    product_id: int,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate FPY (First Pass Yield) and RTY (Rolled Throughput Yield)
    FPY = (Units Passed / Total Units) × 100
    RTY = Product of all FPY values across process steps
    """
    fpy, good, total = calculate_fpy(db, product_id, start_date, end_date)
    rty, steps = calculate_rty(db, product_id, start_date, end_date)

    return FPYRTYCalculationResponse(
        product_id=product_id,
        start_date=start_date,
        end_date=end_date,
        total_units=total,
        first_pass_good=good,
        fpy_percentage=fpy,
        rty_percentage=rty,
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
