"""
DEFECT_DETAIL table ORM schema (SQLAlchemy)
Detailed defect categorization for quality analysis
Source: 05-Phase4_Quality_Inventory.csv lines 28-37

NOTE: defect_type is now a free-form string validated against DEFECT_TYPE_CATALOG.
Each client has their own set of valid defect types defined in the catalog.
The DefectType enum is kept for backward compatibility but is DEPRECATED.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base
import enum


class DefectType(str, enum.Enum):
    """
    DEPRECATED: Use DEFECT_TYPE_CATALOG for client-specific defect types.
    This enum is kept only for backward compatibility with existing data.
    New defect entries should use defect_type values from the client's catalog.
    """

    STITCHING = "Stitching"
    FABRIC_DEFECT = "Fabric Defect"
    MEASUREMENT = "Measurement"
    COLOR_SHADE = "Color Shade"
    PILLING = "Pilling"
    HOLE_TEAR = "Hole/Tear"
    STAIN = "Stain"
    OTHER = "Other"


class DefectDetail(Base):
    """DEFECT_DETAIL table - Granular defect tracking"""

    __tablename__ = "DEFECT_DETAIL"
    __table_args__ = {"extend_existing": True}

    # Primary key
    defect_detail_id = Column(String(50), primary_key=True)

    # Parent quality entry
    quality_entry_id = Column(String(50), ForeignKey("QUALITY_ENTRY.quality_entry_id"), nullable=False, index=True)

    # Multi-tenant isolation (HIGH SECURITY FIX)
    client_id_fk = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Defect classification - NOW uses client-specific catalog (String, not Enum)
    # Validated against DEFECT_TYPE_CATALOG entries for the client
    defect_type = Column(String(100), nullable=False, index=True)
    defect_category = Column(String(100))  # Sub-category
    defect_count = Column(Integer, nullable=False)

    # Defect details
    severity = Column(String(20))  # CRITICAL, MAJOR, MINOR
    location = Column(String(255))  # Where on the product
    description = Column(Text)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
