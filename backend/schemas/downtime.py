"""
Downtime database schema (SQLAlchemy)
PHASE 2: Downtime tracking
"""
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from backend.database import Base


class DowntimeEvent(Base):
    """Downtime events table"""
    __tablename__ = "downtime_events"

    downtime_id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    product_id = Column(Integer, ForeignKey('products.product_id'), nullable=False)
    shift_id = Column(Integer, ForeignKey('shifts.shift_id'), nullable=False)
    production_date = Column(Date, nullable=False)
    downtime_category = Column(String(50), nullable=False)
    downtime_reason = Column(String(255), nullable=False)
    duration_hours = Column(Numeric(5, 2), nullable=False)
    machine_id = Column(String(50))
    work_order_number = Column(String(50))
    notes = Column(Text)
    entered_by = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
