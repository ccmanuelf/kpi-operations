"""
QUALITY_ENTRY table ORM schema (SQLAlchemy)
Complete implementation for KPI #4 PPM, #5 DPMO, #6 FPY, #7 RTY
Source: 05-Phase4_Quality_Inventory.csv lines 2-25
"""
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class QualityEntry(Base):
    """QUALITY_ENTRY table - Quality inspection tracking for PPM/DPMO/FPY/RTY"""
    __tablename__ = "QUALITY_ENTRY"
    __table_args__ = {"extend_existing": True}

    # Primary key
    quality_entry_id = Column(String(50), primary_key=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # Work order reference
    work_order_id = Column(String(50), ForeignKey('WORK_ORDER.work_order_id'), nullable=False, index=True)
    job_id = Column(String(50), ForeignKey('JOB.job_id'), index=True)  # Job-level tracking

    # Date tracking
    shift_date = Column(DateTime, nullable=False, index=True)
    inspection_date = Column(DateTime)

    # Inspection metrics - REQUIRED for quality KPI calculations
    units_inspected = Column(Integer, nullable=False)
    units_passed = Column(Integer, nullable=False)  # For FPY calculation
    units_defective = Column(Integer, nullable=False)  # For PPM calculation
    total_defects_count = Column(Integer, nullable=False)  # For DPMO calculation (≠ units_defective)

    # Process tracking
    inspection_stage = Column(String(50))  # "Incoming", "In-Process", "Final"
    process_step = Column(String(100))  # For RTY calculation
    operation_checked = Column(String(50))  # Which operation was inspected
    is_first_pass = Column(Integer, default=1)  # Boolean: 1=first pass, 0=rework

    # Disposition
    units_scrapped = Column(Integer, default=0)
    units_reworked = Column(Integer, default=0)
    units_requiring_repair = Column(Integer, default=0)  # Repair tracking

    # Calculated KPIs (cached for performance)
    ppm = Column(Numeric(12, 2))  # Parts Per Million
    dpmo = Column(Numeric(12, 2))  # Defects Per Million Opportunities
    fpy_percentage = Column(Numeric(8, 4))  # First Pass Yield

    # Quality details
    inspection_method = Column(String(100))
    inspector_id = Column(Integer, ForeignKey('USER.user_id'))

    # Metadata
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
