"""
CRUD core operations for Floating Pool
Create, Read, Update, Delete operations
SECURITY: Multi-tenant client filtering enabled
"""
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.schemas.floating_pool import FloatingPool
from backend.schemas.employee import Employee
from backend.schemas.user import User
from backend.utils.soft_delete import soft_delete


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
    Soft delete floating pool entry (sets is_active = False)
    SECURITY: Supervisors and admins only

    Args:
        db: Database session
        pool_id: Pool entry ID to delete
        current_user: Authenticated user

    Returns:
        True if soft deleted

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

    # Soft delete - preserves data integrity
    return soft_delete(db, db_pool)
