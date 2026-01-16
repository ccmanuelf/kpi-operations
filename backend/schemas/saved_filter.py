"""
Saved Filter ORM schemas (SQLAlchemy)
User-specific filter configurations for KPI dashboards
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class SavedFilter(Base):
    """
    SAVED_FILTER table - User-specific saved filter configurations

    Stores reusable filter presets for KPI dashboards including:
    - Client selection
    - Date ranges (relative or absolute)
    - Shift/product filters
    - KPI thresholds

    SECURITY: Filters are user-specific and not shared between users
    """
    __tablename__ = "SAVED_FILTER"
    __table_args__ = {"extend_existing": True}

    # Primary key
    filter_id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # User ownership - CRITICAL for isolation
    user_id = Column(String(50), ForeignKey('USER.user_id'), nullable=False, index=True)

    # Filter identification
    filter_name = Column(String(100), nullable=False)
    filter_type = Column(String(50), nullable=False, index=True)  # dashboard, production, quality, attendance, etc.

    # Filter configuration (JSON string)
    # Contains: client_id, date_range, shift_ids, product_ids, kpi_thresholds
    filter_config = Column(Text, nullable=False)

    # Default filter flag (one per filter_type per user)
    is_default = Column(Boolean, nullable=False, default=False, index=True)

    # Usage tracking
    usage_count = Column(Integer, nullable=False, default=0)
    last_used_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class FilterHistory(Base):
    """
    FILTER_HISTORY table - Track recently applied filter configurations

    Stores temporary filter history for quick access to recent configurations
    without requiring explicit save. Limited to most recent entries per user.

    SECURITY: History is user-specific
    """
    __tablename__ = "FILTER_HISTORY"
    __table_args__ = {"extend_existing": True}

    # Primary key
    history_id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    # User ownership
    user_id = Column(String(50), ForeignKey('USER.user_id'), nullable=False, index=True)

    # Filter configuration (JSON string)
    filter_config = Column(Text, nullable=False)

    # Application timestamp
    applied_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
