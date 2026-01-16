"""
CRUD operations for User Preferences
Dashboard customization and widget configuration management
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
import json
import logging

from backend.schemas.user_preferences import UserPreferences, DashboardWidgetDefaults
from backend.schemas.user import User
from backend.models.preferences import (
    DashboardPreferences,
    DashboardWidgetConfig,
    DashboardPreferencesUpdate,
    WidgetDefaultResponse
)

logger = logging.getLogger(__name__)

# Default widgets when no role defaults exist
FALLBACK_DEFAULT_WIDGETS = [
    DashboardWidgetConfig(
        widget_key="production_summary",
        widget_name="Production Summary",
        widget_order=0,
        is_visible=True,
        custom_config={"chart_type": "bar", "time_range": "7d"}
    ),
    DashboardWidgetConfig(
        widget_key="quality_metrics",
        widget_name="Quality Metrics",
        widget_order=1,
        is_visible=True,
        custom_config={"show_trend": True}
    ),
    DashboardWidgetConfig(
        widget_key="attendance_overview",
        widget_name="Attendance Overview",
        widget_order=2,
        is_visible=True,
        custom_config=None
    ),
    DashboardWidgetConfig(
        widget_key="downtime_analysis",
        widget_name="Downtime Analysis",
        widget_order=3,
        is_visible=True,
        custom_config={"chart_type": "pie"}
    )
]


def get_user_dashboard_preferences(
    db: Session,
    user_id: str
) -> tuple[Optional[int], DashboardPreferences]:
    """
    Get dashboard preferences for a user
    Returns existing preferences or creates default based on fallback

    Args:
        db: Database session
        user_id: User ID to retrieve preferences for

    Returns:
        Tuple of (preference_id or None, DashboardPreferences)
    """
    # Query existing preferences
    preference = db.query(UserPreferences).filter(
        and_(
            UserPreferences.user_id == user_id,
            UserPreferences.preference_type == "dashboard",
            UserPreferences.preference_key == "main",
            UserPreferences.is_active == True
        )
    ).first()

    if preference and preference.preference_value:
        try:
            # Parse stored JSON preference
            pref_data = json.loads(preference.preference_value)
            return preference.preference_id, DashboardPreferences(**pref_data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse preferences for user {user_id}: {e}")

    # Return default preferences if none exist
    default_prefs = DashboardPreferences(
        layout="grid",
        widgets=FALLBACK_DEFAULT_WIDGETS,
        theme="light",
        auto_refresh=0,
        default_time_range="7d"
    )

    return None, default_prefs


def get_user_dashboard_preferences_full(
    db: Session,
    user_id: str
) -> tuple[Optional[UserPreferences], DashboardPreferences]:
    """
    Get full preference record with dashboard preferences

    Args:
        db: Database session
        user_id: User ID to retrieve preferences for

    Returns:
        Tuple of (UserPreferences record or None, DashboardPreferences)
    """
    preference = db.query(UserPreferences).filter(
        and_(
            UserPreferences.user_id == user_id,
            UserPreferences.preference_type == "dashboard",
            UserPreferences.preference_key == "main",
            UserPreferences.is_active == True
        )
    ).first()

    if preference and preference.preference_value:
        try:
            pref_data = json.loads(preference.preference_value)
            return preference, DashboardPreferences(**pref_data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse preferences for user {user_id}: {e}")

    # Return default preferences
    default_prefs = DashboardPreferences(
        layout="grid",
        widgets=FALLBACK_DEFAULT_WIDGETS,
        theme="light",
        auto_refresh=0,
        default_time_range="7d"
    )

    return preference, default_prefs


def save_user_dashboard_preferences(
    db: Session,
    user_id: str,
    preferences: DashboardPreferences
) -> UserPreferences:
    """
    Save or update dashboard preferences for a user

    Args:
        db: Database session
        user_id: User ID to save preferences for
        preferences: DashboardPreferences to save

    Returns:
        Updated or created UserPreferences record
    """
    # Serialize preferences to JSON
    pref_json = preferences.model_dump_json()

    # Check for existing preference
    existing = db.query(UserPreferences).filter(
        and_(
            UserPreferences.user_id == user_id,
            UserPreferences.preference_type == "dashboard",
            UserPreferences.preference_key == "main"
        )
    ).first()

    if existing:
        # Update existing preference
        existing.preference_value = pref_json
        existing.is_active = True
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        logger.info(f"Updated dashboard preferences for user {user_id}")
        return existing

    # Create new preference
    new_preference = UserPreferences(
        user_id=user_id,
        preference_type="dashboard",
        preference_key="main",
        preference_value=pref_json,
        is_active=True
    )

    db.add(new_preference)
    db.commit()
    db.refresh(new_preference)
    logger.info(f"Created dashboard preferences for user {user_id}")

    return new_preference


def update_user_dashboard_preferences(
    db: Session,
    user_id: str,
    updates: DashboardPreferencesUpdate
) -> UserPreferences:
    """
    Partially update dashboard preferences (PATCH semantics)

    Args:
        db: Database session
        user_id: User ID to update preferences for
        updates: Partial update data

    Returns:
        Updated UserPreferences record
    """
    # Get current preferences
    _, current_prefs = get_user_dashboard_preferences(db, user_id)

    # Apply updates only for provided fields
    update_data = updates.model_dump(exclude_unset=True, exclude_none=True)

    if 'layout' in update_data:
        current_prefs.layout = update_data['layout']
    if 'widgets' in update_data:
        current_prefs.widgets = update_data['widgets']
    if 'theme' in update_data:
        current_prefs.theme = update_data['theme']
    if 'auto_refresh' in update_data:
        current_prefs.auto_refresh = update_data['auto_refresh']
    if 'default_time_range' in update_data:
        current_prefs.default_time_range = update_data['default_time_range']

    # Save updated preferences
    return save_user_dashboard_preferences(db, user_id, current_prefs)


def get_role_default_widgets(
    db: Session,
    role: str
) -> List[WidgetDefaultResponse]:
    """
    Get default widget configurations for a specific role

    Args:
        db: Database session
        role: User role to get defaults for

    Returns:
        List of WidgetDefaultResponse for the role
    """
    defaults = db.query(DashboardWidgetDefaults).filter(
        DashboardWidgetDefaults.role == role.lower()
    ).order_by(
        DashboardWidgetDefaults.widget_order
    ).all()

    result = []
    for default in defaults:
        # Parse default_config JSON if present
        config_dict = None
        if default.default_config:
            try:
                config_dict = json.loads(default.default_config)
            except json.JSONDecodeError:
                config_dict = None

        result.append(WidgetDefaultResponse(
            config_id=default.config_id,
            role=default.role,
            widget_key=default.widget_key,
            widget_name=default.widget_name,
            widget_order=default.widget_order,
            is_visible=default.is_visible,
            default_config=config_dict
        ))

    return result


def reset_to_role_defaults(
    db: Session,
    user_id: str,
    role: str
) -> tuple[DashboardPreferences, int]:
    """
    Reset user dashboard preferences to role defaults

    Args:
        db: Database session
        user_id: User ID to reset preferences for
        role: Role to use for default widgets

    Returns:
        Tuple of (DashboardPreferences, widgets_applied_count)
    """
    # Get role defaults from database
    role_defaults = get_role_default_widgets(db, role)

    if role_defaults:
        # Convert role defaults to widget configs
        widgets = [
            DashboardWidgetConfig(
                widget_key=d.widget_key,
                widget_name=d.widget_name,
                widget_order=d.widget_order,
                is_visible=d.is_visible,
                custom_config=d.default_config
            )
            for d in role_defaults
        ]
    else:
        # Use fallback defaults if no role defaults configured
        widgets = FALLBACK_DEFAULT_WIDGETS
        logger.info(f"No role defaults for '{role}', using fallback defaults")

    # Create new preferences with defaults
    new_preferences = DashboardPreferences(
        layout="grid",
        widgets=widgets,
        theme="light",
        auto_refresh=0,
        default_time_range="7d"
    )

    # Save the reset preferences
    save_user_dashboard_preferences(db, user_id, new_preferences)

    return new_preferences, len(widgets)


def delete_user_preferences(
    db: Session,
    user_id: str,
    preference_type: Optional[str] = None
) -> int:
    """
    Soft delete user preferences (sets is_active = False)

    Args:
        db: Database session
        user_id: User ID to delete preferences for
        preference_type: Specific type to delete, or all if None

    Returns:
        Number of preferences deactivated
    """
    query = db.query(UserPreferences).filter(
        and_(
            UserPreferences.user_id == user_id,
            UserPreferences.is_active == True
        )
    )

    if preference_type:
        query = query.filter(UserPreferences.preference_type == preference_type)

    preferences = query.all()
    count = 0

    for pref in preferences:
        pref.is_active = False
        pref.updated_at = datetime.utcnow()
        count += 1

    db.commit()
    logger.info(f"Deactivated {count} preferences for user {user_id}")

    return count


def get_all_role_defaults(db: Session) -> dict:
    """
    Get all role defaults organized by role

    Args:
        db: Database session

    Returns:
        Dictionary mapping role names to their widget defaults
    """
    all_defaults = db.query(DashboardWidgetDefaults).order_by(
        DashboardWidgetDefaults.role,
        DashboardWidgetDefaults.widget_order
    ).all()

    result = {}
    for default in all_defaults:
        role = default.role
        if role not in result:
            result[role] = []

        config_dict = None
        if default.default_config:
            try:
                config_dict = json.loads(default.default_config)
            except json.JSONDecodeError:
                config_dict = None

        result[role].append(WidgetDefaultResponse(
            config_id=default.config_id,
            role=default.role,
            widget_key=default.widget_key,
            widget_name=default.widget_name,
            widget_order=default.widget_order,
            is_visible=default.is_visible,
            default_config=config_dict
        ))

    return result
