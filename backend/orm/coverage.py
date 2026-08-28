"""
Shift coverage database schema (SQLAlchemy)
PHASE 3: Shift coverage tracking
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class ShiftCoverage(Base):
    """Shift coverage table"""

    __tablename__ = "shift_coverage"
    __table_args__ = {"extend_existing": True}

    coverage_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    shift_id: Mapped[int] = mapped_column(Integer, ForeignKey("SHIFT.shift_id"), nullable=False)
    coverage_date: Mapped[date] = mapped_column(Date, nullable=False)
    required_employees: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_employees: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))  # Calculated field
    notes: Mapped[Optional[str]] = mapped_column(Text)
    entered_by: Mapped[str] = mapped_column(String(50), ForeignKey("USER.user_id"), nullable=False)
    # Soft delete (S1): DELETE endpoints set this False instead of removing the row.
    # Filtering is automatic — see backend/db/soft_delete_filter.py, declared in
    # backend/db/soft_delete_registry.py. Do NOT hand-filter on it.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    # Who deleted it and when. Without these a soft-deleted row is
    # indistinguishable from one that was never active — worse than a hard
    # delete, which at least leaves an absence someone might notice.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Deliberately NOT a FK, for the same reason AUDIT_ENTRY.actor_user_id is not:
    # this is a historical record of who acted, and it has to stay readable after
    # that user is renamed or deactivated — which is exactly when it is needed.
    # It also keeps the migration a plain ADD COLUMN: adding a FK constraint to an
    # existing SQLite table needs a batch table rebuild, on 37k rows across 11 tables.
    deleted_by: Mapped[Optional[str]] = mapped_column(String(50))

    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )
