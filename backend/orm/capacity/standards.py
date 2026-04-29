"""
Capacity Production Standards - SAM per operation per style
Standard Allowed Minutes (SAM) define the expected time for each operation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class CapacityProductionStandard(Base):
    """
    CAPACITY_PRODUCTION_STANDARDS table - SAM data by style and operation

    Purpose:
    - Define Standard Allowed Minutes (SAM) for production operations
    - Support capacity calculations based on style complexity
    - Track setup, machine, and manual time components

    SAM (Standard Allowed Minutes) is the industry standard measure
    for production time in apparel/manufacturing.

    Multi-tenant: All records isolated by client_id
    """

    __tablename__ = "capacity_production_standards"
    __table_args__ = (
        Index("ix_capacity_standards_style_op", "client_id", "style_model", "operation_code"),
        {"extend_existing": True},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Style and operation identification (indexed via composite index in __table_args__)
    style_model: Mapped[str] = mapped_column(String(100), nullable=False)
    operation_code: Mapped[str] = mapped_column(String(50), nullable=False)
    operation_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # CUTTING/SEWING/FINISHING/etc.

    # Standard Allowed Minutes (total)
    sam_minutes: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)

    # Optional time breakdown
    setup_time_minutes: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), default=0)
    machine_time_minutes: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), default=0)
    manual_time_minutes: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), default=0)

    # Notes/metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def total_minutes(self) -> float:
        """
        Return total SAM minutes.
        Uses sam_minutes directly, or sum of breakdown if sam_minutes not set.
        """
        if self.sam_minutes:
            return float(self.sam_minutes)
        return (
            float(self.setup_time_minutes or 0)
            + float(self.machine_time_minutes or 0)
            + float(self.manual_time_minutes or 0)
        )

    def sam_hours(self) -> float:
        """Return SAM in hours."""
        return self.total_minutes() / 60.0

    def __repr__(self) -> str:
        return (
            f"<CapacityProductionStandard(style={self.style_model}, op={self.operation_code}, sam={self.sam_minutes})>"
        )
