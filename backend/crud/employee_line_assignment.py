"""
CRUD operations for Employee Line Assignments.
Enforces allocation rules: max 2 active lines per employee, total <= 100%.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, or_, func as sqlfunc
from typing import List, Optional
from datetime import date
from decimal import Decimal

from backend.orm.employee_line_assignment import EmployeeLineAssignment
from backend.orm.employee import Employee
from backend.schemas.employee_line_assignment import (
    EmployeeLineAssignmentCreate,
    EmployeeLineAssignmentUpdate,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

MAX_ACTIVE_ASSIGNMENTS = 2
MAX_ALLOCATION_PERCENTAGE = Decimal("100.00")


def _active_filter():
    """
    SQLAlchemy filter clause for active assignments.
    Active means: end_date IS NULL or end_date > today.
    """
    today = date.today()
    return or_(
        EmployeeLineAssignment.end_date.is_(None),
        EmployeeLineAssignment.end_date > today,
    )


def _get_active_assignments(db: Session, employee_id: int) -> List[EmployeeLineAssignment]:
    """Get all active assignments for an employee."""
    return (
        db.query(EmployeeLineAssignment)
        .filter(
            EmployeeLineAssignment.employee_id == employee_id,
            _active_filter(),
        )
        .all()
    )


def validate_allocation(
    db: Session,
    employee_id: int,
    exclude_assignment_id: Optional[int] = None,
) -> Decimal:
    """
    Calculate total allocation percentage for an employee's active assignments.

    Args:
        db: Database session.
        employee_id: The employee to check.
        exclude_assignment_id: Assignment to exclude (for update scenarios).

    Returns:
        Total allocation percentage as Decimal.
    """
    query = db.query(
        sqlfunc.coalesce(
            sqlfunc.sum(EmployeeLineAssignment.allocation_percentage),
            Decimal("0.00"),
        )
    ).filter(
        EmployeeLineAssignment.employee_id == employee_id,
        _active_filter(),
    )

    if exclude_assignment_id is not None:
        query = query.filter(
            EmployeeLineAssignment.assignment_id != exclude_assignment_id
        )

    result = query.scalar()
    return Decimal(str(result)) if result is not None else Decimal("0.00")


def create_assignment(
    db: Session,
    data: EmployeeLineAssignmentCreate,
) -> EmployeeLineAssignment:
    """
    Create a new employee-to-line assignment.

    Business Rules:
    1. Employee must exist and be active.
    2. Max 2 active assignments per employee.
    3. Total allocation (existing + new) must not exceed 100%.
    4. First assignment is forced to is_primary=True.
    5. If second assignment requests is_primary=True, the existing primary is demoted.

    Args:
        db: Database session.
        data: Assignment creation payload.

    Returns:
        The newly created EmployeeLineAssignment ORM object.

    Raises:
        ValueError: If business rule validation fails.
    """
    # 1. Verify employee exists and is active
    employee = (
        db.query(Employee)
        .filter(Employee.employee_id == data.employee_id)
        .first()
    )
    if not employee:
        raise ValueError(f"Employee with id {data.employee_id} not found")
    if not employee.is_active:
        raise ValueError(f"Employee with id {data.employee_id} is not active")

    # 2. Count active assignments
    active_assignments = _get_active_assignments(db, data.employee_id)
    active_count = len(active_assignments)

    if active_count >= MAX_ACTIVE_ASSIGNMENTS:
        raise ValueError(
            f"Maximum {MAX_ACTIVE_ASSIGNMENTS} line assignments per employee"
        )

    # 3. Validate allocation total
    existing_total = sum(
        Decimal(str(a.allocation_percentage)) for a in active_assignments
    )
    new_total = existing_total + data.allocation_percentage

    if new_total > MAX_ALLOCATION_PERCENTAGE:
        raise ValueError(
            f"Total allocation cannot exceed 100%. "
            f"Current: {existing_total}%, requested: {data.allocation_percentage}%, "
            f"total would be: {new_total}%"
        )

    # 4. First assignment is always primary
    is_primary = data.is_primary
    if active_count == 0:
        is_primary = True

    # 5. If this is the second assignment and is_primary=True, demote existing primary
    if active_count == 1 and is_primary:
        for existing in active_assignments:
            if existing.is_primary:
                existing.is_primary = False
                logger.info(
                    "Demoted existing primary assignment_id=%d for employee_id=%d",
                    existing.assignment_id,
                    data.employee_id,
                )

    db_entry = EmployeeLineAssignment(
        employee_id=data.employee_id,
        line_id=data.line_id,
        client_id=data.client_id,
        allocation_percentage=data.allocation_percentage,
        is_primary=is_primary,
        effective_date=data.effective_date,
        end_date=data.end_date,
    )

    try:
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Duplicate assignment: employee {data.employee_id} "
            f"to line {data.line_id} on {data.effective_date}"
        )

    logger.info(
        "Created line assignment: employee_id=%d, line_id=%d, allocation=%s%%, client=%s",
        data.employee_id,
        data.line_id,
        data.allocation_percentage,
        data.client_id,
    )
    return db_entry


def list_assignments(
    db: Session,
    employee_id: Optional[int] = None,
    line_id: Optional[int] = None,
    client_id: Optional[str] = None,
    active_only: bool = True,
) -> List[EmployeeLineAssignment]:
    """
    List employee line assignments with optional filters.

    Args:
        db: Database session.
        employee_id: Filter by employee.
        line_id: Filter by production line.
        client_id: Filter by client.
        active_only: If True, only return active assignments (end_date IS NULL or > today).

    Returns:
        List of EmployeeLineAssignment ORM objects.
    """
    query = db.query(EmployeeLineAssignment)

    if employee_id is not None:
        query = query.filter(EmployeeLineAssignment.employee_id == employee_id)
    if line_id is not None:
        query = query.filter(EmployeeLineAssignment.line_id == line_id)
    if client_id is not None:
        query = query.filter(EmployeeLineAssignment.client_id == client_id)
    if active_only:
        query = query.filter(_active_filter())

    return query.order_by(EmployeeLineAssignment.effective_date.desc()).all()


def get_assignment(
    db: Session,
    assignment_id: int,
) -> Optional[EmployeeLineAssignment]:
    """
    Get a single assignment by ID.

    Args:
        db: Database session.
        assignment_id: Primary key.

    Returns:
        EmployeeLineAssignment or None.
    """
    return (
        db.query(EmployeeLineAssignment)
        .filter(EmployeeLineAssignment.assignment_id == assignment_id)
        .first()
    )


def get_employee_lines(
    db: Session,
    employee_id: int,
) -> List[EmployeeLineAssignment]:
    """
    Get active line assignments for an employee.
    Useful for My Shift views.

    Args:
        db: Database session.
        employee_id: Employee to look up.

    Returns:
        List of active EmployeeLineAssignment objects.
    """
    return (
        db.query(EmployeeLineAssignment)
        .filter(
            EmployeeLineAssignment.employee_id == employee_id,
            _active_filter(),
        )
        .order_by(EmployeeLineAssignment.is_primary.desc())
        .all()
    )


def get_line_employees(
    db: Session,
    line_id: int,
    client_id: str,
) -> List[EmployeeLineAssignment]:
    """
    Get active employees assigned to a production line.
    Useful for line roster views.

    Args:
        db: Database session.
        line_id: Production line to query.
        client_id: Client for tenant isolation.

    Returns:
        List of active EmployeeLineAssignment objects for the line.
    """
    return (
        db.query(EmployeeLineAssignment)
        .filter(
            EmployeeLineAssignment.line_id == line_id,
            EmployeeLineAssignment.client_id == client_id,
            _active_filter(),
        )
        .order_by(EmployeeLineAssignment.is_primary.desc())
        .all()
    )


def update_assignment(
    db: Session,
    assignment_id: int,
    data: EmployeeLineAssignmentUpdate,
) -> Optional[EmployeeLineAssignment]:
    """
    Partial update of an employee line assignment.
    Re-validates allocation total if percentage changes.

    Args:
        db: Database session.
        assignment_id: PK of assignment to update.
        data: Fields to update (only non-None fields applied).

    Returns:
        Updated EmployeeLineAssignment or None if not found.

    Raises:
        ValueError: If allocation total would exceed 100%.
    """
    db_entry = (
        db.query(EmployeeLineAssignment)
        .filter(EmployeeLineAssignment.assignment_id == assignment_id)
        .first()
    )
    if not db_entry:
        return None

    update_fields = data.model_dump(exclude_unset=True)

    # Re-validate allocation if percentage is being changed
    if "allocation_percentage" in update_fields:
        new_pct = update_fields["allocation_percentage"]
        existing_total = validate_allocation(
            db, db_entry.employee_id, exclude_assignment_id=assignment_id
        )
        proposed_total = existing_total + new_pct
        if proposed_total > MAX_ALLOCATION_PERCENTAGE:
            raise ValueError(
                f"Total allocation cannot exceed 100%. "
                f"Other assignments: {existing_total}%, "
                f"proposed: {new_pct}%, total would be: {proposed_total}%"
            )

    for field, value in update_fields.items():
        setattr(db_entry, field, value)

    db.commit()
    db.refresh(db_entry)
    logger.info("Updated line assignment assignment_id=%d", assignment_id)
    return db_entry


def end_assignment(
    db: Session,
    assignment_id: int,
    end_date_value: Optional[date] = None,
) -> Optional[EmployeeLineAssignment]:
    """
    End an assignment by setting its end_date. Does NOT delete the row.

    Args:
        db: Database session.
        assignment_id: PK of assignment to end.
        end_date_value: The end date to set (defaults to today).

    Returns:
        Updated EmployeeLineAssignment or None if not found.
    """
    db_entry = (
        db.query(EmployeeLineAssignment)
        .filter(EmployeeLineAssignment.assignment_id == assignment_id)
        .first()
    )
    if not db_entry:
        return None

    db_entry.end_date = end_date_value or date.today()
    db.commit()
    db.refresh(db_entry)
    logger.info(
        "Ended line assignment assignment_id=%d, end_date=%s",
        assignment_id,
        db_entry.end_date,
    )
    return db_entry
