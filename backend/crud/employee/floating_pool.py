"""
CRUD operations for Employee Floating Pool membership
Manage floating pool status for employees
SECURITY: Role-based access control
"""

from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.schemas.employee import Employee
from backend.schemas.user import User


def get_floating_pool_employees(db: Session, current_user: User, skip: int = 0, limit: int = 100) -> List[Employee]:
    """
    Get all floating pool employees

    Args:
        db: Database session
        current_user: Authenticated user
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        List of floating pool employees
    """
    return (
        db.query(Employee)
        .filter(Employee.is_floating_pool == 1)
        .order_by(Employee.employee_name)
        .offset(skip)
        .limit(limit)
        .all()
    )


def assign_to_floating_pool(db: Session, employee_id: int, current_user: User) -> Employee:
    """
    Assign employee to floating pool
    SECURITY: Supervisors and admins only

    Args:
        db: Database session
        employee_id: Employee ID
        current_user: Authenticated user

    Returns:
        Updated employee

    Raises:
        HTTPException 403: If user doesn't have permission
        HTTPException 404: If employee not found
    """
    # SECURITY: Only supervisors and admins can assign to floating pool
    if current_user.role not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="Only supervisors and admins can assign to floating pool")

    db_employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()

    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    db_employee.is_floating_pool = 1
    db.commit()
    db.refresh(db_employee)

    return db_employee


def remove_from_floating_pool(db: Session, employee_id: int, current_user: User) -> Employee:
    """
    Remove employee from floating pool
    SECURITY: Supervisors and admins only

    Args:
        db: Database session
        employee_id: Employee ID
        current_user: Authenticated user

    Returns:
        Updated employee

    Raises:
        HTTPException 403: If user doesn't have permission
        HTTPException 404: If employee not found
    """
    # SECURITY: Only supervisors and admins can remove from floating pool
    if current_user.role not in ["admin", "supervisor"]:
        raise HTTPException(status_code=403, detail="Only supervisors and admins can remove from floating pool")

    db_employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()

    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    db_employee.is_floating_pool = 0
    db.commit()
    db.refresh(db_employee)

    return db_employee
