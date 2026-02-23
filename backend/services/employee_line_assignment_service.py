"""
Employee Line Assignment Service
Thin service layer wrapping Employee Line Assignment CRUD operations.
Routes should import from this module instead of backend.crud.employee_line_assignment directly.
"""

from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session

from backend.crud.employee_line_assignment import (
    create_assignment,
    list_assignments,
    get_assignment,
    get_employee_lines,
    get_line_employees,
    update_assignment,
    end_assignment,
)


def create_line_assignment(db: Session, data):
    """Create a new employee line assignment."""
    return create_assignment(db, data)


def list_line_assignments(
    db: Session,
    employee_id: Optional[int] = None,
    line_id: Optional[int] = None,
    client_id: Optional[str] = None,
    active_only: bool = True,
):
    """List employee line assignments with filters."""
    return list_assignments(db, employee_id, line_id, client_id, active_only)


def get_line_assignment(db: Session, assignment_id: int):
    """Get an assignment by ID."""
    return get_assignment(db, assignment_id)


def get_lines_for_employee(db: Session, employee_id: int):
    """Get production lines assigned to an employee."""
    return get_employee_lines(db, employee_id)


def get_employees_for_line(db: Session, line_id: int, client_id: str = None):
    """Get employees assigned to a production line."""
    return get_line_employees(db, line_id, client_id)


def update_line_assignment(db: Session, assignment_id: int, data: dict):
    """Update an employee line assignment."""
    return update_assignment(db, assignment_id, data)


def end_line_assignment(db: Session, assignment_id: int):
    """End an employee line assignment."""
    return end_assignment(db, assignment_id)
