"""
Preferences Service
Thin service layer wrapping User Preferences CRUD operations.
Routes should import from this module instead of backend.crud.preferences directly.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from backend.crud.preferences import (
    get_user_dashboard_preferences,
    get_user_dashboard_preferences_full,
    save_user_dashboard_preferences,
    update_user_dashboard_preferences,
    get_role_default_widgets,
    reset_to_role_defaults,
    delete_user_preferences,
    get_all_role_defaults,
    FALLBACK_DEFAULT_WIDGETS,
)


def get_dashboard_preferences(db: Session, user_id: str):
    """Get dashboard preferences for a user."""
    return get_user_dashboard_preferences(db, user_id)


def get_dashboard_preferences_full(db: Session, user_id: str):
    """Get full dashboard preferences for a user."""
    return get_user_dashboard_preferences_full(db, user_id)


def save_dashboard_preferences(db: Session, user_id: str, preferences):
    """Save dashboard preferences for a user."""
    return save_user_dashboard_preferences(db, user_id, preferences)


def update_dashboard_preferences(db: Session, user_id: str, updates: dict):
    """Update dashboard preferences for a user."""
    return update_user_dashboard_preferences(db, user_id, updates)


def get_default_widgets_for_role(db: Session, role: str):
    """Get default widgets for a role."""
    return get_role_default_widgets(db, role)


def reset_preferences_to_defaults(db: Session, user_id: str, role: str):
    """Reset user preferences to role defaults."""
    return reset_to_role_defaults(db, user_id, role)


def delete_preferences(db: Session, user_id: str, preference_type: Optional[str] = None) -> int:
    """Delete user preferences."""
    return delete_user_preferences(db, user_id, preference_type)


def get_all_defaults(db: Session) -> dict:
    """Get all role defaults."""
    return get_all_role_defaults(db)


def get_fallback_widgets():
    """Get fallback default widgets when no DB defaults exist."""
    return FALLBACK_DEFAULT_WIDGETS
