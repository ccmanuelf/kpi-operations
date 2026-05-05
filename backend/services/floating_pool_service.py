"""
Floating Pool Service
Thin service layer wrapping Floating Pool CRUD operations.
Routes should import from this module instead of backend.crud.floating_pool directly.
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from backend.crud.floating_pool import (
    assign_floating_pool_to_client,
    create_floating_pool_entry,
    delete_floating_pool_entry,
    get_available_floating_pool_employees,
    get_floating_pool_assignments_by_client,
    get_floating_pool_entries,
    get_floating_pool_entry,
    get_floating_pool_summary,
    is_employee_available_for_assignment,
    unassign_floating_pool_from_client,
    update_floating_pool_entry,
)
from backend.orm.user import User


def create_pool_entry(db: Session, pool_data: dict, current_user: User) -> Any:
    """Create a new floating pool entry."""
    return create_floating_pool_entry(db, pool_data, current_user)


def get_pool_entry(db: Session, pool_id: int, current_user: User) -> Any:
    """Get a floating pool entry by ID."""
    return get_floating_pool_entry(db, pool_id, current_user)


def list_pool_entries(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    employee_id: Optional[int] = None,
    available_only: bool = False,
) -> Any:
    """List floating pool entries."""
    return get_floating_pool_entries(db, current_user, skip, limit, employee_id, available_only)


def update_pool_entry(db: Session, pool_id: int, pool_data: dict, current_user: User) -> Any:
    """Update a floating pool entry."""
    return update_floating_pool_entry(db, pool_id, pool_data, current_user)


def delete_pool_entry(db: Session, pool_id: int, current_user: User) -> bool:
    """Delete a floating pool entry."""
    return delete_floating_pool_entry(db, pool_id, current_user)


def assign_to_client(
    db: Session,
    employee_id: int,
    client_id: str,
    available_from: Optional[datetime],
    available_to: Optional[datetime],
    current_user: User,
    notes: Optional[str] = None,
) -> Any:
    """Assign a floating pool employee to a client.

    Forwards directly to the CRUD layer which takes individual fields rather
    than a packed dict; the previous (db, pool_id, dict, user) signature was
    a mismatch with crud.assign_floating_pool_to_client and would have failed
    at runtime.
    """
    return assign_floating_pool_to_client(db, employee_id, client_id, available_from, available_to, current_user, notes)


def unassign_from_client(db: Session, pool_id: int, current_user: User) -> Any:
    """Unassign a floating pool employee from a client."""
    return unassign_floating_pool_from_client(db, pool_id, current_user)


def list_available_employees(db: Session, current_user: User, as_of_date: Optional[datetime] = None) -> Any:
    """Get available floating pool employees."""
    return get_available_floating_pool_employees(db, current_user, as_of_date)


def list_client_assignments(db: Session, client_id: str, current_user: User, skip: int = 0, limit: int = 100) -> Any:
    """Get floating pool assignments for a client."""
    return get_floating_pool_assignments_by_client(db, client_id, current_user, skip, limit)


def check_employee_availability(
    db: Session,
    employee_id: int,
    proposed_start: Optional[datetime] = None,
    proposed_end: Optional[datetime] = None,
) -> Any:
    """Check if employee is available for assignment."""
    return is_employee_available_for_assignment(db, employee_id, proposed_start, proposed_end)


def get_pool_summary(db: Session, current_user: User) -> dict:
    """Get floating pool summary."""
    return get_floating_pool_summary(db, current_user)
