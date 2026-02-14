"""
CRUD operations for Employee Client Assignment
Manage employee assignments to clients
SECURITY: Multi-tenant client filtering enabled
"""

from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.schemas.employee import Employee
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access


def get_employees_by_client(
    db: Session, client_id: str, current_user: User, skip: int = 0, limit: int = 100
) -> List[Employee]:
    """
    Get all employees assigned to a specific client
    SECURITY: Verifies user has access to the client

    Args:
        db: Database session
        client_id: Client ID
        current_user: Authenticated user
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        List of employees assigned to the client

    Raises:
        HTTPException 403: If user doesn't have access to client
    """
    # SECURITY: Verify user has access to this client
    verify_client_access(current_user, client_id)

    return (
        db.query(Employee)
        .filter(Employee.client_id_assigned.like(f"%{client_id}%"))
        .order_by(Employee.employee_name)
        .offset(skip)
        .limit(limit)
        .all()
    )


def assign_employee_to_client(db: Session, employee_id: int, client_id: str, current_user: User) -> Employee:
    """
    Assign employee to a client
    SECURITY: Supervisors and admins only, verifies client access

    Args:
        db: Database session
        employee_id: Employee ID
        client_id: Client ID to assign to
        current_user: Authenticated user

    Returns:
        Updated employee

    Raises:
        HTTPException 403: If user doesn't have permission or client access
        HTTPException 404: If employee not found
    """
    # SECURITY: Only supervisors and admins can assign employees
    if current_user.role not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="Only supervisors and admins can assign employees to clients")

    # SECURITY: Verify user has access to this client
    verify_client_access(current_user, client_id)

    db_employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()

    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Add client to assignment list (comma-separated)
    current_assignments = db_employee.client_id_assigned or ""
    if client_id not in current_assignments.split(","):
        if current_assignments:
            db_employee.client_id_assigned = f"{current_assignments},{client_id}"
        else:
            db_employee.client_id_assigned = client_id

    db.commit()
    db.refresh(db_employee)

    return db_employee
