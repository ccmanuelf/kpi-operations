"""
Capacity Orders - Planning orders (separate from Work Orders)
Orders specifically for capacity planning, with their own lifecycle.
"""

import enum
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Date, DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class OrderPriority(str, enum.Enum):
    """Order priority levels for scheduling"""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class OrderStatus(str, enum.Enum):
    """
    Order status lifecycle for capacity planning

    Workflow:
    DRAFT -> CONFIRMED -> SCHEDULED -> IN_PROGRESS -> COMPLETED
                |
                v
           CANCELLED
    """

    DRAFT = "DRAFT"  # Initial state, order being created
    CONFIRMED = "CONFIRMED"  # Order confirmed by customer/planner
    SCHEDULED = "SCHEDULED"  # Assigned to schedule/production lines
    IN_PROGRESS = "IN_PROGRESS"  # Production started
    COMPLETED = "COMPLETED"  # Production completed
    CANCELLED = "CANCELLED"  # Order cancelled


class CapacityOrder(Base):
    """
    CAPACITY_ORDERS table - Planning orders for capacity module

    Purpose:
    - Store orders used for capacity planning (separate from WORK_ORDER)
    - Track order quantities, dates, and production progress
    - Support scheduling and MRP calculations

    Note: This table is separate from WORK_ORDER to allow capacity planning
    without affecting operational work order tracking.

    Multi-tenant: All records isolated by client_id
    """

    __tablename__ = "capacity_orders"
    __table_args__ = (
        Index("ix_capacity_orders_client_status", "client_id", "status"),
        Index("ix_capacity_orders_client_required_date", "client_id", "required_date"),
        Index("ix_capacity_orders_style", "client_id", "style_model"),
        {"extend_existing": True},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Order identification
    order_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Style/product details (style_model indexed via composite index in __table_args__)
    style_model: Mapped[str] = mapped_column(String(100), nullable=False)
    style_description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Quantities
    order_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_quantity: Mapped[Optional[int]] = mapped_column(Integer, default=0)

    # Dates (required_date indexed via composite index in __table_args__)
    order_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)  # When order was received
    required_date: Mapped[date_type] = mapped_column(Date, nullable=False)  # Customer need date
    planned_start_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)  # Planned start
    planned_end_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)  # Planned end

    # Status and priority (status indexed via composite index in __table_args__)
    priority: Mapped[Optional[OrderPriority]] = mapped_column(SQLEnum(OrderPriority), default=OrderPriority.NORMAL)
    status: Mapped[Optional[OrderStatus]] = mapped_column(SQLEnum(OrderStatus), default=OrderStatus.DRAFT)

    # SAM for this specific order (if different from standard)
    # Allows order-level override of production standard
    order_sam_minutes: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)

    # Notes/metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def remaining_quantity(self) -> int:
        """Calculate remaining quantity to produce."""
        return max(0, (self.order_quantity or 0) - (self.completed_quantity or 0))

    def completion_percent(self) -> float:
        """Calculate completion percentage."""
        if not self.order_quantity or self.order_quantity == 0:
            return 0.0
        return min(100.0, (self.completed_quantity or 0) / self.order_quantity * 100)

    def __repr__(self) -> str:
        return f"<CapacityOrder(client_id={self.client_id}, order={self.order_number}, style={self.style_model})>"
