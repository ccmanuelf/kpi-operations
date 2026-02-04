"""
Capacity Stock Snapshot - Weekly inventory positions
Point-in-time inventory data for capacity planning and MRP.
"""
from sqlalchemy import Column, Integer, String, Numeric, Date, ForeignKey, Text, Index
from sqlalchemy.sql import func
from sqlalchemy import DateTime
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
        Index('ix_capacity_stock_date_item', 'client_id', 'snapshot_date', 'item_code'),
        Index('ix_capacity_stock_item', 'client_id', 'item_code'),
        {"extend_existing": True}
    )

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # Snapshot date (indexed via composite indexes in __table_args__)
    snapshot_date = Column(Date, nullable=False)

    # Item identification (indexed via composite indexes in __table_args__)
    item_code = Column(String(50), nullable=False)
    item_description = Column(String(200), nullable=True)

    # Stock quantities
    on_hand_quantity = Column(Numeric(12, 4), default=0)  # Physical inventory
    allocated_quantity = Column(Numeric(12, 4), default=0)  # Reserved for orders
    on_order_quantity = Column(Numeric(12, 4), default=0)  # Expected receipts
    available_quantity = Column(Numeric(12, 4), default=0)  # Calculated: on_hand - allocated + on_order

    # Unit and location
    unit_of_measure = Column(String(20), default="EA")
    location = Column(String(50), nullable=True)

    # Notes/metadata
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

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

    def __repr__(self):
        return f"<CapacityStockSnapshot(item={self.item_code}, date={self.snapshot_date}, avail={self.available_quantity})>"
