"""
DEFECT_DETAIL table ORM schema (SQLAlchemy)
Detailed defect categorization for quality analysis
Source: 05-Phase4_Quality_Inventory.csv lines 28-37

NOTE: defect_type is now a free-form string validated against DEFECT_TYPE_CATALOG.
Each client has their own set of valid defect types defined in the catalog.
The DefectType enum is kept for backward compatibility but is DEPRECATED.
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


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
    defect_detail_id: Mapped[str] = mapped_column(String(50), primary_key=True)

    # Parent quality entry
    quality_entry_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("QUALITY_ENTRY.quality_entry_id"), nullable=False, index=True
    )

    # Multi-tenant isolation (HIGH SECURITY FIX)
    client_id_fk: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Defect classification - NOW uses client-specific catalog (String, not Enum)
    # Validated against DEFECT_TYPE_CATALOG entries for the client
    defect_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    defect_category: Mapped[Optional[str]] = mapped_column(String(100))  # Sub-category
    defect_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Defect details
    severity: Mapped[Optional[str]] = mapped_column(String(20))  # CRITICAL, MAJOR, MINOR
    location: Mapped[Optional[str]] = mapped_column(String(255))  # Where on the product
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Soft delete (S1): DELETE endpoints set this False instead of removing the row.
    # Filtering is automatic — see backend/db/soft_delete_filter.py, declared in
    # backend/db/soft_delete_registry.py. Do NOT hand-filter on it.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    # Who deleted it and when. Without these a soft-deleted row is
    # indistinguishable from one that was never active — worse than a hard
    # delete, which at least leaves an absence someone might notice.
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Deliberately NOT a FK, for the same reason AUDIT_ENTRY.actor_user_id is not:
    # this is a historical record of who acted, and it has to stay readable after
    # that user is renamed or deactivated — which is exactly when it is needed.
    # It also keeps the migration a plain ADD COLUMN: adding a FK constraint to an
    # existing SQLite table needs a batch table rebuild, on 37k rows across 11 tables.
    deleted_by: Mapped[Optional[str]] = mapped_column(String(50))

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
