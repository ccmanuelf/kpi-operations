"""
Production Entry ORM schema (SQLAlchemy)
"""
from sqlalchemy import (
    Column, Integer, String, Date, DECIMAL, Text, TIMESTAMP, ForeignKey
)
from sqlalchemy.sql import func
from backend.database import Base


class ProductionEntry(Base):
    """Production Entry table ORM"""
    __tablename__ = "production_entry"
    __table_args__ = {"extend_existing": True}

    entry_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("product.product_id"), nullable=False)
    shift_id = Column(Integer, ForeignKey("shift.shift_id"), nullable=False)
    production_date = Column(Date, nullable=False, index=True)
    work_order_number = Column(String(50), index=True)

    # Production metrics
    units_produced = Column(Integer, nullable=False)
    run_time_hours = Column(DECIMAL(8, 2), nullable=False)
    employees_assigned = Column(Integer, nullable=False)

    # Quality metrics
    defect_count = Column(Integer, nullable=False, default=0)
    scrap_count = Column(Integer, nullable=False, default=0)

    # Calculated KPIs
    efficiency_percentage = Column(DECIMAL(8, 4), nullable=True)
    performance_percentage = Column(DECIMAL(8, 4), nullable=True)

    # Metadata
    notes = Column(Text)
    entered_by = Column(Integer, ForeignKey("user.user_id"), nullable=False)
    confirmed_by = Column(Integer, ForeignKey("user.user_id"))
    confirmation_timestamp = Column(TIMESTAMP, nullable=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
    updated_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now(), onupdate=func.now()
    )
