"""
KPI_THRESHOLD table ORM schema (SQLAlchemy)
Stores KPI target thresholds per client or global defaults
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class KPIThreshold(Base):
    """KPI_THRESHOLD table - Client-specific or global KPI targets"""

    __tablename__ = "KPI_THRESHOLD"
    __table_args__ = (UniqueConstraint("client_id", "kpi_key", name="uq_client_kpi"), {"extend_existing": True})

    # Primary key
    threshold_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)

    # Client reference (NULL = global default)
    client_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("CLIENT.client_id"), nullable=True, index=True
    )

    # KPI identification
    kpi_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # e.g., 'efficiency', 'quality', 'oee'

    # Threshold values
    target_value: Mapped[float] = mapped_column(Float, nullable=False)  # Target value
    warning_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Warning level
    critical_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Critical level

    # Metadata
    unit: Mapped[Optional[str]] = mapped_column(String(20), default="%")  # %, ppm, days, hrs
    higher_is_better: Mapped[Optional[str]] = mapped_column(String(1), default="Y")  # Y/N - direction for status

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
