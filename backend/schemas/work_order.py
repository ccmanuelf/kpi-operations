"""
WORK_ORDER table ORM schema (SQLAlchemy)
Core entity for WIP tracking, OTD, and quality metrics
Source: 01-Core_DataEntities_Inventory.csv lines 16-42
"""
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey, Enum as SQLEnum, Index
from sqlalchemy.sql import func
from backend.database import Base
import enum


class WorkOrderStatus(str, enum.Enum):
    """
    Work order status - Flexible workflow states

    Workflow lifecycle (configurable per client):
    RECEIVED → RELEASED → IN_PROGRESS → COMPLETED → SHIPPED → CLOSED

    Optional branches:
    - Any → ON_HOLD → (previous state)
    - Any → CANCELLED
    - RELEASED → DEMOTED → RECEIVED
    """
    # Initial states
    RECEIVED = "RECEIVED"           # Order acknowledged/received

    # Pre-production states
    RELEASED = "RELEASED"           # Released/dispatched to shopfloor
    DEMOTED = "DEMOTED"             # Priority lowered, pushed back

    # Production states (legacy + new)
    ACTIVE = "ACTIVE"               # Legacy: In active production (alias for IN_PROGRESS)
    IN_PROGRESS = "IN_PROGRESS"     # Currently being worked on
    ON_HOLD = "ON_HOLD"             # Paused/held

    # Completion states
    COMPLETED = "COMPLETED"         # Production completed

    # Post-production states
    SHIPPED = "SHIPPED"             # Shipped to client
    CLOSED = "CLOSED"               # Formally closed (terminal)

    # Termination states
    REJECTED = "REJECTED"           # QC rejection (terminal)
    CANCELLED = "CANCELLED"         # Order cancelled (terminal)


class WorkOrder(Base):
    """WORK_ORDER table - Central entity for all phases"""
    __tablename__ = "WORK_ORDER"
    __table_args__ = (
        # Composite indexes for query performance (per audit requirement)
        Index('ix_workorder_client_status', 'client_id', 'status'),  # Active work orders by client
        Index('ix_workorder_client_ship_date', 'client_id', 'planned_ship_date'),  # OTD queries
        Index('ix_workorder_status_ship_date', 'status', 'planned_ship_date'),  # Delivery reports
        {"extend_existing": True}
    )

    # Primary key
    work_order_id = Column(String(50), primary_key=True, index=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # Order details
    style_model = Column(String(100), nullable=False, index=True)
    planned_quantity = Column(Integer, nullable=False)
    actual_quantity = Column(Integer, default=0)

    # Workflow lifecycle dates
    received_date = Column(DateTime, index=True)      # When order was received/acknowledged
    planned_date = Column(DateTime)                    # When work is planned to start
    expected_date = Column(DateTime)                   # Expected completion date
    dispatch_date = Column(DateTime, index=True)       # When released/dispatched to shopfloor
    shipped_date = Column(DateTime)                    # When shipped to client
    closure_date = Column(DateTime)                    # When formally closed
    closed_by = Column(Integer)                        # USER.user_id who closed the order

    # Date tracking for OTD calculation (legacy + enhanced)
    planned_start_date = Column(DateTime)
    actual_start_date = Column(DateTime, index=True)
    planned_ship_date = Column(DateTime, index=True)  # REQUIRED for OTD
    required_date = Column(DateTime)
    actual_delivery_date = Column(DateTime)  # REQUIRED for OTD

    # Workflow state tracking
    previous_status = Column(String(20))               # For ON_HOLD resume tracking

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
