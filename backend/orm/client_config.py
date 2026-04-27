"""
CLIENT_CONFIG table ORM schema (SQLAlchemy)
Client-level KPI calculation configuration overrides
Implements Phase 7.2: Client-Level Calculation Overrides
Implements Phase 10: Flexible Workflow Foundation
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


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
    config_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to CLIENT
    client_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("CLIENT.client_id"), nullable=False, unique=True, index=True
    )

    # OTD Configuration
    otd_mode: Mapped[OTDMode] = mapped_column(
        SQLEnum(OTDMode, values_callable=lambda x: [e.value for e in x]), nullable=False, default=OTDMode.STANDARD
    )

    # Efficiency Configuration
    default_cycle_time_hours: Mapped[Optional[float]] = mapped_column(Float, default=0.25)  # 15 min per unit
    efficiency_target_percent: Mapped[Optional[float]] = mapped_column(Float, default=85.0)  # 85% target

    # Quality Configuration
    quality_target_ppm: Mapped[Optional[float]] = mapped_column(Float, default=10000.0)  # 10,000 PPM target
    fpy_target_percent: Mapped[Optional[float]] = mapped_column(Float, default=95.0)  # 95% FPY target
    dpmo_opportunities_default: Mapped[Optional[int]] = mapped_column(Integer, default=1)

    # Availability Configuration
    availability_target_percent: Mapped[Optional[float]] = mapped_column(Float, default=90.0)

    # Performance Configuration
    performance_target_percent: Mapped[Optional[float]] = mapped_column(Float, default=95.0)

    # OEE Configuration (combined: Availability × Performance × Quality)
    oee_target_percent: Mapped[Optional[float]] = mapped_column(Float, default=85.0)

    # Absenteeism Configuration
    absenteeism_target_percent: Mapped[Optional[float]] = mapped_column(Float, default=3.0)  # lower is better

    # WIP Aging Configuration
    wip_aging_threshold_days: Mapped[Optional[int]] = mapped_column(Integer, default=7)
    wip_critical_threshold_days: Mapped[Optional[int]] = mapped_column(Integer, default=14)

    # ===========================================
    # Workflow Configuration (Phase 10)
    # ===========================================

    # Workflow statuses allowed for this client (JSON array)
    # Default: ["RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED"]
    # Client can customize to subset or reorder
    workflow_statuses: Mapped[Optional[str]] = mapped_column(
        Text, default='["RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED"]'
    )

    # Required status transitions (JSON object)
    # Format: {"TO_STATUS": ["ALLOWED_FROM_STATUS_1", "ALLOWED_FROM_STATUS_2"]}
    # Default allows standard linear flow with hold/cancel from any
    workflow_transitions: Mapped[Optional[str]] = mapped_column(
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
    workflow_optional_statuses: Mapped[Optional[str]] = mapped_column(Text, default='["SHIPPED", "DEMOTED"]')

    # When to close the order: "at_shipment", "at_client_receipt", "at_completion", "manual"
    workflow_closure_trigger: Mapped[Optional[str]] = mapped_column(String(30), default="at_shipment")

    # Workflow version for future migrations
    workflow_version: Mapped[Optional[int]] = mapped_column(Integer, default=1)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationship to Client (optional, for eager loading)
    # client = relationship("Client", back_populates="config")
