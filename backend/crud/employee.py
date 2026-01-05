"""
CRUD operations for Employee
Create, Read, Update, Delete with multi-tenant security and floating pool management
SECURITY: Multi-tenant client filtering enabled
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.schemas.employee import Employee
from backend.schemas.user import User
from middleware.client_auth import verify_client_access


def create_employee(
    db: Session,
    employee_data: dict,
    current_user: User
) -> Employee:
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
    if current_user.role not in ['admin', 'supervisor']:
        raise HTTPException(
            status_code=403,
            detail="Only supervisors and admins can create employees"
        )

    # Check if employee_code already exists
    existing = db.query(Employee).filter(
        Employee.employee_code == employee_data.get('employee_code')
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Employee with code {employee_data.get('employee_code')} already exists"
        )

    # Create employee
    db_employee = Employee(**employee_data)

    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)

    return db_employee


def get_employee(
    db: Session,
    employee_id: int,
    current_user: User
) -> Optional[Employee]:
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
    """
    employee = db.query(Employee).filter(
        Employee.employee_id == employee_id
    ).first()

    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    return employee


def get_employees(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[str] = None,
    is_floating_pool: Optional[bool] = None
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

    # Apply filters
    if client_id:
        # Filter employees assigned to specific client
        query = query.filter(Employee.client_id_assigned.like(f"%{client_id}%"))

    if is_floating_pool is not None:
        query = query.filter(Employee.is_floating_pool == (1 if is_floating_pool else 0))

    return query.order_by(
        Employee.employee_name
    ).offset(skip).limit(limit).all()


def update_employee(
    db: Session,
    employee_id: int,
    employee_update: dict,
    current_user: User
) -> Optional[Employee]:
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
    if current_user.role not in ['admin', 'supervisor']:
        raise HTTPException(
            status_code=403,
            detail="Only supervisors and admins can update employees"
        )

    db_employee = db.query(Employee).filter(
        Employee.employee_id == employee_id
    ).first()

    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Update fields
    for field, value in employee_update.items():
        if hasattr(db_employee, field):
            setattr(db_employee, field, value)

    db.commit()
    db.refresh(db_employee)

    return db_employee


def delete_employee(
    db: Session,
    employee_id: int,
    current_user: User
) -> bool:
    """
    Delete employee
    SECURITY: Admins only

    Args:
        db: Database session
        employee_id: Employee ID to delete
        current_user: Authenticated user

    Returns:
        True if deleted

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 404: If employee not found
    """
    # SECURITY: Only admins can delete employees
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=403,
            detail="Only admins can delete employees"
        )

    db_employee = db.query(Employee).filter(
        Employee.employee_id == employee_id
    ).first()

    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    db.delete(db_employee)
    db.commit()

    return True


def get_employees_by_client(
    db: Session,
    client_id: str,
    current_user: User,
    skip: int = 0,
    limit: int = 100
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

    return db.query(Employee).filter(
        Employee.client_id_assigned.like(f"%{client_id}%")
    ).order_by(
        Employee.employee_name
    ).offset(skip).limit(limit).all()


def get_floating_pool_employees(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100
) -> List[Employee]:
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
    return db.query(Employee).filter(
        Employee.is_floating_pool == 1
    ).order_by(
        Employee.employee_name
    ).offset(skip).limit(limit).all()


def assign_to_floating_pool(
    db: Session,
    employee_id: int,
    current_user: User
) -> Employee:
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
    if current_user.role not in ['admin', 'supervisor']:
        raise HTTPException(
            status_code=403,
            detail="Only supervisors and admins can assign to floating pool"
        )

    db_employee = db.query(Employee).filter(
        Employee.employee_id == employee_id
    ).first()

    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    db_employee.is_floating_pool = 1
    db.commit()
    db.refresh(db_employee)

    return db_employee


def remove_from_floating_pool(
    db: Session,
    employee_id: int,
    current_user: User
) -> Employee:
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
    if current_user.role not in ['admin', 'supervisor']:
        raise HTTPException(
            status_code=403,
            detail="Only supervisors and admins can remove from floating pool"
        )

    db_employee = db.query(Employee).filter(
        Employee.employee_id == employee_id
    ).first()

    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    db_employee.is_floating_pool = 0
    db.commit()
    db.refresh(db_employee)

    return db_employee


def assign_employee_to_client(
    db: Session,
    employee_id: int,
    client_id: str,
    current_user: User
) -> Employee:
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
    if current_user.role not in ['admin', 'supervisor']:
        raise HTTPException(
            status_code=403,
            detail="Only supervisors and admins can assign employees to clients"
        )

    # SECURITY: Verify user has access to this client
    verify_client_access(current_user, client_id)

    db_employee = db.query(Employee).filter(
        Employee.employee_id == employee_id
    ).first()

    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Add client to assignment list (comma-separated)
    current_assignments = db_employee.client_id_assigned or ""
    if client_id not in current_assignments.split(','):
        if current_assignments:
            db_employee.client_id_assigned = f"{current_assignments},{client_id}"
        else:
            db_employee.client_id_assigned = client_id

    db.commit()
    db.refresh(db_employee)

    return db_employee
