"""
Alert ORM models for SQLAlchemy
Stores alerts and alert configurations
"""
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, JSON, Boolean, Integer
from sqlalchemy.sql import func
from backend.database import Base


class Alert(Base):
    """ALERT table - Stores generated alerts"""
    __tablename__ = "ALERT"
    __table_args__ = {"extend_existing": True}

    # Primary key
    alert_id = Column(String(50), primary_key=True, index=True)

    # Classification
    category = Column(String(30), nullable=False, index=True)  # otd, quality, efficiency, etc.
    severity = Column(String(20), nullable=False, index=True)  # info, warning, critical, urgent
    status = Column(String(20), nullable=False, default='active', index=True)

    # Content
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=True)

    # References
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=True, index=True)
    kpi_key = Column(String(50), nullable=True, index=True)
    work_order_id = Column(String(50), ForeignKey("WORK_ORDER.work_order_id"), nullable=True, index=True)

    # Values
    current_value = Column(Float, nullable=True)
    threshold_value = Column(Float, nullable=True)
    predicted_value = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)

    # Additional context (renamed from 'metadata' which is reserved in SQLAlchemy)
    alert_metadata = Column(JSON, nullable=True)

    # Lifecycle tracking
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(50), ForeignKey("USER.user_id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(50), ForeignKey("USER.user_id"), nullable=True)
    resolution_notes = Column(Text, nullable=True)


class AlertConfig(Base):
    """ALERT_CONFIG table - Alert settings per client or global"""
    __tablename__ = "ALERT_CONFIG"
    __table_args__ = {"extend_existing": True}

    # Primary key
    config_id = Column(String(50), primary_key=True, index=True)

    # Client reference (NULL = global default)
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=True, index=True)

    # Alert type
    alert_type = Column(String(30), nullable=False, index=True)

    # Configuration
    enabled = Column(Boolean, default=True)
    warning_threshold = Column(Float, nullable=True)
    critical_threshold = Column(Float, nullable=True)

    # Notification settings
    notification_email = Column(Boolean, default=True)
    notification_sms = Column(Boolean, default=False)

    # Check frequency
    check_frequency_minutes = Column(Integer, default=60)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AlertHistory(Base):
    """ALERT_HISTORY table - Historical accuracy tracking for predictions"""
    __tablename__ = "ALERT_HISTORY"
    __table_args__ = {"extend_existing": True}

    # Primary key
    history_id = Column(String(50), primary_key=True, index=True)

    # Reference to original alert
    alert_id = Column(String(50), ForeignKey("ALERT.alert_id"), nullable=False, index=True)

    # Prediction vs Actual
    predicted_value = Column(Float, nullable=True)
    actual_value = Column(Float, nullable=True)
    prediction_date = Column(DateTime, nullable=False)
    actual_date = Column(DateTime, nullable=True)

    # Accuracy metrics
    was_accurate = Column(Boolean, nullable=True)  # True if prediction was correct
    error_percent = Column(Float, nullable=True)  # % difference

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
