"""
Quality Inspection - FPY/RTY and Quality Score Endpoints

First Pass Yield (FPY), Rolled Throughput Yield (RTY), detailed breakdown
with repair/rework distinction, and comprehensive quality score calculation.
"""

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.models.quality import FPYRTYCalculationResponse, InferenceMetadata
from backend.calculations.fpy_rty import (
    calculate_quality_score,
    calculate_fpy_with_repair_breakdown,
    calculate_rty_with_repair_impact,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

fpy_rty_router = APIRouter()


@fpy_rty_router.get("/kpi/fpy-rty", response_model=FPYRTYCalculationResponse)
def calculate_fpy_rty_kpi(
    product_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FPYRTYCalculationResponse:
    """
    Calculate FPY (First Pass Yield) and RTY (Rolled Throughput Yield) with client filtering
    FPY = (Units Passed / Total Units) × 100
    RTY = Product of all FPY values across process steps (inspection stages)

    Parameters are optional - defaults to all products and last 30 days
    """
    from datetime import timedelta
    from backend.schemas.quality_entry import QualityEntry
    from sqlalchemy import func

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Overall FPY query
    query = db.query(
        func.sum(QualityEntry.units_inspected).label("total"),
        func.sum(QualityEntry.units_passed).label("good"),
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
    )

    if effective_client_id:
        query = query.filter(QualityEntry.client_id == effective_client_id)

    result = query.first()
    total = result.total or 0
    good = result.good or 0
    fpy = (good / total * 100) if total > 0 else 0

    # Total scrapped for Final Yield
    scrapped_query = db.query(func.sum(QualityEntry.units_scrapped).label("scrapped")).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
    )
    if effective_client_id:
        scrapped_query = scrapped_query.filter(QualityEntry.client_id == effective_client_id)
    scrapped_result = scrapped_query.first()
    total_scrapped = scrapped_result.scrapped or 0

    # Final Yield = (Total Inspected - Scrapped) / Total Inspected × 100
    final_yield = ((total - total_scrapped) / total * 100) if total > 0 else 0

    # RTY per inspection stage
    stage_query = db.query(
        QualityEntry.inspection_stage,
        func.sum(QualityEntry.units_inspected).label("stage_total"),
        func.sum(QualityEntry.units_passed).label("stage_passed"),
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time()),
        QualityEntry.inspection_stage.isnot(None),
    )
    if effective_client_id:
        stage_query = stage_query.filter(QualityEntry.client_id == effective_client_id)
    stage_results = stage_query.group_by(QualityEntry.inspection_stage).all()

    steps = []
    rty_decimal = 1.0
    for stage in stage_results:
        stage_total = stage.stage_total or 0
        stage_passed = stage.stage_passed or 0
        if stage_total > 0:
            stage_fpy = stage_passed / stage_total
            rty_decimal *= stage_fpy
            steps.append({
                "stage": stage.inspection_stage,
                "fpy": round(stage_fpy * 100, 2),
                "total": stage_total,
                "passed": stage_passed,
            })

    rty = rty_decimal * 100 if steps else fpy

    is_estimated = total == 0 or (not steps and fpy > 0)
    inference = InferenceMetadata(
        is_estimated=is_estimated,
        confidence_score=1.0 if total > 0 and steps else (0.7 if total > 0 else 0.3),
        inference_source=(
            "actual_data"
            if total > 0 and steps
            else ("overall_fpy_fallback" if total > 0 else "system_fallback")
        ),
        inference_warning=(
            "RTY calculation used overall FPY as fallback (no stage-specific data)"
            if (total > 0 and not steps)
            else ("No quality data available" if total == 0 else None)
        ),
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
        calculation_timestamp=datetime.now(tz=timezone.utc),
        inference=inference,
    )


@fpy_rty_router.get("/kpi/fpy-rty-breakdown")
def get_fpy_rty_breakdown(
    product_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    inspection_stage: Optional[str] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
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

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    effective_product_id = product_id or 0

    fpy_breakdown = calculate_fpy_with_repair_breakdown(
        db, effective_product_id, start_date, end_date, inspection_stage
    )
    rty_breakdown = calculate_rty_with_repair_impact(db, effective_product_id, start_date, end_date)

    return {
        "period": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
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
            "recovery_rate": float(fpy_breakdown["recovery_rate"]),
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
                    "repair_rate": float(step["repair_rate"]),
                }
                for step in rty_breakdown["step_details"]
            ],
            "total_rework": rty_breakdown["total_rework"],
            "total_repair": rty_breakdown["total_repair"],
            "total_scrap": rty_breakdown["total_scrap"],
            "rework_impact_percentage": float(rty_breakdown["rework_impact_percentage"]),
            "repair_impact_percentage": float(rty_breakdown["repair_impact_percentage"]),
            "throughput_loss_percentage": float(rty_breakdown["throughput_loss_percentage"]),
            "interpretation": rty_breakdown["interpretation"],
        },
        "calculation_timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


@fpy_rty_router.get("/kpi/quality-score")
def get_quality_score(
    product_id: int,
    start_date: date,
    end_date: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Calculate comprehensive quality score combining multiple metrics
    Includes FPY, RTY, PPM, and DPMO analysis
    """
    return calculate_quality_score(db, product_id, start_date, end_date)
