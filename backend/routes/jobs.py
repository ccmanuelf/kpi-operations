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
