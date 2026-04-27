"""
User Preferences ORM schemas (SQLAlchemy)
Dashboard customization and widget configuration storage
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class UserPreferences(Base):
    """
    USER_PREFERENCES table ORM
    Stores user-specific preferences including dashboard configurations

    Preference Types:
    - dashboard: Dashboard layout and widget configurations
    - theme: UI theme preferences
    - notifications: Notification settings
    """

    __tablename__ = "USER_PREFERENCES"
    __table_args__ = {"extend_existing": True}

    preference_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    preference_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    preference_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    preference_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DashboardWidgetDefaults(Base):
    """
    DASHBOARD_WIDGET_DEFAULTS table ORM
    Stores default widget configurations by user role

    Role-based defaults provide sensible starting configurations
    for different user types (admin, supervisor, operator, etc.)
    """

    __tablename__ = "DASHBOARD_WIDGET_DEFAULTS"
    __table_args__ = {"extend_existing": True}

    config_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    widget_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    widget_name: Mapped[str] = mapped_column(String(100), nullable=False)
    widget_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
