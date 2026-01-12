"""
CRUD operations for JOB (Work Order Line Items)
Create, Read, Update, Delete with multi-tenant client filtering
SECURITY: All operations enforce client-based access control
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException

from backend.schemas.job import Job
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.utils.soft_delete import soft_delete


def create_job(
    db: Session,
    job_data: dict,
    current_user: User
) -> Job:
    """
    Create new job (work order line item)
    SECURITY: Verifies user has access to the specified client

    Args:
        db: Database session
        job_data: Job data dictionary
        current_user: Authenticated user

    Returns:
        Created job

    Raises:
        ClientAccessError: If user doesn't have access to job_data['client_id_fk']
    """
    # Verify client access
    verify_client_access(current_user, job_data.get('client_id_fk'))

    db_job = Job(**job_data)
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    return db_job


def get_job(
    db: Session,
    job_id: str,
    current_user: User
) -> Optional[Job]:
    """
    Get job by ID with client filtering
    SECURITY: Returns None if user doesn't have access to job's client

    Args:
        db: Database session
        job_id: Job ID
        current_user: Authenticated user

    Returns:
        Job if found and user has access, None otherwise
    """
    query = db.query(Job).filter(Job.job_id == job_id)

    # Apply client filtering
    client_filter = build_client_filter_clause(current_user, Job.client_id_fk)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.first()


def get_jobs(
    db: Session,
    current_user: User,
    work_order_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Job]:
    """
    List jobs with client filtering
    SECURITY: Returns only jobs for user's authorized clients

    Args:
        db: Database session
        current_user: Authenticated user
        work_order_id: Optional filter by work order
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        List of jobs user has access to
    """
    query = db.query(Job)

    # Apply client filtering
    client_filter = build_client_filter_clause(current_user, Job.client_id_fk)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Optional work order filter
    if work_order_id:
        query = query.filter(Job.work_order_id == work_order_id)

    return query.offset(skip).limit(limit).all()


def get_jobs_by_work_order(
    db: Session,
    work_order_id: str,
    current_user: User
) -> List[Job]:
    """
    Get all jobs for a specific work order with client filtering
    SECURITY: Returns only jobs for user's authorized clients

    Args:
        db: Database session
        work_order_id: Work order ID
        current_user: Authenticated user

    Returns:
        List of jobs for the work order
    """
    query = db.query(Job).filter(Job.work_order_id == work_order_id)

    # Apply client filtering
    client_filter = build_client_filter_clause(current_user, Job.client_id_fk)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.all()


def update_job(
    db: Session,
    job_id: str,
    job_update: dict,
    current_user: User
) -> Optional[Job]:
    """
    Update job with client access verification
    SECURITY: Verifies user has access to the job's client

    Args:
        db: Database session
        job_id: Job ID to update
        job_update: Fields to update
        current_user: Authenticated user

    Returns:
        Updated job if found and user has access, None otherwise
    """
    job = get_job(db, job_id, current_user)
    if not job:
        return None

    # Update fields
    for key, value in job_update.items():
        if hasattr(job, key) and key != 'job_id':  # Prevent ID changes
            setattr(job, key, value)

    db.commit()
    db.refresh(job)
    return job


def delete_job(
    db: Session,
    job_id: str,
    current_user: User
) -> bool:
    """
    Soft delete job (sets is_active = False)
    SECURITY: Only deletes if user has access to the job's client

    Args:
        db: Database session
        job_id: Job ID to delete
        current_user: Authenticated user

    Returns:
        True if soft deleted, False if not found or no access
    """
    job = get_job(db, job_id, current_user)
    if not job:
        return False

    # Soft delete - preserves data integrity
    return soft_delete(db, job)


def complete_job(
    db: Session,
    job_id: str,
    completed_quantity: int,
    actual_hours: float,
    current_user: User
) -> Optional[Job]:
    """
    Mark job as completed with actual quantities and hours
    SECURITY: Verifies user has access to the job's client

    Args:
        db: Database session
        job_id: Job ID
        completed_quantity: Actual quantity completed
        actual_hours: Actual hours spent
        current_user: Authenticated user

    Returns:
        Updated job if successful, None if not found or no access
    """
    from datetime import datetime

    job = get_job(db, job_id, current_user)
    if not job:
        return None

    job.completed_quantity = completed_quantity
    job.actual_hours = actual_hours
    job.is_completed = 1
    job.completed_date = datetime.now()

    db.commit()
    db.refresh(job)
    return job
