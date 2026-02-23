"""
CLIENT_CONFIG table ORM schema (SQLAlchemy)
Client-level KPI calculation configuration overrides
Implements Phase 7.2: Client-Level Calculation Overrides
Implements Phase 10: Flexible Workflow Foundation
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from backend.database import Base
import enum


class OTDMode(str, enum.Enum):
    """OTD calculation mode"""

    STANDARD = "STANDARD"  # Standard OTD (all orders)
    TRUE = "TRUE"  # TRUE-OTD (only complete orders)
    BOTH = "BOTH"  # Show both metrics


class ClientConfig(Base):
    """CLIENT_CONFIG table - Client-specific KPI calculation parameters"""

    __tablename__ = "CLIENT_CONFIG"
    __table_args__ = {"extend_existing": True}

    # Primary key
    config_id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to CLIENT
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, unique=True, index=True)

    # OTD Configuration
    otd_mode = Column(
        SQLEnum(OTDMode, values_callable=lambda x: [e.value for e in x]), nullable=False, default=OTDMode.STANDARD
    )

    # Efficiency Configuration
    default_cycle_time_hours = Column(Float, default=0.25)  # Default: 15 minutes per unit
    efficiency_target_percent = Column(Float, default=85.0)  # Default: 85% efficiency target

    # Quality Configuration
    quality_target_ppm = Column(Float, default=10000.0)  # Default: 10,000 PPM target
    fpy_target_percent = Column(Float, default=95.0)  # Default: 95% FPY target
    dpmo_opportunities_default = Column(Integer, default=1)  # Default opportunities per unit

    # Availability Configuration
    availability_target_percent = Column(Float, default=90.0)  # Default: 90% availability target

    # Performance Configuration
    performance_target_percent = Column(Float, default=95.0)  # Default: 95% performance target

    # OEE Configuration (combined: Availability × Performance × Quality)
    oee_target_percent = Column(Float, default=85.0)  # Default: 85% OEE target

    # Absenteeism Configuration
    absenteeism_target_percent = Column(Float, default=3.0)  # Default: 3% absenteeism target (lower is better)

    # WIP Aging Configuration
    wip_aging_threshold_days = Column(Integer, default=7)  # Default: 7 days before flagging as aged
    wip_critical_threshold_days = Column(Integer, default=14)  # Default: 14 days for critical aging

    # ===========================================
    # Workflow Configuration (Phase 10)
    # ===========================================

    # Workflow statuses allowed for this client (JSON array)
    # Default: ["RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED"]
    # Client can customize to subset or reorder
    workflow_statuses = Column(
        Text, default='["RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED"]'
    )

    # Required status transitions (JSON object)
    # Format: {"TO_STATUS": ["ALLOWED_FROM_STATUS_1", "ALLOWED_FROM_STATUS_2"]}
    # Default allows standard linear flow with hold/cancel from any
    workflow_transitions = Column(
        Text,
        default="""{
        "RELEASED": ["RECEIVED"],
        "IN_PROGRESS": ["RELEASED"],
        "COMPLETED": ["IN_PROGRESS"],
        "SHIPPED": ["COMPLETED"],
        "CLOSED": ["SHIPPED", "COMPLETED"],
        "ON_HOLD": ["RECEIVED", "RELEASED", "IN_PROGRESS"],
        "DEMOTED": ["RELEASED"],
        "CANCELLED": ["RECEIVED", "RELEASED", "IN_PROGRESS", "ON_HOLD", "DEMOTED"],
        "REJECTED": ["IN_PROGRESS", "COMPLETED"]
    }""",
    )

    # Optional statuses that can be skipped
    # Default: SHIPPED can be skipped if closure_trigger is "at_completion"
    workflow_optional_statuses = Column(Text, default='["SHIPPED", "DEMOTED"]')

    # When to close the order: "at_shipment", "at_client_receipt", "at_completion", "manual"
    workflow_closure_trigger = Column(String(30), default="at_shipment")

    # Workflow version for future migrations
    workflow_version = Column(Integer, default=1)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationship to Client (optional, for eager loading)
    # client = relationship("Client", back_populates="config")
