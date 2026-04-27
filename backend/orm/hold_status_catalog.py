"""
Client-specific Hold Status Catalog
Allows each client to define their own hold status values for approval workflows.
Replaces hardcoded HoldStatus enum with configurable per-client catalog.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
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
    catalog_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant: each status belongs to a specific client
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Status definition
    status_code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "ON_HOLD"
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "On Hold"

    # Flags
    is_default: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)  # Seeded vs custom
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # UI ordering
    sort_order: Mapped[Optional[int]] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    def __repr__(self):
        return f"<HoldStatusCatalog {self.client_id}:{self.status_code}>"
