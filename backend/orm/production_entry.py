"""
PRODUCTION_ENTRY table ORM schema (SQLAlchemy)
Complete implementation with all 26 fields for KPI #3 Efficiency and #9 Performance
Source: 02-Phase1_Production_Inventory.csv
Enhanced with composite indexes for query performance (per audit requirement)

Phase A.2: Added relationships with joined loading for query optimization
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database import Base


class ProductionEntry(Base):
    """PRODUCTION_ENTRY table - Daily production tracking"""

    __tablename__ = "PRODUCTION_ENTRY"
    __table_args__ = (
        # Composite indexes for query performance (per audit requirement)
        Index("ix_production_client_shift_date", "client_id", "shift_date"),  # Most common query pattern
        Index("ix_production_client_product", "client_id", "product_id"),  # Client product analysis
        Index("ix_production_shift_date_product", "shift_date", "product_id"),  # Date range by product
        Index("ix_production_client_work_order", "client_id", "work_order_id"),  # Work order lookups
        {"extend_existing": True},
    )

    # Primary key
    production_entry_id: Mapped[str] = mapped_column(String(50), primary_key=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)
    line_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("PRODUCTION_LINE.line_id"), nullable=True, index=True
    )

    # References
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("PRODUCT.product_id"), nullable=False, index=True)
    shift_id: Mapped[int] = mapped_column(Integer, ForeignKey("SHIFT.shift_id"), nullable=False, index=True)
    work_order_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("WORK_ORDER.work_order_id"), index=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("JOB.job_id"), index=True)  # Job-level

    # Date tracking
    production_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    shift_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)

    # Production metrics (REQUIRED for KPI calculations)
    units_produced: Mapped[int] = mapped_column(Integer, nullable=False)
    run_time_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    employees_assigned: Mapped[int] = mapped_column(Integer, nullable=False)
    employees_present: Mapped[Optional[int]] = mapped_column(Integer)  # For absenteeism correlation

    # Quality metrics
    defect_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scrap_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rework_count: Mapped[Optional[int]] = mapped_column(Integer, default=0)

    # Time breakdown
    setup_time_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    downtime_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    maintenance_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # Performance calculation inputs
    ideal_cycle_time: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))  # Hours per unit
    actual_cycle_time: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))  # run_time / units_produced

    # Calculated KPIs (cached)
    efficiency_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4))
    performance_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4))
    quality_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4))

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text)
    entered_by: Mapped[int] = mapped_column(Integer, ForeignKey("USER.user_id"), nullable=False)
    confirmed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("USER.user_id"))
    confirmation_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime)
    entry_method: Mapped[Optional[str]] = mapped_column(String(20), default="MANUAL_ENTRY")  # MANUAL/CSV/API

    # Audit field - tracks who last modified the record (per audit requirement)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("USER.user_id"))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships with joined loading for query optimization (Phase A.2)
    # Using lazy="joined" pre-fetches related data in a single query
    product = relationship(
        "Product",
        lazy="joined",
        foreign_keys=[product_id],
        primaryjoin="ProductionEntry.product_id == Product.product_id",
    )
    shift = relationship(
        "Shift", lazy="joined", foreign_keys=[shift_id], primaryjoin="ProductionEntry.shift_id == Shift.shift_id"
    )
