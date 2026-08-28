"""
PART_OPPORTUNITIES table ORM schema (SQLAlchemy)
Defines opportunities per unit for DPMO calculation (KPI #5)
Source: 01-Core_DataEntities_Inventory.csv lines 71-75
"""

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class PartOpportunities(Base):
    """PART_OPPORTUNITIES table - DPMO calculation metadata"""

    __tablename__ = "PART_OPPORTUNITIES"
    __table_args__ = {"extend_existing": True}

    # Primary key
    part_number: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)

    # Multi-tenant isolation (MEDIUM SECURITY FIX)
    client_id_fk: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # DPMO calculation
    opportunities_per_unit: Mapped[int] = mapped_column(Integer, nullable=False)

    # Metadata
    part_description: Mapped[Optional[str]] = mapped_column(String(255))
    part_category: Mapped[Optional[str]] = mapped_column(String(100))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Soft delete (S1): DELETE endpoints set this False instead of removing the row.
    # Filtering is automatic — see backend/db/soft_delete_filter.py, declared in
    # backend/db/soft_delete_registry.py. Do NOT hand-filter on it.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
