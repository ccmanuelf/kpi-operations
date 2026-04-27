"""
CLIENT table ORM schema (SQLAlchemy)
Multi-tenant foundation - ALL transactional tables reference this
Source: 01-Core_DataEntities_Inventory.csv lines 2-15
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database import Base


class ClientType(str, enum.Enum):
    """Client payment type"""

    HOURLY_RATE = "Hourly Rate"
    PIECE_RATE = "Piece Rate"
    HYBRID = "Hybrid"
    SERVICE = "Service"
    OTHER = "Other"


class Client(Base):
    """CLIENT table - Multi-tenant isolation foundation"""

    __tablename__ = "CLIENT"
    __table_args__ = {"extend_existing": True}

    # Primary key
    client_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)

    # Core identification
    client_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    client_contact: Mapped[Optional[str]] = mapped_column(String(255))
    client_email: Mapped[Optional[str]] = mapped_column(String(255))
    client_phone: Mapped[Optional[str]] = mapped_column(String(50))
    location: Mapped[Optional[str]] = mapped_column(String(255))

    # Responsible parties (references to USER table)
    supervisor_id: Mapped[Optional[str]] = mapped_column(String(50))
    planner_id: Mapped[Optional[str]] = mapped_column(String(50))
    engineering_id: Mapped[Optional[str]] = mapped_column(String(50))

    # Business configuration
    client_type: Mapped[ClientType] = mapped_column(
        SQLEnum(ClientType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ClientType.PIECE_RATE,
    )
    timezone: Mapped[Optional[str]] = mapped_column(String(50), default="America/New_York")

    # Status (1=active, 0=inactive — stored as int for legacy compatibility)
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    defect_types = relationship("DefectTypeCatalog", back_populates="client", lazy="dynamic")
