"""
PART_OPPORTUNITIES table ORM schema (SQLAlchemy)
Defines opportunities per unit for DPMO calculation (KPI #5)
Source: 01-Core_DataEntities_Inventory.csv lines 71-75
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from backend.database import Base


class PartOpportunities(Base):
    """PART_OPPORTUNITIES table - DPMO calculation metadata"""
    __tablename__ = "PART_OPPORTUNITIES"
    __table_args__ = {"extend_existing": True}

    # Primary key
    part_number = Column(String(100), primary_key=True, index=True)

    # Multi-tenant isolation (MEDIUM SECURITY FIX)
    client_id_fk = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # DPMO calculation
    opportunities_per_unit = Column(Integer, nullable=False)

    # Metadata
    part_description = Column(String(255))
    part_category = Column(String(100))
    notes = Column(Text)
