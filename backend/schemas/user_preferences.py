"""
User Preferences ORM schemas (SQLAlchemy)
Dashboard customization and widget configuration storage
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
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

    preference_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False, index=True)
    preference_type = Column(String(50), nullable=False, index=True)
    preference_key = Column(String(100), nullable=False, index=True)
    preference_value = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
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

    config_id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String(20), nullable=False, index=True)
    widget_key = Column(String(50), nullable=False, index=True)
    widget_name = Column(String(100), nullable=False)
    widget_order = Column(Integer, nullable=False, default=0)
    is_visible = Column(Boolean, nullable=False, default=True)
    default_config = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
