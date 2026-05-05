"""
Capacity Component Check - MRP explosion results
Stores results of component availability checks for orders.
"""

import enum
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class ComponentStatus(str, enum.Enum):
    """Component availability status"""

    OK = "OK"  # Full quantity available
    SHORTAGE = "SHORTAGE"  # No quantity available
    PARTIAL = "PARTIAL"  # Partial quantity available


class CapacityComponentCheck(Base):
    """
    CAPACITY_COMPONENT_CHECK table - MRP explosion results

    Purpose:
    - Store results of component availability checks
    - Track shortages by order and component
    - Support material planning and procurement decisions

    Multi-tenant: All records isolated by client_id
    """

    __tablename__ = "capacity_component_check"
    __table_args__ = (
        Index("ix_capacity_component_check_order", "client_id", "order_id"),
        Index("ix_capacity_component_check_run_date", "client_id", "run_date"),
        Index("ix_capacity_component_check_status", "client_id", "status"),
        {"extend_existing": True},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Check run metadata (indexed via composite index in __table_args__)
    run_date: Mapped[date_type] = mapped_column(Date, nullable=False)

    # Source order reference
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("capacity_orders.id"), nullable=False, index=True)
    order_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Denormalized for reporting

    # Component details
    component_item_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    component_description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Quantities
    required_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    available_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    shortage_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), default=0)

    # Status (indexed via composite index in __table_args__)
    status: Mapped[Optional[ComponentStatus]] = mapped_column(SQLEnum(ComponentStatus), default=ComponentStatus.OK)

    # Notes/metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    @classmethod
    def calculate_status(cls, required: float, available: float) -> ComponentStatus:
        """
        Determine component status based on quantities.

        Args:
            required: Required quantity
            available: Available quantity

        Returns:
            ComponentStatus enum value
        """
        if available >= required:
            return ComponentStatus.OK
        elif available <= 0:
            return ComponentStatus.SHORTAGE
        else:
            return ComponentStatus.PARTIAL

    def coverage_percent(self) -> float:
        """Calculate percentage of requirement covered."""
        if not self.required_quantity or float(self.required_quantity) == 0:
            return 100.0
        return min(100.0, float(self.available_quantity or 0) / float(self.required_quantity) * 100)

    def __repr__(self) -> str:
        return (
            f"<CapacityComponentCheck(order={self.order_number}, "
            f"component={self.component_item_code}, status={self.status})>"
        )
