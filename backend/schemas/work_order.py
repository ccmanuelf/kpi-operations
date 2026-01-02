"""
WORK_ORDER table ORM schema (SQLAlchemy)
Core entity for WIP tracking, OTD, and quality metrics
Source: 01-Core_DataEntities_Inventory.csv lines 16-42
"""
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from backend.database import Base
import enum


class WorkOrderStatus(str, enum.Enum):
    """Work order status"""
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class WorkOrder(Base):
    """WORK_ORDER table - Central entity for all phases"""
    __tablename__ = "WORK_ORDER"

    # Primary key
    work_order_id = Column(String(50), primary_key=True, index=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # Order details
    style_model = Column(String(100), nullable=False, index=True)
    planned_quantity = Column(Integer, nullable=False)
    actual_quantity = Column(Integer, default=0)

    # Date tracking for OTD calculation
    planned_start_date = Column(DateTime)
    actual_start_date = Column(DateTime, index=True)
    planned_ship_date = Column(DateTime, index=True)  # REQUIRED for OTD
    required_date = Column(DateTime)
    actual_delivery_date = Column(DateTime)  # REQUIRED for OTD

    # Performance calculation
    ideal_cycle_time = Column(Numeric(10, 4))  # Decimal hours (0.25 = 15 min)
    calculated_cycle_time = Column(Numeric(10, 4))  # From production data

    # Status tracking
    status = Column(SQLEnum(WorkOrderStatus), nullable=False, default=WorkOrderStatus.ACTIVE, index=True)
    priority = Column(String(20))  # HIGH, MEDIUM, LOW

    # Quality gates
    qc_approved = Column(Integer, default=0)  # Boolean
    qc_approved_by = Column(Integer)  # USER.user_id
    qc_approved_date = Column(DateTime)

    # Rejection tracking
    rejection_reason = Column(Text)
    rejected_by = Column(Integer)  # USER.user_id
    rejected_date = Column(DateTime)

    # Production tracking
    total_run_time_hours = Column(Numeric(10, 2))
    total_employees_assigned = Column(Integer)

    # Additional metadata
    notes = Column(Text)
    customer_po_number = Column(String(100))
    internal_notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
