"""
Employee Management API Routes
All employee CRUD endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.models.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeWithClients,
    EmployeeAssignmentRequest,
    FloatingPoolAssignmentRequest as EmployeeFloatingPoolRequest,
)
from backend.crud.employee import (
    create_employee,
    get_employee,
    get_employees,
    update_employee,
    delete_employee,
    get_employees_by_client,
    get_floating_pool_employees,
    assign_to_floating_pool,
    remove_from_floating_pool,
    assign_employee_to_client,
)
from backend.auth.jwt import get_current_user
from backend.schemas.user import User


router = APIRouter(prefix="/api/employees", tags=["Employees"])


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def create_employee_endpoint(
    employee: EmployeeCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Create new employee
    SECURITY: Supervisor/admin only
    """
    employee_data = employee.model_dump()
    return create_employee(db, employee_data, current_user)


@router.get("", response_model=List[EmployeeResponse])
def list_employees(
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[str] = None,
    is_floating_pool: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List employees with filters
    """
    return get_employees(db, current_user, skip, limit, client_id, is_floating_pool)


@router.get("/floating-pool/list", response_model=List[EmployeeResponse])
def get_floating_pool_employees_endpoint(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get all floating pool employees
    """
    return get_floating_pool_employees(db, current_user, skip, limit)


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee_endpoint(
    employee_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get employee by ID
    """
    employee = get_employee(db, employee_id, current_user)
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee_endpoint(
    employee_id: int,
    employee_update: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update employee
    SECURITY: Supervisor/admin only
    """
    employee_data = employee_update.model_dump(exclude_unset=True)
    updated = update_employee(db, employee_id, employee_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Employee not found")
    return updated


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_employee_endpoint(
    employee_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Delete employee (admin only)
    SECURITY: Admin only
    """
    success = delete_employee(db, employee_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Employee not found")


@router.post("/{employee_id}/floating-pool/assign", response_model=EmployeeResponse)
def assign_employee_to_floating_pool(
    employee_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Assign employee to floating pool
    SECURITY: Supervisor/admin only
    """
    return assign_to_floating_pool(db, employee_id, current_user)


@router.post("/{employee_id}/floating-pool/remove", response_model=EmployeeResponse)
def remove_employee_from_floating_pool(
    employee_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Remove employee from floating pool
    SECURITY: Supervisor/admin only
    """
    return remove_from_floating_pool(db, employee_id, current_user)


@router.post("/{employee_id}/assign-client", response_model=EmployeeResponse)
def assign_employee_to_client_endpoint(
    employee_id: int,
    assignment: EmployeeAssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Assign employee to a client
    SECURITY: Supervisor/admin only, verifies client access
    """
    return assign_employee_to_client(db, employee_id, assignment.client_id, current_user)


# Client employees endpoint (separate prefix for /api/clients namespace)
client_employees_router = APIRouter(prefix="/api/clients", tags=["Employees"])


@client_employees_router.get("/{client_id}/employees", response_model=List[EmployeeResponse])
def get_client_employees(
    client_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all employees assigned to a specific client
    SECURITY: Verifies user has access to client
    """
    return get_employees_by_client(db, client_id, current_user, skip, limit)
