"""
FLOATING_POOL table ORM schema (SQLAlchemy)
Tracks shared resources across multiple clients
Source: 01-Core_DataEntities_Inventory.csv lines 54-60
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class FloatingPool(Base):
    """FLOATING_POOL table - Shared resource availability tracking"""
    __tablename__ = "FLOATING_POOL"
    __table_args__ = {"extend_existing": True}

    # Primary key
    pool_id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL (nullable for shared resources)
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=True, index=True)

    # Employee reference
    employee_id = Column(Integer, ForeignKey('EMPLOYEE.employee_id'), nullable=False, index=True)

    # Availability tracking
    available_from = Column(DateTime)
    available_to = Column(DateTime)
    current_assignment = Column(String(255))  # Current client_id or NULL if available

    # Metadata
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
