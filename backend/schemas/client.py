"""
CLIENT table ORM schema (SQLAlchemy)
Multi-tenant foundation - ALL transactional tables reference this
Source: 01-Core_DataEntities_Inventory.csv lines 2-15
"""

from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base
import enum


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
    client_id = Column(String(50), primary_key=True, index=True)

    # Core identification
    client_name = Column(String(255), nullable=False, index=True)
    client_contact = Column(String(255))
    client_email = Column(String(255))
    client_phone = Column(String(50))
    location = Column(String(255))

    # Responsible parties (references to USER table)
    supervisor_id = Column(String(50))
    planner_id = Column(String(50))
    engineering_id = Column(String(50))

    # Business configuration
    client_type = Column(
        SQLEnum(ClientType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ClientType.PIECE_RATE,
    )
    timezone = Column(String(50), default="America/New_York")

    # Status
    is_active = Column(Integer, nullable=False, default=1)  # Boolean: 1=active, 0=inactive

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    defect_types = relationship("DefectTypeCatalog", back_populates="client", lazy="dynamic")
