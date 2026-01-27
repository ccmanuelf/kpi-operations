"""
Floating Pool Management API Routes
All floating pool CRUD and assignment endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from backend.database import get_db
from backend.models.floating_pool import (
    FloatingPoolCreate,
    FloatingPoolUpdate,
    FloatingPoolResponse,
    FloatingPoolAssignmentRequest,
    FloatingPoolUnassignmentRequest,
    FloatingPoolAvailability,
    FloatingPoolSummary
)
from backend.crud.floating_pool import (
    create_floating_pool_entry,
    get_floating_pool_entry,
    get_floating_pool_entries,
    update_floating_pool_entry,
    delete_floating_pool_entry,
    assign_floating_pool_to_client,
    unassign_floating_pool_from_client,
    get_available_floating_pool_employees,
    get_floating_pool_assignments_by_client,
    is_employee_available_for_assignment,
    get_floating_pool_summary
)
from backend.auth.jwt import get_current_user
from backend.schemas.user import User


router = APIRouter(
    prefix="/api/floating-pool",
    tags=["Floating Pool"]
)


@router.post("", response_model=FloatingPoolResponse, status_code=status.HTTP_201_CREATED)
def create_floating_pool_entry_endpoint(
    pool_entry: FloatingPoolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new floating pool entry
    SECURITY: Supervisor/admin only
    """
    pool_data = pool_entry.model_dump()
    return create_floating_pool_entry(db, pool_data, current_user)


@router.get("", response_model=List[FloatingPoolResponse])
def list_floating_pool_entries(
    skip: int = 0,
    limit: int = 100,
    employee_id: Optional[int] = None,
    available_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List floating pool entries with filters
    """
    return get_floating_pool_entries(db, current_user, skip, limit, employee_id, available_only)


@router.get("/available/list")
def get_available_floating_pool_list(
    as_of_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all currently available floating pool employees
    """
    return get_available_floating_pool_employees(db, current_user, as_of_date)


@router.get("/check-availability/{employee_id}")
def check_employee_availability(
    employee_id: int,
    proposed_start: Optional[datetime] = None,
    proposed_end: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Check if an employee is available for a new assignment.
    Returns availability status with conflict details if any.

    Use this before attempting to assign an employee to prevent double-assignment errors.

    Returns:
        {
            "is_available": bool,
            "current_assignment": str or None,
            "conflict_dates": dict or None,
            "message": str
        }
    """
    return is_employee_available_for_assignment(
        db, employee_id, proposed_start, proposed_end
    )


@router.get("/summary")
def get_floating_pool_summary_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get summary statistics for floating pool.
    Useful for dashboard widgets.

    Returns:
        {
            "total_floating_pool_employees": int,
            "currently_available": int,
            "currently_assigned": int,
            "available_employees": list
        }
    """
    return get_floating_pool_summary(db, current_user)


@router.get("/{pool_id}", response_model=FloatingPoolResponse)
def get_floating_pool_entry_endpoint(
    pool_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get floating pool entry by ID
    """
    pool_entry = get_floating_pool_entry(db, pool_id, current_user)
    if not pool_entry:
        raise HTTPException(status_code=404, detail="Floating pool entry not found")
    return pool_entry


@router.put("/{pool_id}", response_model=FloatingPoolResponse)
def update_floating_pool_entry_endpoint(
    pool_id: int,
    pool_update: FloatingPoolUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update floating pool entry
    SECURITY: Supervisor/admin only
    """
    pool_data = pool_update.model_dump(exclude_unset=True)
    updated = update_floating_pool_entry(db, pool_id, pool_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Floating pool entry not found")
    return updated


@router.delete("/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_floating_pool_entry_endpoint(
    pool_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete floating pool entry
    SECURITY: Supervisor/admin only
    """
    success = delete_floating_pool_entry(db, pool_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Floating pool entry not found")


@router.post("/assign", response_model=FloatingPoolResponse)
def assign_floating_pool_employee_to_client(
    assignment: FloatingPoolAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Assign floating pool employee to a client
    SECURITY: Supervisor/admin only, verifies client access
    """
    return assign_floating_pool_to_client(
        db,
        assignment.employee_id,
        assignment.client_id,
        assignment.available_from,
        assignment.available_to,
        current_user,
        assignment.notes
    )


@router.post("/unassign", response_model=FloatingPoolResponse)
def unassign_floating_pool_employee_from_client(
    unassignment: FloatingPoolUnassignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Unassign floating pool employee from client
    SECURITY: Supervisor/admin only
    """
    return unassign_floating_pool_from_client(db, unassignment.pool_id, current_user)


# Client floating pool endpoint (separate prefix for /api/clients namespace)
client_floating_pool_router = APIRouter(
    prefix="/api/clients",
    tags=["Floating Pool"]
)


@client_floating_pool_router.get("/{client_id}/floating-pool", response_model=List[FloatingPoolResponse])
def get_client_floating_pool_assignments(
    client_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all floating pool assignments for a specific client
    SECURITY: Verifies user has access to client
    """
    return get_floating_pool_assignments_by_client(db, client_id, current_user, skip, limit)
