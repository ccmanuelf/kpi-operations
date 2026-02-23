"""
Job Service
Thin service layer wrapping Job CRUD operations.
Routes should import from this module instead of backend.crud.job directly.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.crud.job import (
    create_job,
    get_job,
    get_jobs,
    get_jobs_by_work_order,
    update_job,
    delete_job,
    complete_job,
)


def create_job_record(db: Session, job_data: dict, current_user: User):
    """Create a new job."""
    return create_job(db, job_data, current_user)


def get_job_by_id(db: Session, job_id: str, current_user: User):
    """Get a job by ID."""
    return get_job(db, job_id, current_user)


def list_jobs(
    db: Session,
    current_user: User,
    work_order_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
):
    """List jobs with filters."""
    return get_jobs(db, current_user, work_order_id, skip, limit)


def list_jobs_by_work_order(db: Session, work_order_id: str, current_user: User):
    """Get jobs for a specific work order."""
    return get_jobs_by_work_order(db, work_order_id, current_user)


def update_job_record(db: Session, job_id: str, job_data: dict, current_user: User):
    """Update a job."""
    return update_job(db, job_id, job_data, current_user)


def delete_job_record(db: Session, job_id: str, current_user: User) -> bool:
    """Delete a job."""
    return delete_job(db, job_id, current_user)


def complete_job_record(db: Session, job_id: str, current_user: User):
    """Mark a job as complete."""
    return complete_job(db, job_id, current_user)
