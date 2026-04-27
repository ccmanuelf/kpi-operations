"""
FLOATING_POOL table ORM schema (SQLAlchemy)
Tracks shared resources across multiple clients
Source: 01-Core_DataEntities_Inventory.csv lines 54-60
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class FloatingPool(Base):
    """FLOATING_POOL table - Shared resource availability tracking"""

    __tablename__ = "FLOATING_POOL"
    __table_args__ = {"extend_existing": True}

    # Primary key
    pool_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL (nullable for shared resources)
    client_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("CLIENT.client_id"), nullable=True, index=True
    )

    # Employee reference
    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("EMPLOYEE.employee_id"), nullable=False, index=True)

    # Availability tracking
    available_from: Mapped[Optional[datetime]] = mapped_column(DateTime)
    available_to: Mapped[Optional[datetime]] = mapped_column(DateTime)
    current_assignment: Mapped[Optional[str]] = mapped_column(String(255))  # Current client_id or NULL if available

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
