"""
Capacity Stock Snapshot - Weekly inventory positions
Point-in-time inventory data for capacity planning and MRP.
"""

from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class CapacityStockSnapshot(Base):
    """
    CAPACITY_STOCK_SNAPSHOT table - Point-in-time inventory positions

    Purpose:
    - Store weekly/periodic inventory snapshots
    - Support MRP calculations with on-hand, allocated, and on-order quantities
    - Track inventory by location

    Available quantity formula:
    available = on_hand - allocated + on_order

    Multi-tenant: All records isolated by client_id
    """

    __tablename__ = "capacity_stock_snapshot"
    __table_args__ = (
        Index("ix_capacity_stock_date_item", "client_id", "snapshot_date", "item_code"),
        Index("ix_capacity_stock_item", "client_id", "item_code"),
        {"extend_existing": True},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Snapshot date (indexed via composite indexes in __table_args__)
    snapshot_date: Mapped[date_type] = mapped_column(Date, nullable=False)

    # Item identification (indexed via composite indexes in __table_args__)
    item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    item_description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Stock quantities
    on_hand_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), default=0)  # Physical inventory
    allocated_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), default=0)  # Reserved
    on_order_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), default=0)  # Expected receipts
    available_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), default=0)  # Calculated

    # Unit and location
    unit_of_measure: Mapped[Optional[str]] = mapped_column(String(20), default="EA")
    location: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Notes/metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def calculate_available(self) -> float:
        """
        Calculate available quantity.
        Formula: on_hand - allocated + on_order
        """
        on_hand = float(self.on_hand_quantity or 0)
        allocated = float(self.allocated_quantity or 0)
        on_order = float(self.on_order_quantity or 0)
        return on_hand - allocated + on_order

    def is_short(self, required_quantity: float) -> bool:
        """Check if available quantity is less than required."""
        return self.calculate_available() < required_quantity

    def shortage_quantity(self, required_quantity: float) -> float:
        """Calculate shortage quantity (0 if none)."""
        shortage = required_quantity - self.calculate_available()
        return max(0, shortage)

    def __repr__(self) -> str:
        return f"<CapacityStockSnapshot(item={self.item_code}, date={self.snapshot_date}, avail={self.available_quantity})>"
