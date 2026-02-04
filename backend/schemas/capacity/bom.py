"""
Capacity BOM - Bill of Materials
Two-table structure: Header (parent items) and Detail (components).
Used for MRP explosion and component availability checking.
"""
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, Text, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import DateTime
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
        Index('ix_capacity_bom_header_parent', 'client_id', 'parent_item_code'),
        Index('ix_capacity_bom_header_style', 'client_id', 'style_code'),
        {"extend_existing": True}
    )

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # Parent item identification (indexed via composite index in __table_args__)
    parent_item_code = Column(String(50), nullable=False)
    parent_item_description = Column(String(200), nullable=True)

    # Link to style (indexed via composite index in __table_args__)
    style_code = Column(String(50), nullable=True)

    # Revision tracking
    revision = Column(String(20), default="1.0")

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Notes/metadata
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationship to details
    components = relationship(
        "CapacityBOMDetail",
        back_populates="header",
        cascade="all, delete-orphan",
        lazy="dynamic"
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
        Index('ix_capacity_bom_detail_header', 'header_id'),
        Index('ix_capacity_bom_detail_component', 'client_id', 'component_item_code'),
        {"extend_existing": True}
    )

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Parent BOM header reference (indexed via composite index in __table_args__)
    header_id = Column(Integer, ForeignKey("capacity_bom_header.id"), nullable=False)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # Component identification (indexed via composite index in __table_args__)
    component_item_code = Column(String(50), nullable=False)
    component_description = Column(String(200), nullable=True)

    # Quantity per parent unit (allows fractional quantities)
    quantity_per = Column(Numeric(12, 6), nullable=False, default=1.0)
    unit_of_measure = Column(String(20), default="EA")

    # Waste/scrap allowance percentage (e.g., 5.0 = 5%)
    waste_percentage = Column(Numeric(5, 2), default=0)

    # Component categorization
    component_type = Column(String(50), nullable=True)  # FABRIC, TRIM, ACCESSORY, PACKAGING, etc.

    # Notes/metadata
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

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
