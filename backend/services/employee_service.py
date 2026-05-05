"""
Employee Service
Thin service layer wrapping Employee CRUD operations.
Routes should import from this module instead of backend.crud.employee directly.
"""

from typing import Any, Optional
from sqlalchemy.orm import Session

from backend.orm.user import User
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


def create_employee_record(db: Session, employee_data: dict, current_user: User) -> Any:
    """Create a new employee record."""
    return create_employee(db, employee_data, current_user)


def get_employee_by_id(db: Session, employee_id: int, current_user: User) -> Any:
    """Get employee by ID with access control."""
    return get_employee(db, employee_id, current_user)


def list_employees(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[str] = None,
    is_floating_pool: Optional[bool] = None,
) -> Any:
    """List employees with optional filters."""
    return get_employees(db, current_user, skip, limit, client_id, is_floating_pool)


def update_employee_record(db: Session, employee_id: int, employee_data: dict, current_user: User) -> Any:
    """Update an employee record."""
    return update_employee(db, employee_id, employee_data, current_user)


def delete_employee_record(db: Session, employee_id: int, current_user: User) -> bool:
    """Delete (soft) an employee record."""
    return delete_employee(db, employee_id, current_user)


def list_employees_by_client(db: Session, client_id: str, current_user: User, skip: int = 0, limit: int = 100) -> Any:
    """Get all employees assigned to a specific client."""
    return get_employees_by_client(db, client_id, current_user, skip, limit)


def list_floating_pool_employees(db: Session, current_user: User, skip: int = 0, limit: int = 100) -> Any:
    """Get all floating pool employees."""
    return get_floating_pool_employees(db, current_user, skip, limit)


def assign_employee_to_pool(db: Session, employee_id: int, current_user: User) -> Any:
    """Assign an employee to the floating pool."""
    return assign_to_floating_pool(db, employee_id, current_user)


def remove_employee_from_pool(db: Session, employee_id: int, current_user: User) -> Any:
    """Remove an employee from the floating pool."""
    return remove_from_floating_pool(db, employee_id, current_user)


def assign_employee_client(db: Session, employee_id: int, client_id: str, current_user: User) -> Any:
    """Assign an employee to a client."""
    return assign_employee_to_client(db, employee_id, client_id, current_user)
