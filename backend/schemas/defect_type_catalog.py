"""
Client-specific Defect Type Catalog
Allows each client to define their own defect types based on their industry
"""
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from backend.database import Base


class DefectTypeCatalog(Base):
    """
    Client-specific defect type definitions
    Each client can have their own set of defect types appropriate for their industry
    """
    __tablename__ = "DEFECT_TYPE_CATALOG"
    __table_args__ = {'extend_existing': True}

    # Primary key
    defect_type_id = Column(String(50), primary_key=True)

    # Multi-tenant: Each defect type belongs to a specific client
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Defect type definition
    defect_code = Column(String(20), nullable=False)  # Short code like "SOLDER_DEF"
    defect_name = Column(String(100), nullable=False)  # Display name like "Solder Defect"
    description = Column(Text)  # Detailed description for training/reference

    # Categorization
    category = Column(String(50))  # Group defects: "Assembly", "Material", "Process", etc.
    severity_default = Column(String(20), default="MAJOR")  # CRITICAL, MAJOR, MINOR

    # For reporting/analytics
    industry_standard_code = Column(String(50))  # Optional: Maps to industry standards (e.g., IPC codes for electronics)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0)  # For UI display ordering

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationships
    client = relationship("Client", back_populates="defect_types")

    def __repr__(self):
        return f"<DefectTypeCatalog {self.defect_code}: {self.defect_name}>"
