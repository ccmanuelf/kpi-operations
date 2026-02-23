"""
Client-specific Hold Reason Catalog
Allows each client to define their own hold reason values.
Replaces hardcoded HoldReason enum with configurable per-client catalog.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.sql import func

from backend.database import Base


class HoldReasonCatalog(Base):
    """
    Client-specific hold reason definitions.
    Each client can have their own set of reasons appropriate for their industry.
    """

    __tablename__ = "HOLD_REASON_CATALOG"
    __table_args__ = (
        UniqueConstraint("client_id", "reason_code", name="uq_hold_reason_client_code"),
        {"extend_existing": True},
    )

    # Primary key — auto-increment integer
    catalog_id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant: each reason belongs to a specific client
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Reason definition
    reason_code = Column(String(50), nullable=False)  # e.g. "QUALITY_ISSUE", "MATERIAL_SHORTAGE"
    display_name = Column(String(100), nullable=False)  # e.g. "Quality Issue", "Material Shortage"

    # Flags
    is_default = Column(Boolean, default=True, nullable=False)  # Seeded by system vs custom
    is_active = Column(Boolean, default=True, nullable=False)

    # UI ordering
    sort_order = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    def __repr__(self):
        return f"<HoldReasonCatalog {self.client_id}:{self.reason_code}>"
