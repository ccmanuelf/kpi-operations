"""
EMPLOYEE_CLIENT_ASSIGNMENT Junction Table ORM Schema
Phase 2.1: Data Layer Normalization

Replaces comma-separated client_id_assigned field with proper junction table.
Provides normalized employee-to-client relationship with assignment type support.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Index, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.database import Base
import enum


class AssignmentType(str, enum.Enum):
    """Type of employee assignment to a client."""

    DEDICATED = "DEDICATED"  # Regular employee, dedicated to one client
    FLOATING_POOL = "FLOATING"  # Floating pool employee, can serve multiple clients


class EmployeeClientAssignment(Base):
    """
    EMPLOYEE_CLIENT_ASSIGNMENT table - Junction for employee to client mapping.

    Business Rules:
    - Regular employees (is_floating_pool=0): Can only have ONE active DEDICATED assignment
    - Floating pool employees (is_floating_pool=1): Can have multiple FLOATING assignments

    This replaces the comma-separated client_id_assigned column in EMPLOYEE table.
    """

    __tablename__ = "EMPLOYEE_CLIENT_ASSIGNMENT"
    __table_args__ = (
        UniqueConstraint("employee_id", "client_id", name="uq_employee_client"),
        Index("idx_employee_client_employee", "employee_id"),
        Index("idx_employee_client_client", "client_id"),
        Index("idx_employee_client_type", "assignment_type"),
        Index("idx_employee_client_active", "is_active"),
        {"extend_existing": True},
    )

    # Primary key
    assignment_id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    employee_id = Column(Integer, ForeignKey("EMPLOYEE.employee_id", ondelete="CASCADE"), nullable=False)
    client_id = Column(String(50), ForeignKey("CLIENT.client_id", ondelete="RESTRICT"), nullable=False)

    # Assignment type
    assignment_type = Column(String(20), nullable=False, default=AssignmentType.DEDICATED.value)

    # Assignment validity period
    assigned_at = Column(DateTime, nullable=False, server_default=func.now())
    valid_from = Column(DateTime)  # When assignment becomes active
    valid_to = Column(DateTime)  # When assignment expires (optional)

    # Assignment metadata
    assigned_by = Column(String(50))  # User who made this assignment
    notes = Column(String(500))  # Optional assignment notes

    # Soft delete / deactivation
    is_active = Column(Boolean, nullable=False, default=True)
    deactivated_at = Column(DateTime)
    deactivated_by = Column(String(50))

    # Audit timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


def get_employee_assigned_clients(db, employee_id: int, active_only: bool = True):
    """
    Get all clients assigned to an employee.

    Args:
        db: Database session
        employee_id: Employee ID
        active_only: Only return active assignments

    Returns:
        List of (client_id, assignment_type) tuples
    """
    query = db.query(EmployeeClientAssignment.client_id, EmployeeClientAssignment.assignment_type).filter(
        EmployeeClientAssignment.employee_id == employee_id
    )

    if active_only:
        query = query.filter(EmployeeClientAssignment.is_active == True)

    return [(row.client_id, row.assignment_type) for row in query.all()]


def validate_employee_assignment(db, employee_id: int, client_id: str) -> tuple[bool, str]:
    """
    Validate if an employee can be assigned to a client.

    Business Rules:
    - Regular employees: Can only have ONE active assignment
    - Floating pool: Can have multiple assignments

    Args:
        db: Database session
        employee_id: Employee ID
        client_id: Client ID to assign to

    Returns:
        Tuple of (is_valid, error_message)
    """
    from backend.schemas.employee import Employee

    # Get employee
    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if not employee:
        return False, "Employee not found"

    # Get existing active assignments
    existing = (
        db.query(EmployeeClientAssignment)
        .filter(EmployeeClientAssignment.employee_id == employee_id, EmployeeClientAssignment.is_active == True)
        .all()
    )

    # If already assigned to this client, it's valid (idempotent)
    for assignment in existing:
        if assignment.client_id == client_id:
            return True, ""

    # Non-floating pool employees can only have ONE assignment
    if not employee.is_floating_pool and existing:
        current_client = existing[0].client_id
        return (
            False,
            f"Regular employee already assigned to client '{current_client}'. Remove existing assignment first.",
        )

    return True, ""


def assign_employee_to_client(
    db, employee_id: int, client_id: str, assigned_by: str, assignment_type: str = None
) -> EmployeeClientAssignment:
    """
    Assign an employee to a client.

    Args:
        db: Database session
        employee_id: Employee ID to assign
        client_id: Client ID to assign to
        assigned_by: User making the assignment
        assignment_type: DEDICATED or FLOATING (auto-detected if not provided)

    Returns:
        Created EmployeeClientAssignment

    Raises:
        ValueError: If assignment validation fails
    """
    from backend.schemas.employee import Employee

    # Validate the assignment
    is_valid, error = validate_employee_assignment(db, employee_id, client_id)
    if not is_valid:
        raise ValueError(error)

    # Auto-detect assignment type
    if assignment_type is None:
        employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
        assignment_type = (
            AssignmentType.FLOATING_POOL.value if employee.is_floating_pool else AssignmentType.DEDICATED.value
        )

    assignment = EmployeeClientAssignment(
        employee_id=employee_id, client_id=client_id, assignment_type=assignment_type, assigned_by=assigned_by
    )

    db.add(assignment)
    db.flush()

    return assignment


def remove_employee_from_client(db, employee_id: int, client_id: str, removed_by: str) -> bool:
    """
    Remove (deactivate) an employee's client assignment.

    Args:
        db: Database session
        employee_id: Employee ID
        client_id: Client ID
        removed_by: User making the removal

    Returns:
        True if assignment was deactivated, False if not found
    """
    from datetime import datetime

    assignment = (
        db.query(EmployeeClientAssignment)
        .filter(EmployeeClientAssignment.employee_id == employee_id, EmployeeClientAssignment.client_id == client_id)
        .first()
    )

    if not assignment:
        return False

    assignment.is_active = False
    assignment.deactivated_at = datetime.now(tz=timezone.utc)
    assignment.deactivated_by = removed_by

    return True
