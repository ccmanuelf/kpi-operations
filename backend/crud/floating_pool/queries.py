"""
CRUD query operations for Floating Pool
List, filter, and summary queries
SECURITY: Multi-tenant client filtering enabled
"""

from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.schemas.floating_pool import FloatingPool
from backend.schemas.employee import Employee
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.crud.floating_pool.assignments import is_employee_available_for_assignment


def get_floating_pool_entries(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    employee_id: Optional[int] = None,
    available_only: bool = False,
) -> List[FloatingPool]:
    """
    Get floating pool entries with filtering

    Args:
        db: Database session
        current_user: Authenticated user
        skip: Number of records to skip
        limit: Maximum records to return
        employee_id: Filter by employee
        available_only: Filter to only available (unassigned) entries

    Returns:
        List of floating pool entries
    """
    query = db.query(FloatingPool)

    # Apply filters
    if employee_id:
        query = query.filter(FloatingPool.employee_id == employee_id)

    if available_only:
        query = query.filter(FloatingPool.current_assignment.is_(None))

    return query.order_by(FloatingPool.created_at.desc()).offset(skip).limit(limit).all()


def get_available_floating_pool_employees(
    db: Session, current_user: User, as_of_date: Optional[datetime] = None
) -> List[dict]:
    """
    Get all currently available floating pool employees

    Args:
        db: Database session
        current_user: Authenticated user
        as_of_date: Date to check availability (defaults to now)

    Returns:
        List of available employees with their details
    """
    if as_of_date is None:
        as_of_date = datetime.now(tz=timezone.utc)

    # Get unassigned floating pool entries
    available_entries = db.query(FloatingPool).filter(FloatingPool.current_assignment.is_(None)).all()

    # Get employee details
    result = []
    for entry in available_entries:
        employee = db.query(Employee).filter(Employee.employee_id == entry.employee_id).first()

        if employee:
            result.append(
                {
                    "pool_id": entry.pool_id,
                    "employee_id": employee.employee_id,
                    "employee_code": employee.employee_code,
                    "employee_name": employee.employee_name,
                    "position": employee.position,
                    "available_from": entry.available_from,
                    "available_to": entry.available_to,
                    "notes": entry.notes,
                }
            )

    return result


def get_floating_pool_assignments_by_client(
    db: Session, client_id: str, current_user: User, skip: int = 0, limit: int = 100
) -> List[FloatingPool]:
    """
    Get all floating pool assignments for a specific client
    SECURITY: Verifies user has access to the client

    Args:
        db: Database session
        client_id: Client ID
        current_user: Authenticated user
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        List of floating pool assignments for the client

    Raises:
        HTTPException 403: If user doesn't have access to client
    """
    # SECURITY: Verify user has access to this client
    verify_client_access(current_user, client_id)

    return (
        db.query(FloatingPool)
        .filter(FloatingPool.current_assignment == client_id)
        .order_by(FloatingPool.available_from.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_floating_pool_summary(db: Session, current_user: User) -> dict:
    """
    Get summary statistics for floating pool
    Useful for dashboard widgets

    Args:
        db: Database session
        current_user: Authenticated user

    Returns:
        Dictionary with floating pool statistics
    """
    # Get all floating pool employees
    floating_employees = db.query(Employee).filter(Employee.is_floating_pool == True).all()

    total_floating = len(floating_employees)

    # Count currently assigned
    assigned_count = (
        db.query(FloatingPool)
        .filter(FloatingPool.current_assignment.isnot(None))
        .distinct(FloatingPool.employee_id)
        .count()
    )

    # Get available employees
    available_employees = []
    for emp in floating_employees:
        availability = is_employee_available_for_assignment(db, emp.employee_id)
        if availability["is_available"]:
            available_employees.append(
                {
                    "employee_id": emp.employee_id,
                    "employee_code": emp.employee_code,
                    "employee_name": emp.employee_name,
                    "position": emp.position,
                }
            )

    return {
        "total_floating_pool_employees": total_floating,
        "currently_available": len(available_employees),
        "currently_assigned": assigned_count,
        "available_employees": available_employees,
    }
