"""
EMPLOYEE_LINE_ASSIGNMENT table ORM schema (SQLAlchemy)
Junction table for assigning employees to production lines with allocation tracking.

Business Rules:
- An employee can be assigned to at most 2 active production lines
- Total allocation across active assignments must not exceed 100%
- Each assignment has an effective_date and optional end_date (NULL = currently active)
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Date,
    Numeric,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.sql import func
from backend.database import Base


class EmployeeLineAssignment(Base):
    """
    EMPLOYEE_LINE_ASSIGNMENT table - Maps employees to production lines.

    Supports:
    - 1 line at 100% (default) or 2 lines with percentage split (e.g., 60/40)
    - Date-bounded assignments (effective_date + end_date)
    - Primary line designation
    - Multi-tenant isolation via client_id
    """

    __tablename__ = "EMPLOYEE_LINE_ASSIGNMENT"
    __table_args__ = (
        UniqueConstraint(
            "employee_id", "line_id", "effective_date",
            name="uq_employee_line_date",
        ),
        Index("idx_ela_employee", "employee_id"),
        Index("idx_ela_line", "line_id"),
        Index("idx_ela_client", "client_id"),
        {"extend_existing": True},
    )

    # Primary key
    assignment_id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    employee_id = Column(
        Integer,
        ForeignKey("EMPLOYEE.employee_id", ondelete="CASCADE"),
        nullable=False,
    )
    line_id = Column(
        Integer,
        ForeignKey("PRODUCTION_LINE.line_id", ondelete="CASCADE"),
        nullable=False,
    )
    client_id = Column(
        String(50),
        ForeignKey("CLIENT.client_id", ondelete="RESTRICT"),
        nullable=False,
    )

    # Allocation
    allocation_percentage = Column(
        Numeric(5, 2), nullable=False, default=100.00,
    )  # 1.00 - 100.00

    # Primary line flag
    is_primary = Column(Boolean, default=True, nullable=False)

    # Date range
    effective_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # NULL = currently active

    # Audit
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    def __repr__(self):
        return (
            f"<EmployeeLineAssignment(id={self.assignment_id}, "
            f"emp={self.employee_id}, line={self.line_id}, "
            f"alloc={self.allocation_percentage}%, "
            f"primary={self.is_primary})>"
        )
