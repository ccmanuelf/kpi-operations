"""
WIP hold database schema (SQLAlchemy)
PHASE 2: WIP aging tracking
"""
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from backend.database import Base


class WIPHold(Base):
    """WIP hold records table"""
    __tablename__ = "wip_holds"

    hold_id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    product_id = Column(Integer, ForeignKey('products.product_id'), nullable=False)
    shift_id = Column(Integer, ForeignKey('shifts.shift_id'), nullable=False)
    hold_date = Column(Date, nullable=False)
    work_order_number = Column(String(50), nullable=False)
    quantity_held = Column(Integer, nullable=False)
    hold_reason = Column(String(255), nullable=False)
    hold_category = Column(String(50), nullable=False)
    expected_resolution_date = Column(Date)
    release_date = Column(Date)
    actual_resolution_date = Column(Date)
    quantity_released = Column(Integer)
    quantity_scrapped = Column(Integer)
    aging_days = Column(Integer)  # Calculated field
    notes = Column(Text)
    entered_by = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
