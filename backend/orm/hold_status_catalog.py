"""
Client-specific Hold Status Catalog
Allows each client to define their own hold status values for approval workflows.
Replaces hardcoded HoldStatus enum with configurable per-client catalog.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.sql import func

from backend.database import Base


class HoldStatusCatalog(Base):
    """
    Client-specific hold status definitions.
    Each client can have their own set of statuses appropriate for their workflow.
    """

    __tablename__ = "HOLD_STATUS_CATALOG"
    __table_args__ = (
        UniqueConstraint("client_id", "status_code", name="uq_hold_status_client_code"),
        {"extend_existing": True},
    )

    # Primary key — auto-increment integer
    catalog_id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant: each status belongs to a specific client
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Status definition
    status_code = Column(String(50), nullable=False)  # e.g. "ON_HOLD", "PENDING_HOLD_APPROVAL"
    display_name = Column(String(100), nullable=False)  # e.g. "On Hold", "Pending Hold Approval"

    # Flags
    is_default = Column(Boolean, default=True, nullable=False)  # Seeded by system vs custom
    is_active = Column(Boolean, default=True, nullable=False)

    # UI ordering
    sort_order = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    def __repr__(self):
        return f"<HoldStatusCatalog {self.client_id}:{self.status_code}>"
