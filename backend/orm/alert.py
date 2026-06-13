"""
Alert ORM models for SQLAlchemy
Stores alerts and alert configurations
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class Alert(Base):
    """ALERT table - Stores generated alerts"""

    __tablename__ = "ALERT"
    __table_args__ = {"extend_existing": True}

    # Primary key
    alert_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)

    # Classification
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # otd/quality/efficiency/etc.
    severity: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # info/warning/critical/urgent
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)

    # Content
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # References
    client_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("CLIENT.client_id"), nullable=True, index=True
    )
    kpi_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    work_order_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("WORK_ORDER.work_order_id"), nullable=True, index=True
    )

    # Values
    current_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    threshold_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    predicted_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Additional context (renamed from 'metadata' which is reserved in SQLAlchemy)
    alert_metadata: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)

    # Lifecycle tracking
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("USER.user_id"), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("USER.user_id"), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AlertConfig(Base):
    """ALERT_CONFIG table - Alert settings per client or global"""

    __tablename__ = "ALERT_CONFIG"
    __table_args__ = {"extend_existing": True}

    # Primary key
    config_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)

    # Client reference (NULL = global default)
    client_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("CLIENT.client_id"), nullable=True, index=True
    )

    # Alert type
    alert_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # Configuration
    enabled: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    warning_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    critical_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Notification settings
    notification_email: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    notification_sms: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)

    # Check frequency
    check_frequency_minutes: Mapped[Optional[int]] = mapped_column(Integer, default=60)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class AlertHistory(Base):
    """ALERT_HISTORY table - Historical accuracy tracking for predictions"""

    __tablename__ = "ALERT_HISTORY"
    __table_args__ = {"extend_existing": True}

    # Primary key
    history_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)

    # Reference to original alert
    alert_id: Mapped[str] = mapped_column(String(50), ForeignKey("ALERT.alert_id"), nullable=False, index=True)

    # Prediction vs Actual
    predicted_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    actual_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    prediction_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Accuracy metrics
    was_accurate: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)  # True if prediction was correct
    error_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # % difference

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
