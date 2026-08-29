"""
DOWNTIME_ENTRY table ORM schema (SQLAlchemy)
Complete implementation for KPI #8 Availability calculation
Source: 03-Phase2_Downtime_WIP_Inventory.csv lines 2-19
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.sql import func

from backend.database import Base


class DowntimeEntry(Base):
    """DOWNTIME_ENTRY table - Equipment downtime tracking for Availability KPI"""

    __tablename__ = "DOWNTIME_ENTRY"
    __table_args__ = {"extend_existing": True}

    # Primary key
    downtime_entry_id: Mapped[str] = mapped_column(String(50), primary_key=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)
    line_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("PRODUCTION_LINE.line_id"), nullable=True, index=True
    )

    # Work order reference (optional — downtime can be attributed to machine/line without a work order)
    work_order_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("WORK_ORDER.work_order_id"), nullable=True, index=True
    )

    # Date tracking
    shift_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Downtime classification - String to accept any value
    downtime_reason: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    downtime_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)  # REQUIRED for Availability

    # Equipment details
    machine_id: Mapped[Optional[str]] = mapped_column(String(100))
    equipment_code: Mapped[Optional[str]] = mapped_column(String(50))

    # Root cause analysis
    root_cause_category: Mapped[Optional[str]] = mapped_column(String(100))
    corrective_action: Mapped[Optional[str]] = mapped_column(Text)

    # Responsible parties
    reported_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("USER.user_id"))
    resolved_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("USER.user_id"))
    resolution_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Audit field - tracks who last modified the record (per audit requirement)
    updated_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("USER.user_id"))

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

    @validates("downtime_reason")
    def _validate_downtime_reason(self, key: str, value: str) -> str:
        from backend.orm.downtime_taxonomy import DowntimeReasonEnum

        valid = {r.value for r in DowntimeReasonEnum}
        if value not in valid:
            raise ValueError(f"downtime_reason must be one of {sorted(valid)}, got {value!r}")
        return value

    @validates("root_cause_category")
    def _validate_root_cause_category(self, key: str, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        from backend.orm.downtime_taxonomy import DowntimeCategoryEnum

        valid = {c.value for c in DowntimeCategoryEnum}
        if value not in valid:
            raise ValueError(f"root_cause_category must be one of {sorted(valid)} or NULL, got {value!r}")
        return value
