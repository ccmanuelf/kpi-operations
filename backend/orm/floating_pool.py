"""
FLOATING_POOL table ORM schema (SQLAlchemy)
Tracks shared resources across multiple clients
Source: 01-Core_DataEntities_Inventory.csv lines 54-60
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class FloatingPool(Base):
    """FLOATING_POOL table - Shared resource availability tracking"""

    __tablename__ = "FLOATING_POOL"
    __table_args__ = {"extend_existing": True}

    # Primary key
    pool_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL (nullable for shared resources)
    client_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("CLIENT.client_id"), nullable=True, index=True
    )

    # Employee reference
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("EMPLOYEE.employee_id"), nullable=False, index=True)

    # Availability tracking
    available_from: Mapped[Optional[datetime]] = mapped_column(DateTime)
    available_to: Mapped[Optional[datetime]] = mapped_column(DateTime)
    current_assignment: Mapped[Optional[str]] = mapped_column(String(255))  # Current client_id or NULL if available

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text)

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

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
