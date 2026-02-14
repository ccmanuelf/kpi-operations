"""
KPI_THRESHOLD table ORM schema (SQLAlchemy)
Stores KPI target thresholds per client or global defaults
"""

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from backend.database import Base


class KPIThreshold(Base):
    """KPI_THRESHOLD table - Client-specific or global KPI targets"""

    __tablename__ = "KPI_THRESHOLD"
    __table_args__ = (UniqueConstraint("client_id", "kpi_key", name="uq_client_kpi"), {"extend_existing": True})

    # Primary key
    threshold_id = Column(String(50), primary_key=True, index=True)

    # Client reference (NULL = global default)
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=True, index=True)

    # KPI identification
    kpi_key = Column(String(50), nullable=False, index=True)  # e.g., 'efficiency', 'quality', 'oee'

    # Threshold values
    target_value = Column(Float, nullable=False)  # Target value
    warning_threshold = Column(Float, nullable=True)  # Warning level (e.g., 80% of target)
    critical_threshold = Column(Float, nullable=True)  # Critical level (e.g., 60% of target)

    # Metadata
    unit = Column(String(20), default="%")  # %, ppm, days, hrs
    higher_is_better = Column(String(1), default="Y")  # Y/N - direction for status calculation

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
