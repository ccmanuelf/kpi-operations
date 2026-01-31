"""
Job (Work Order Line Items) API Routes
All job CRUD endpoints - core data entity

Phase 6.6: Includes job-level RTY calculation endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from backend.database import get_db
from backend.models.job import (
    JobCreate,
    JobUpdate,
    JobComplete,
    JobResponse
)
from backend.crud.job import (
    create_job,
    get_job,
    get_jobs,
    get_jobs_by_work_order,
    update_job,
    delete_job,
    complete_job
)
from backend.calculations.fpy_rty import (
    calculate_job_yield,
    calculate_work_order_job_rty,
    calculate_job_rty_summary
)
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User


router = APIRouter(
    prefix="/api/jobs",
    tags=["Jobs"]
)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job_endpoint(
    job: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new job (work order line item)
    SECURITY: Enforces client filtering
    """
    job_data = job.model_dump()
    return create_job(db, job_data, current_user)


@router.get("", response_model=List[JobResponse])
def list_jobs(
    work_order_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List jobs with optional work order filter
    SECURITY: Returns only jobs for user's authorized clients
    """
    return get_jobs(db, current_user, work_order_id, skip, limit)


@router.get("/{job_id}", response_model=JobResponse)
def get_job_endpoint(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get job by ID
    SECURITY: Verifies user has access to job's client
    """
    job = get_job(db, job_id, current_user)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
    return job


@router.put("/{job_id}", response_model=JobResponse)
def update_job_endpoint(
    job_id: str,
    job_update: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update job
    SECURITY: Verifies user has access to job's client
    """
    job_data = job_update.model_dump(exclude_unset=True)
    updated = update_job(db, job_id, job_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
    return updated


@router.post("/{job_id}/complete", response_model=JobResponse)
def complete_job_endpoint(
    job_id: str,
    completion: JobComplete,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Mark job as completed with actual quantities and hours
    SECURITY: Verifies user has access to job's client
    """
    completed = complete_job(
        db,
        job_id,
        completion.completed_quantity,
        float(completion.actual_hours),
        current_user
    )
    if not completed:
        raise HTTPException(status_code=404, detail="Job not found or access denied")
    return completed


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job_endpoint(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """
    Delete job (supervisor only)
    SECURITY: Only deletes if user has access to job's client
    """
    success = delete_job(db, job_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found or access denied")


# Work order jobs endpoint (separate prefix for /api/work-orders namespace)
work_order_jobs_router = APIRouter(
    prefix="/api/work-orders",
    tags=["Jobs"]
)


@work_order_jobs_router.get("/{work_order_id}/jobs", response_model=List[JobResponse])
def get_work_order_jobs(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all jobs for a specific work order
    SECURITY: Returns only jobs for user's authorized clients
    """
    return get_jobs_by_work_order(db, work_order_id, current_user)


# ============================================================================
# PHASE 6.6: JOB-LEVEL RTY CALCULATION ENDPOINTS
# ============================================================================

@router.get("/{job_id}/yield")
def get_job_yield(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate yield metrics for a specific job (line item).

    Phase 6.6: Job-level yield calculation.

    Returns yield percentage, good units, and scrapped units for the job.
    """
    # First verify user has access to this job
    job = get_job(db, job_id, current_user)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")

    return calculate_job_yield(db, job_id)


@work_order_jobs_router.get("/{work_order_id}/rty")
def get_work_order_job_rty(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate RTY across all jobs within a work order.

    Phase 6.6: Job-level RTY calculation.

    Returns:
    - RTY percentage rolled across all job operations
    - Per-job yield breakdown
    - Bottleneck identification (lowest yield job)
    - Total scrap across all jobs
    """
    # Determine client filter
    client_id = None
    if current_user.role != 'admin' and current_user.client_id_assigned:
        client_id = current_user.client_id_assigned

    result = calculate_work_order_job_rty(db, work_order_id, client_id)

    if "error" in result and result.get("job_count", 0) == 0:
        raise HTTPException(status_code=404, detail=result.get("error", "No jobs found"))

    return result


@router.get("/kpi/rty-summary")
def get_job_rty_summary(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get aggregate job-level RTY summary for a date range.

    Phase 6.6: Job-level RTY reporting.

    Returns:
    - Total jobs completed in period
    - Average job yield
    - Overall yield (all units)
    - Jobs below target count
    - Top scrap operations
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

    return calculate_job_rty_summary(db, start_date, end_date, effective_client_id)


# ============================================================================
# PHASE 4: JOB-LEVEL KPI CALCULATION ENDPOINTS
# ============================================================================

@router.get("/{job_id}/efficiency")
def get_job_efficiency(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate efficiency metrics for a specific job.

    Phase 4.1: Job-level efficiency calculation.

    Aggregates all production entries linked to this job and calculates:
    - Total efficiency percentage
    - Total units produced
    - Total labor hours used
    - Average efficiency per shift
    """
    from backend.services.production_kpi_service import ProductionKPIService
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.job import Job
    from decimal import Decimal

    # Verify user has access to this job
    job = get_job(db, job_id, current_user)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")

    # Get all production entries for this job
    entries = db.query(ProductionEntry).filter(
        ProductionEntry.job_id == job_id
    ).all()

    if not entries:
        return {
            "job_id": job_id,
            "efficiency_percentage": 0,
            "total_units_produced": 0,
            "total_labor_hours": 0,
            "entry_count": 0,
            "message": "No production entries found for this job"
        }

    # Calculate aggregated metrics
    service = ProductionKPIService(db)
    total_units = 0
    total_labor_hours = Decimal("0")
    efficiency_sum = Decimal("0")
    efficiency_count = 0

    for entry in entries:
        total_units += entry.units_produced
        total_labor_hours += Decimal(str(entry.run_time_hours)) * (entry.employees_assigned or 1)

        kpi = service.calculate_efficiency_only(entry)
        efficiency_sum += kpi.efficiency_percentage
        efficiency_count += 1

    avg_efficiency = efficiency_sum / efficiency_count if efficiency_count > 0 else Decimal("0")

    return {
        "job_id": job_id,
        "part_number": job.part_number if hasattr(job, 'part_number') else None,
        "efficiency_percentage": float(avg_efficiency),
        "total_units_produced": total_units,
        "total_labor_hours": float(total_labor_hours),
        "entry_count": efficiency_count,
        "entries": [
            {
                "production_entry_id": e.production_entry_id,
                "units_produced": e.units_produced,
                "efficiency_percentage": float(e.efficiency_percentage or 0)
            }
            for e in entries
        ]
    }


@router.get("/{job_id}/performance")
def get_job_performance(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate performance metrics for a specific job.

    Phase 4.1: Job-level performance calculation.

    Aggregates all production entries linked to this job.
    """
    from backend.services.production_kpi_service import ProductionKPIService
    from backend.schemas.production_entry import ProductionEntry
    from decimal import Decimal

    # Verify user has access to this job
    job = get_job(db, job_id, current_user)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")

    # Get all production entries for this job
    entries = db.query(ProductionEntry).filter(
        ProductionEntry.job_id == job_id
    ).all()

    if not entries:
        return {
            "job_id": job_id,
            "performance_percentage": 0,
            "total_units_produced": 0,
            "entry_count": 0,
            "message": "No production entries found for this job"
        }

    # Calculate aggregated metrics
    service = ProductionKPIService(db)
    total_units = 0
    total_run_time = Decimal("0")
    performance_sum = Decimal("0")

    for entry in entries:
        total_units += entry.units_produced
        total_run_time += Decimal(str(entry.run_time_hours))

        kpi = service.calculate_performance_only(entry)
        performance_sum += kpi.performance_percentage

    avg_performance = performance_sum / len(entries) if entries else Decimal("0")

    return {
        "job_id": job_id,
        "performance_percentage": float(avg_performance),
        "total_units_produced": total_units,
        "total_run_time_hours": float(total_run_time),
        "entry_count": len(entries)
    }


@router.get("/{job_id}/ppm")
def get_job_ppm(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate PPM (Parts Per Million) for a specific job.

    Phase 4.2: Job-level PPM calculation.

    Aggregates all quality entries linked to this job.
    """
    from backend.schemas.quality_entry import QualityEntry
    from backend.calculations.ppm import calculate_ppm_pure
    from decimal import Decimal

    # Verify user has access to this job
    job = get_job(db, job_id, current_user)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")

    # Get all quality entries for this job
    entries = db.query(QualityEntry).filter(
        QualityEntry.job_id == job_id
    ).all()

    if not entries:
        return {
            "job_id": job_id,
            "ppm": 0,
            "total_inspected": 0,
            "total_defects": 0,
            "entry_count": 0,
            "message": "No quality entries found for this job"
        }

    # Aggregate totals
    total_inspected = sum(e.units_inspected or 0 for e in entries)
    total_defects = sum(e.units_defective or 0 for e in entries)

    ppm = calculate_ppm_pure(total_inspected, total_defects)

    return {
        "job_id": job_id,
        "ppm": float(ppm),
        "total_inspected": total_inspected,
        "total_defects": total_defects,
        "entry_count": len(entries)
    }


@router.get("/{job_id}/dpmo")
def get_job_dpmo(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Calculate DPMO (Defects Per Million Opportunities) for a specific job.

    Phase 4.2: Job-level DPMO calculation.

    Uses part-specific opportunities if available in PART_OPPORTUNITIES table.
    """
    from backend.schemas.quality_entry import QualityEntry
    from backend.calculations.dpmo import (
        calculate_dpmo_pure,
        calculate_sigma_level_pure,
        get_opportunities_for_part,
        get_client_opportunities_default
    )

    # Verify user has access to this job
    job = get_job(db, job_id, current_user)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")

    # Get all quality entries for this job
    entries = db.query(QualityEntry).filter(
        QualityEntry.job_id == job_id
    ).all()

    if not entries:
        return {
            "job_id": job_id,
            "dpmo": 0,
            "sigma_level": 0,
            "total_opportunities": 0,
            "entry_count": 0,
            "message": "No quality entries found for this job"
        }

    # Get opportunities per unit (part-specific or default)
    client_id = getattr(job, 'client_id', None)
    part_number = getattr(job, 'part_number', None)

    if part_number:
        opportunities_per_unit = get_opportunities_for_part(db, part_number, client_id)
        using_part_specific = True
    else:
        opportunities_per_unit = get_client_opportunities_default(db, client_id)
        using_part_specific = False

    # Aggregate totals
    total_inspected = sum(e.units_inspected or 0 for e in entries)
    total_defects = sum(e.total_defects_count or e.units_defective or 0 for e in entries)

    dpmo, total_opportunities = calculate_dpmo_pure(total_defects, total_inspected, opportunities_per_unit)
    sigma_level = calculate_sigma_level_pure(dpmo)

    return {
        "job_id": job_id,
        "dpmo": float(dpmo),
        "sigma_level": float(sigma_level),
        "total_inspected": total_inspected,
        "total_defects": total_defects,
        "total_opportunities": total_opportunities,
        "opportunities_per_unit": opportunities_per_unit,
        "using_part_specific_opportunities": using_part_specific,
        "entry_count": len(entries)
    }


@router.get("/{job_id}/kpi-summary")
def get_job_kpi_summary(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive KPI summary for a specific job.

    Phase 4.3: Combined job-level KPI endpoint.

    Returns all KPIs in a single response:
    - Efficiency
    - Performance
    - Yield
    - PPM
    - DPMO with Sigma Level
    """
    from backend.services.production_kpi_service import ProductionKPIService
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.quality_entry import QualityEntry
    from backend.calculations.ppm import calculate_ppm_pure
    from backend.calculations.dpmo import (
        calculate_dpmo_pure,
        calculate_sigma_level_pure,
        get_opportunities_for_part,
        get_client_opportunities_default
    )
    from backend.calculations.fpy_rty import calculate_job_yield_pure
    from decimal import Decimal

    # Verify user has access to this job
    job = get_job(db, job_id, current_user)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or access denied")

    # Get production entries
    production_entries = db.query(ProductionEntry).filter(
        ProductionEntry.job_id == job_id
    ).all()

    # Get quality entries
    quality_entries = db.query(QualityEntry).filter(
        QualityEntry.job_id == job_id
    ).all()

    # Calculate production KPIs
    service = ProductionKPIService(db)
    efficiency_sum = Decimal("0")
    performance_sum = Decimal("0")
    total_units = 0
    total_defects = 0
    total_scrap = 0

    for entry in production_entries:
        total_units += entry.units_produced
        total_defects += entry.defect_count or 0
        total_scrap += entry.scrap_count or 0

        eff_result = service.calculate_efficiency_only(entry)
        perf_result = service.calculate_performance_only(entry)
        efficiency_sum += eff_result.efficiency_percentage
        performance_sum += perf_result.performance_percentage

    avg_efficiency = efficiency_sum / len(production_entries) if production_entries else Decimal("0")
    avg_performance = performance_sum / len(production_entries) if production_entries else Decimal("0")

    # Calculate production quality rate
    if total_units > 0:
        good_units = total_units - total_defects - total_scrap
        production_quality_rate = (Decimal(str(good_units)) / Decimal(str(total_units))) * 100
    else:
        production_quality_rate = Decimal("0")

    # Calculate quality KPIs from QC entries
    qc_total_inspected = sum(e.units_inspected or 0 for e in quality_entries)
    qc_total_defects = sum(e.units_defective or 0 for e in quality_entries)
    qc_total_defects_count = sum(e.total_defects_count or e.units_defective or 0 for e in quality_entries)

    ppm = calculate_ppm_pure(qc_total_inspected, qc_total_defects)

    # Get opportunities for DPMO
    client_id = getattr(job, 'client_id', None)
    part_number = getattr(job, 'part_number', None)
    if part_number:
        opportunities_per_unit = get_opportunities_for_part(db, part_number, client_id)
    else:
        opportunities_per_unit = get_client_opportunities_default(db, client_id)

    dpmo, total_opportunities = calculate_dpmo_pure(qc_total_defects_count, qc_total_inspected, opportunities_per_unit)
    sigma_level = calculate_sigma_level_pure(dpmo)

    # Calculate job yield
    completed_qty = getattr(job, 'completed_quantity', 0) or 0
    scrapped_qty = getattr(job, 'quantity_scrapped', 0) or 0
    yield_pct = calculate_job_yield_pure(completed_qty, scrapped_qty)

    return {
        "job_id": job_id,
        "part_number": part_number,
        "status": getattr(job, 'status', None),
        "production_kpis": {
            "efficiency_percentage": float(avg_efficiency),
            "performance_percentage": float(avg_performance),
            "quality_rate": float(production_quality_rate),
            "total_units_produced": total_units,
            "defect_count": total_defects,
            "scrap_count": total_scrap,
            "entry_count": len(production_entries)
        },
        "quality_kpis": {
            "ppm": float(ppm),
            "dpmo": float(dpmo),
            "sigma_level": float(sigma_level),
            "total_inspected": qc_total_inspected,
            "total_defects": qc_total_defects,
            "opportunities_per_unit": opportunities_per_unit,
            "entry_count": len(quality_entries)
        },
        "yield": {
            "yield_percentage": float(yield_pct),
            "completed_quantity": completed_qty,
            "quantity_scrapped": scrapped_qty
        }
    }
