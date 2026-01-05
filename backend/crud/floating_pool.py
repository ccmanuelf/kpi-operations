"""
CRUD operations for Floating Pool
Manage shared resource availability and assignments
SECURITY: Multi-tenant client filtering enabled
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.schemas.floating_pool import FloatingPool
from backend.schemas.employee import Employee
from backend.schemas.user import User
from middleware.client_auth import verify_client_access


def create_floating_pool_entry(
    db: Session,
    pool_data: dict,
    current_user: User
) -> FloatingPool:
    """
    Create new floating pool availability entry
    SECURITY: Supervisors and admins only

    Args:
        db: Database session
        pool_data: Floating pool data dictionary
        current_user: Authenticated user

    Returns:
        Created floating pool entry

    Raises:
        HTTPException 403: If user doesn't have permission
        HTTPException 404: If employee not found or not in floating pool
    """
    # SECURITY: Only supervisors and admins can manage floating pool
    if current_user.role not in ['admin', 'supervisor']:
        raise HTTPException(
            status_code=403,
            detail="Only supervisors and admins can manage floating pool"
        )

    # Verify employee exists and is in floating pool
    employee = db.query(Employee).filter(
        Employee.employee_id == pool_data.get('employee_id')
    ).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if not employee.is_floating_pool:
        raise HTTPException(
            status_code=400,
            detail="Employee is not in floating pool"
        )

    # Create floating pool entry
    db_pool = FloatingPool(**pool_data)

    db.add(db_pool)
    db.commit()
    db.refresh(db_pool)

    return db_pool


def get_floating_pool_entry(
    db: Session,
    pool_id: int,
    current_user: User
) -> Optional[FloatingPool]:
    """
    Get floating pool entry by ID

    Args:
        db: Database session
        pool_id: Pool entry ID
        current_user: Authenticated user

    Returns:
        Floating pool entry or None if not found

    Raises:
        HTTPException 404: If pool entry not found
    """
    pool_entry = db.query(FloatingPool).filter(
        FloatingPool.pool_id == pool_id
    ).first()

    if not pool_entry:
        raise HTTPException(status_code=404, detail="Floating pool entry not found")

    return pool_entry


def get_floating_pool_entries(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    employee_id: Optional[int] = None,
    available_only: bool = False
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

    return query.order_by(
        FloatingPool.created_at.desc()
    ).offset(skip).limit(limit).all()


def update_floating_pool_entry(
    db: Session,
    pool_id: int,
    pool_update: dict,
    current_user: User
) -> Optional[FloatingPool]:
    """
    Update floating pool entry
    SECURITY: Supervisors and admins only

    Args:
        db: Database session
        pool_id: Pool entry ID to update
        pool_update: Update data dictionary
        current_user: Authenticated user

    Returns:
        Updated floating pool entry or None if not found

    Raises:
        HTTPException 403: If user doesn't have permission
        HTTPException 404: If pool entry not found
    """
    # SECURITY: Only supervisors and admins can manage floating pool
    if current_user.role not in ['admin', 'supervisor']:
        raise HTTPException(
            status_code=403,
            detail="Only supervisors and admins can manage floating pool"
        )

    db_pool = db.query(FloatingPool).filter(
        FloatingPool.pool_id == pool_id
    ).first()

    if not db_pool:
        raise HTTPException(status_code=404, detail="Floating pool entry not found")

    # Update fields
    for field, value in pool_update.items():
        if hasattr(db_pool, field):
            setattr(db_pool, field, value)

    db.commit()
    db.refresh(db_pool)

    return db_pool


def delete_floating_pool_entry(
    db: Session,
    pool_id: int,
    current_user: User
) -> bool:
    """
    Delete floating pool entry
    SECURITY: Supervisors and admins only

    Args:
        db: Database session
        pool_id: Pool entry ID to delete
        current_user: Authenticated user

    Returns:
        True if deleted

    Raises:
        HTTPException 403: If user doesn't have permission
        HTTPException 404: If pool entry not found
    """
    # SECURITY: Only supervisors and admins can manage floating pool
    if current_user.role not in ['admin', 'supervisor']:
        raise HTTPException(
            status_code=403,
            detail="Only supervisors and admins can manage floating pool"
        )

    db_pool = db.query(FloatingPool).filter(
        FloatingPool.pool_id == pool_id
    ).first()

    if not db_pool:
        raise HTTPException(status_code=404, detail="Floating pool entry not found")

    db.delete(db_pool)
    db.commit()

    return True


def assign_floating_pool_to_client(
    db: Session,
    employee_id: int,
    client_id: str,
    available_from: Optional[datetime],
    available_to: Optional[datetime],
    current_user: User,
    notes: Optional[str] = None
) -> FloatingPool:
    """
    Assign a floating pool employee to a client
    SECURITY: Supervisors and admins only, verifies client access

    Args:
        db: Database session
        employee_id: Employee ID (must be in floating pool)
        client_id: Client ID to assign to
        available_from: Start date of assignment
        available_to: End date of assignment
        current_user: Authenticated user
        notes: Optional assignment notes

    Returns:
        Created/updated floating pool entry

    Raises:
        HTTPException 403: If user doesn't have permission or client access
        HTTPException 404: If employee not found
        HTTPException 400: If employee not in floating pool
    """
    # SECURITY: Only supervisors and admins can assign floating pool
    if current_user.role not in ['admin', 'supervisor']:
        raise HTTPException(
            status_code=403,
            detail="Only supervisors and admins can assign floating pool employees"
        )

    # SECURITY: Verify user has access to this client
    verify_client_access(current_user, client_id)

    # Verify employee exists and is in floating pool
    employee = db.query(Employee).filter(
        Employee.employee_id == employee_id
    ).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    if not employee.is_floating_pool:
        raise HTTPException(
            status_code=400,
            detail="Employee is not in floating pool"
        )

    # Create assignment entry
    pool_entry = FloatingPool(
        employee_id=employee_id,
        current_assignment=client_id,
        available_from=available_from,
        available_to=available_to,
        notes=notes
    )

    db.add(pool_entry)
    db.commit()
    db.refresh(pool_entry)

    return pool_entry


def unassign_floating_pool_from_client(
    db: Session,
    pool_id: int,
    current_user: User
) -> FloatingPool:
    """
    Unassign a floating pool employee from their current client
    SECURITY: Supervisors and admins only

    Args:
        db: Database session
        pool_id: Floating pool entry ID
        current_user: Authenticated user

    Returns:
        Updated floating pool entry

    Raises:
        HTTPException 403: If user doesn't have permission
        HTTPException 404: If pool entry not found
    """
    # SECURITY: Only supervisors and admins can unassign floating pool
    if current_user.role not in ['admin', 'supervisor']:
        raise HTTPException(
            status_code=403,
            detail="Only supervisors and admins can unassign floating pool employees"
        )

    db_pool = db.query(FloatingPool).filter(
        FloatingPool.pool_id == pool_id
    ).first()

    if not db_pool:
        raise HTTPException(status_code=404, detail="Floating pool entry not found")

    # Clear assignment
    db_pool.current_assignment = None
    db_pool.available_to = datetime.utcnow()

    db.commit()
    db.refresh(db_pool)

    return db_pool


def get_available_floating_pool_employees(
    db: Session,
    current_user: User,
    as_of_date: Optional[datetime] = None
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
        as_of_date = datetime.utcnow()

    # Get unassigned floating pool entries
    available_entries = db.query(FloatingPool).filter(
        FloatingPool.current_assignment.is_(None)
    ).all()

    # Get employee details
    result = []
    for entry in available_entries:
        employee = db.query(Employee).filter(
            Employee.employee_id == entry.employee_id
        ).first()

        if employee:
            result.append({
                "pool_id": entry.pool_id,
                "employee_id": employee.employee_id,
                "employee_code": employee.employee_code,
                "employee_name": employee.employee_name,
                "position": employee.position,
                "available_from": entry.available_from,
                "available_to": entry.available_to,
                "notes": entry.notes
            })

    return result


def get_floating_pool_assignments_by_client(
    db: Session,
    client_id: str,
    current_user: User,
    skip: int = 0,
    limit: int = 100
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

    return db.query(FloatingPool).filter(
        FloatingPool.current_assignment == client_id
    ).order_by(
        FloatingPool.available_from.desc()
    ).offset(skip).limit(limit).all()
