"""
PRODUCTION_ENTRY table ORM schema (SQLAlchemy)
Complete implementation with all 26 fields for KPI #3 Efficiency and #9 Performance
Source: 02-Phase1_Production_Inventory.csv
"""
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class ProductionEntry(Base):
    """PRODUCTION_ENTRY table - Daily production tracking"""
    __tablename__ = "PRODUCTION_ENTRY"

    # Primary key
    production_entry_id = Column(String(50), primary_key=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # References
    product_id = Column(Integer, ForeignKey("PRODUCT.product_id"), nullable=False, index=True)
    shift_id = Column(Integer, ForeignKey("SHIFT.shift_id"), nullable=False, index=True)
    work_order_id = Column(String(50), ForeignKey("WORK_ORDER.work_order_id"), index=True)

    # Date tracking
    production_date = Column(DateTime, nullable=False, index=True)
    shift_date = Column(DateTime, nullable=False, index=True)

    # Production metrics (REQUIRED for KPI calculations)
    units_produced = Column(Integer, nullable=False)
    run_time_hours = Column(Numeric(10, 2), nullable=False)
    employees_assigned = Column(Integer, nullable=False)

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

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
