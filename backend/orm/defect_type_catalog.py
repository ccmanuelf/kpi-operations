"""
Client-specific Defect Type Catalog
Allows each client to define their own defect types based on their industry
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database import Base


class DefectTypeCatalog(Base):
    """
    Client-specific defect type definitions
    Each client can have their own set of defect types appropriate for their industry
    """

    __tablename__ = "DEFECT_TYPE_CATALOG"
    __table_args__ = {"extend_existing": True}

    # Primary key
    defect_type_id: Mapped[str] = mapped_column(String(50), primary_key=True)

    # Multi-tenant: Each defect type belongs to a specific client
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Defect type definition
    defect_code: Mapped[str] = mapped_column(String(20), nullable=False)  # Short code like "SOLDER_DEF"
    defect_name: Mapped[str] = mapped_column(String(100), nullable=False)  # Display name like "Solder Defect"
    description: Mapped[Optional[str]] = mapped_column(Text)  # Detailed description for training/reference

    # Categorization
    category: Mapped[Optional[str]] = mapped_column(String(50))  # "Assembly", "Material", "Process", etc.
    severity_default: Mapped[Optional[str]] = mapped_column(String(20), default="MAJOR")  # CRITICAL/MAJOR/MINOR

    # For reporting/analytics
    industry_standard_code: Mapped[Optional[str]] = mapped_column(String(50))  # Optional industry standards

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[Optional[int]] = mapped_column(Integer, default=0)  # For UI display ordering

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, onupdate=func.now())

    # Relationships
    client = relationship("Client", back_populates="defect_types")

    def __repr__(self) -> str:
        return f"<DefectTypeCatalog {self.defect_code}: {self.defect_name}>"
