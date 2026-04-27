"""
Capacity BOM - Bill of Materials
Two-table structure: Header (parent items) and Detail (components).
Used for MRP explosion and component availability checking.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database import Base


class CapacityBOMHeader(Base):
    """
    CAPACITY_BOM_HEADER table - Bill of Materials parent items

    Purpose:
    - Define parent items (finished goods/assemblies)
    - Link to style codes for production planning
    - Track BOM revisions

    Multi-tenant: All records isolated by client_id
    """

    __tablename__ = "capacity_bom_header"
    __table_args__ = (
        Index("ix_capacity_bom_header_parent", "client_id", "parent_item_code"),
        Index("ix_capacity_bom_header_style", "client_id", "style_model"),
        {"extend_existing": True},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Parent item identification (indexed via composite index in __table_args__)
    parent_item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_item_description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Link to style (indexed via composite index in __table_args__)
    style_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Revision tracking
    revision: Mapped[Optional[str]] = mapped_column(String(20), default="1.0")

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Notes/metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationship to details
    components = relationship(
        "CapacityBOMDetail", back_populates="header", cascade="all, delete-orphan", lazy="dynamic"
    )

    def __repr__(self):
        return f"<CapacityBOMHeader(parent={self.parent_item_code}, rev={self.revision})>"


class CapacityBOMDetail(Base):
    """
    CAPACITY_BOM_DETAIL table - Bill of Materials components

    Purpose:
    - Define component items needed for parent
    - Specify quantity per parent unit
    - Track waste/scrap allowances
    - Categorize components (FABRIC, TRIM, ACCESSORY)

    Multi-tenant: All records isolated by client_id
    """

    __tablename__ = "capacity_bom_detail"
    __table_args__ = (
        Index("ix_capacity_bom_detail_header", "header_id"),
        Index("ix_capacity_bom_detail_component", "client_id", "component_item_code"),
        {"extend_existing": True},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Parent BOM header reference (indexed via composite index in __table_args__)
    header_id: Mapped[int] = mapped_column(Integer, ForeignKey("capacity_bom_header.id"), nullable=False)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Component identification (indexed via composite index in __table_args__)
    component_item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    component_description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Quantity per parent unit (allows fractional quantities)
    quantity_per: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=1.0)
    unit_of_measure: Mapped[Optional[str]] = mapped_column(String(20), default="EA")

    # Waste/scrap allowance percentage (e.g., 5.0 = 5%)
    waste_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), default=0)

    # Component categorization
    component_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # FABRIC/TRIM/etc.

    # Notes/metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationship back to header
    header = relationship("CapacityBOMHeader", back_populates="components")

    def required_quantity(self, parent_quantity: int) -> float:
        """
        Calculate required quantity including waste allowance.

        Args:
            parent_quantity: Number of parent units to produce

        Returns:
            Required component quantity including waste
        """
        base_qty = float(self.quantity_per or 1.0) * parent_quantity
        waste_factor = 1 + (float(self.waste_percentage or 0) / 100)
        return base_qty * waste_factor

    def __repr__(self):
        return f"<CapacityBOMDetail(component={self.component_item_code}, qty_per={self.quantity_per})>"
