"""
DOWNTIME_ENTRY table ORM schema (SQLAlchemy)
Complete implementation for KPI #8 Availability calculation
Source: 03-Phase2_Downtime_WIP_Inventory.csv lines 2-19
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
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
    reported_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("USER.user_id"))
    resolved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("USER.user_id"))
    resolution_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Audit field - tracks who last modified the record (per audit requirement)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("USER.user_id"))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
