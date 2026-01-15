"""
Quality inspection database schema (SQLAlchemy)
PHASE 4: Quality metrics tracking
"""
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from backend.database import Base


class QualityInspection(Base):
    """Quality inspection records table"""
    __tablename__ = "quality_inspections"
    __table_args__ = {"extend_existing": True}

    inspection_id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    product_id = Column(Integer, ForeignKey('PRODUCT.product_id'), nullable=False)
    shift_id = Column(Integer, ForeignKey('SHIFT.shift_id'), nullable=False)
    inspection_date = Column(Date, nullable=False)
    work_order_number = Column(String(50))
    units_inspected = Column(Integer, nullable=False)
    defects_found = Column(Integer, default=0)
    defect_type = Column(String(100))
    defect_category = Column(String(50))
    scrap_units = Column(Integer, default=0)
    rework_units = Column(Integer, default=0)
    inspection_stage = Column(String(50), nullable=False)
    ppm = Column(Numeric(12, 2))  # Calculated field
    dpmo = Column(Numeric(12, 2))  # Calculated field
    notes = Column(Text)
    entered_by = Column(Integer, ForeignKey('USER.user_id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
