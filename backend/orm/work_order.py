"""
WORK_ORDER table ORM schema (SQLAlchemy)
Core entity for WIP tracking, OTD, and quality metrics
Source: 01-Core_DataEntities_Inventory.csv lines 16-42
"""

import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


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
    RECEIVED = "RECEIVED"  # Order acknowledged/received

    # Pre-production states
    RELEASED = "RELEASED"  # Released/dispatched to shopfloor
    DEMOTED = "DEMOTED"  # Priority lowered, pushed back

    # Production states (legacy + new)
    ACTIVE = "ACTIVE"  # Legacy: In active production (alias for IN_PROGRESS)
    IN_PROGRESS = "IN_PROGRESS"  # Currently being worked on
    ON_HOLD = "ON_HOLD"  # Paused/held

    # Completion states
    COMPLETED = "COMPLETED"  # Production completed

    # Post-production states
    SHIPPED = "SHIPPED"  # Shipped to client
    CLOSED = "CLOSED"  # Formally closed (terminal)

    # Termination states
    REJECTED = "REJECTED"  # QC rejection (terminal)
    CANCELLED = "CANCELLED"  # Order cancelled (terminal)


class WorkOrder(Base):
    """WORK_ORDER table - Central entity for all phases"""

    __tablename__ = "WORK_ORDER"
    __table_args__ = (
        # Composite indexes for query performance (per audit requirement)
        Index("ix_workorder_client_status", "client_id", "status"),  # Active work orders by client
        Index("ix_workorder_client_ship_date", "client_id", "planned_ship_date"),  # OTD queries
        Index("ix_workorder_status_ship_date", "status", "planned_ship_date"),  # Delivery reports
        {"extend_existing": True},
    )

    # Primary key
    work_order_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Order details
    style_model: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    planned_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_quantity: Mapped[Optional[int]] = mapped_column(Integer, default=0)

    # Workflow lifecycle dates
    received_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)  # When received
    planned_date: Mapped[Optional[datetime]] = mapped_column(DateTime)  # When work is planned to start
    expected_date: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Expected completion date
    dispatch_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)  # When released
    shipped_date: Mapped[Optional[datetime]] = mapped_column(DateTime)  # When shipped to client
    closure_date: Mapped[Optional[datetime]] = mapped_column(DateTime)  # When formally closed
    # USER.user_id is String(50), so this FK column type-matches that.
    # (Was Integer historically, but USER.user_id has been a string PK
    # for long enough that no rows ever stored a meaningful int here —
    # verified zero non-null rows in the live demo DB before migration.)
    closed_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("USER.user_id"))

    # Date tracking for OTD calculation (legacy + enhanced)
    planned_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    actual_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    planned_ship_date: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)  # REQUIRED for OTD
    required_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    actual_delivery_date: Mapped[Optional[datetime]] = mapped_column(DateTime)  # REQUIRED for OTD

    # Workflow state tracking
    previous_status: Mapped[Optional[str]] = mapped_column(String(20))  # For ON_HOLD resume tracking

    # Performance calculation
    ideal_cycle_time: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))  # Decimal hours (0.25 = 15 min)
    calculated_cycle_time: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))  # From production data

    # Status tracking
    status: Mapped[WorkOrderStatus] = mapped_column(
        SQLEnum(WorkOrderStatus), nullable=False, default=WorkOrderStatus.ACTIVE, index=True
    )
    priority: Mapped[Optional[str]] = mapped_column(String(20))  # HIGH, MEDIUM, LOW

    # Quality gates
    qc_approved: Mapped[Optional[int]] = mapped_column(Integer, default=0)  # Boolean
    qc_approved_by: Mapped[Optional[int]] = mapped_column(Integer)  # USER.user_id
    qc_approved_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Rejection tracking
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)
    rejected_by: Mapped[Optional[int]] = mapped_column(Integer)  # USER.user_id
    rejected_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Production tracking
    total_run_time_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    total_employees_assigned: Mapped[Optional[int]] = mapped_column(Integer)

    # Additional metadata
    notes: Mapped[Optional[str]] = mapped_column(Text)
    customer_po_number: Mapped[Optional[str]] = mapped_column(String(100))
    internal_notes: Mapped[Optional[str]] = mapped_column(Text)

    # Bridge to Capacity Planning: links work order to a capacity order.
    # NULL means ad-hoc work order (prove-in, test run, calibration, rework).
    capacity_order_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("capacity_orders.id"),
        nullable=True,
    )
    # Origin distinguishes planned WOs (from Capacity Planning) from ad-hoc ones (from Ops).
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="AD_HOC")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
