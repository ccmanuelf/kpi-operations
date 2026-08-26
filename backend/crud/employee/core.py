"""
CRUD core operations for Employee
Create, Read, Update, Delete with multi-tenant security
SECURITY: Multi-tenant client filtering enabled
"""

from typing import List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.orm.employee import Employee
from backend.orm.user import User, SUPERVISORY_ROLES
from backend.middleware.client_auth import (
    client_token_clause,
    get_user_client_filter,
    verify_client_access,
    verify_employee_access,
)
from backend.utils.soft_delete import soft_delete


def create_employee(db: Session, employee_data: dict, current_user: User) -> Employee:
    """
    Create new employee
    SECURITY: Supervisors and admins only

    Args:
        db: Database session
        employee_data: Employee data dictionary
        current_user: Authenticated user

    Returns:
        Created employee

    Raises:
        HTTPException 403: If user doesn't have permission
        HTTPException 400: If employee_code already exists
    """
    # SECURITY: Only supervisors and admins can create employees
    if current_user.role not in SUPERVISORY_ROLES:
        raise HTTPException(status_code=403, detail="Only supervisors and admins can create employees")

    # Check if employee_code already exists
    existing = db.query(Employee).filter(Employee.employee_code == employee_data.get("employee_code")).first()

    if existing:
        raise HTTPException(
            status_code=400, detail=f"Employee with code {employee_data.get('employee_code')} already exists"
        )

    # Create employee
    db_employee = Employee(**employee_data)

    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)

    return db_employee


def get_employee(db: Session, employee_id: int, current_user: User) -> Optional[Employee]:
    """
    Get employee by ID

    Args:
        db: Database session
        employee_id: Employee ID
        current_user: Authenticated user

    Returns:
        Employee or None if not found

    Raises:
        HTTPException 404: If employee not found
        HTTPException 403: If the employee belongs to a client the caller is
            not assigned to
    """
    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # SECURITY: current_user was accepted but unused here, so any authenticated
    # user could read any client's employee by id.
    verify_employee_access(current_user, employee, db)

    return employee


def get_employees(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[str] = None,
    is_floating_pool: Optional[bool] = None,
) -> List[Employee]:
    """
    Get employees with filtering

    Args:
        db: Database session
        current_user: Authenticated user
        skip: Number of records to skip
        limit: Maximum records to return
        client_id: Filter by client assignment
        is_floating_pool: Filter by floating pool status

    Returns:
        List of employees
    """
    query = db.query(Employee)

    # SECURITY: confine the listing to the caller's clients. EMPLOYEE ownership
    # is the comma-separated client_id_assigned, so this matches whole tokens
    # via client_token_clause rather than an IN. It must agree exactly with
    # verify_employee_access, which the by-id routes use: a substring LIKE made
    # the listing MORE permissive than the by-id route on the same row (a caller
    # scoped to ACME saw ACME-WEST's employees but got 403 fetching one).
    # Employees with no assignment are shared floating-pool resources and stay
    # visible — the same rule verify_employee_access applies. Without any of
    # this the listing returned every tenant's employees to any authenticated
    # user.
    user_clients = get_user_client_filter(current_user, db)
    if user_clients is not None:
        query = query.filter(
            or_(
                *[client_token_clause(Employee.client_id_assigned, c) for c in user_clients],
                Employee.client_id_assigned.is_(None),
            )
        )

    # Apply filters
    if client_id:
        # SECURITY: an explicit client_id must be one the caller may see.
        verify_client_access(current_user, client_id, db)
        # Filter employees assigned to specific client
        query = query.filter(client_token_clause(Employee.client_id_assigned, client_id))

    if is_floating_pool is not None:
        query = query.filter(Employee.is_floating_pool == (1 if is_floating_pool else 0))

    return query.order_by(Employee.employee_name).offset(skip).limit(limit).all()


def update_employee(db: Session, employee_id: int, employee_update: dict, current_user: User) -> Optional[Employee]:
    """
    Update employee
    SECURITY: Supervisors and admins only

    Args:
        db: Database session
        employee_id: Employee ID to update
        employee_update: Update data dictionary
        current_user: Authenticated user

    Returns:
        Updated employee or None if not found

    Raises:
        HTTPException 403: If user doesn't have permission
        HTTPException 404: If employee not found
    """
    # SECURITY: Only supervisors and admins can update employees
    if current_user.role not in SUPERVISORY_ROLES:
        raise HTTPException(status_code=403, detail="Only supervisors and admins can update employees")

    db_employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()

    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # SECURITY: the role check above does not bind the caller to a tenant.
    verify_employee_access(current_user, db_employee, db)

    # Update fields
    for field, value in employee_update.items():
        if hasattr(db_employee, field):
            setattr(db_employee, field, value)

    db.commit()
    db.refresh(db_employee)

    return db_employee


def delete_employee(db: Session, employee_id: int, current_user: User) -> bool:
    """
    Soft delete employee (sets is_active = False)
    SECURITY: Admins only

    Args:
        db: Database session
        employee_id: Employee ID to delete
        current_user: Authenticated user

    Returns:
        True if soft deleted

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 404: If employee not found
    """
    # SECURITY: Only admins can delete employees
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete employees")

    db_employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()

    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Soft delete - preserves data integrity
    return soft_delete(db, db_employee)
