"""
PRODUCTION_ENTRY table ORM schema (SQLAlchemy)
Complete implementation with all 26 fields for KPI #3 Efficiency and #9 Performance
Source: 02-Phase1_Production_Inventory.csv
Enhanced with composite indexes for query performance (per audit requirement)

Phase A.2: Added relationships with joined loading for query optimization
"""

from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
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
    production_entry_id = Column(String(50), primary_key=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # References
    product_id = Column(Integer, ForeignKey("PRODUCT.product_id"), nullable=False, index=True)
    shift_id = Column(Integer, ForeignKey("SHIFT.shift_id"), nullable=False, index=True)
    work_order_id = Column(String(50), ForeignKey("WORK_ORDER.work_order_id"), index=True)
    job_id = Column(String(50), ForeignKey("JOB.job_id"), index=True)  # Job-level tracking

    # Date tracking
    production_date = Column(DateTime, nullable=False, index=True)
    shift_date = Column(DateTime, nullable=False, index=True)

    # Production metrics (REQUIRED for KPI calculations)
    units_produced = Column(Integer, nullable=False)
    run_time_hours = Column(Numeric(10, 2), nullable=False)
    employees_assigned = Column(Integer, nullable=False)
    employees_present = Column(Integer)  # For absenteeism correlation

    # Quality metrics
    defect_count = Column(Integer, nullable=False, default=0)
    scrap_count = Column(Integer, nullable=False, default=0)
    rework_count = Column(Integer, default=0)

    # Time breakdown
    setup_time_hours = Column(Numeric(10, 2))
    downtime_hours = Column(Numeric(10, 2))
    maintenance_hours = Column(Numeric(10, 2))

    # Performance calculation inputs
    ideal_cycle_time = Column(Numeric(10, 4))  # Hours per unit
    actual_cycle_time = Column(Numeric(10, 4))  # Calculated from run_time / units_produced

    # Calculated KPIs (cached)
    efficiency_percentage = Column(Numeric(8, 4))
    performance_percentage = Column(Numeric(8, 4))
    quality_rate = Column(Numeric(8, 4))

    # Metadata
    notes = Column(Text)
    entered_by = Column(Integer, ForeignKey("USER.user_id"), nullable=False)
    confirmed_by = Column(Integer, ForeignKey("USER.user_id"))
    confirmation_timestamp = Column(DateTime)
    entry_method = Column(String(20), default="MANUAL_ENTRY")  # MANUAL_ENTRY, CSV_UPLOAD, API

    # Audit field - tracks who last modified the record (per audit requirement)
    updated_by = Column(Integer, ForeignKey("USER.user_id"))

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

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
