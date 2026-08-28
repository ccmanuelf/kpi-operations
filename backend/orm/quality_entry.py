"""
QUALITY_ENTRY table ORM schema (SQLAlchemy)
Complete implementation for KPI #4 PPM, #5 DPMO, #6 FPY, #7 RTY
Source: 05-Phase4_Quality_Inventory.csv lines 2-25
Enhanced with composite indexes for query performance (per audit requirement)
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class QualityEntry(Base):
    """QUALITY_ENTRY table - Quality inspection tracking for PPM/DPMO/FPY/RTY"""

    __tablename__ = "QUALITY_ENTRY"
    __table_args__ = (
        # Composite indexes for query performance (per audit requirement)
        Index("ix_quality_client_shift_date", "client_id", "shift_date"),  # Most common query pattern
        Index("ix_quality_client_work_order", "client_id", "work_order_id"),  # Work order quality
        Index("ix_quality_shift_date_stage", "shift_date", "inspection_stage"),  # Inspection reports
        {"extend_existing": True},
    )

    # Primary key
    quality_entry_id: Mapped[str] = mapped_column(String(50), primary_key=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Work order reference
    work_order_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("WORK_ORDER.work_order_id"), nullable=False, index=True
    )
    job_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("JOB.job_id"), index=True)  # Job-level

    # Date tracking
    shift_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    inspection_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Inspection metrics - REQUIRED for quality KPI calculations
    units_inspected: Mapped[int] = mapped_column(Integer, nullable=False)
    units_passed: Mapped[int] = mapped_column(Integer, nullable=False)  # For FPY calculation
    units_defective: Mapped[int] = mapped_column(Integer, nullable=False)  # For PPM calculation
    total_defects_count: Mapped[int] = mapped_column(Integer, nullable=False)  # DPMO (≠ units_defective)

    # Process tracking
    inspection_stage: Mapped[Optional[str]] = mapped_column(String(50))  # "Incoming", "In-Process", "Final"
    process_step: Mapped[Optional[str]] = mapped_column(String(100))  # For RTY calculation
    operation_checked: Mapped[Optional[str]] = mapped_column(String(50))  # Which operation was inspected
    is_first_pass: Mapped[Optional[int]] = mapped_column(Integer, default=1)  # 1=first pass, 0=rework

    # Disposition
    units_scrapped: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    units_reworked: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    units_requiring_repair: Mapped[Optional[int]] = mapped_column(Integer, default=0)  # Repair tracking

    # Calculated KPIs (cached for performance)
    ppm: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))  # Parts Per Million
    dpmo: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))  # Defects Per Million Opportunities
    fpy_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4))  # First Pass Yield

    # Quality details
    inspection_method: Mapped[Optional[str]] = mapped_column(String(100))
    inspector_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("USER.user_id"))

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
