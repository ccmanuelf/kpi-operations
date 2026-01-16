"""
User Preferences API Routes
Dashboard customization and widget configuration endpoints

All endpoints require authentication via JWT token
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import json
import logging

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.models.preferences import (
    DashboardPreferences,
    DashboardPreferencesUpdate,
    PreferenceResponse,
    RoleDefaultsResponse,
    ResetPreferencesRequest,
    ResetPreferencesResponse,
    WidgetDefaultResponse
)
from backend.crud.preferences import (
    get_user_dashboard_preferences,
    get_user_dashboard_preferences_full,
    save_user_dashboard_preferences,
    update_user_dashboard_preferences,
    get_role_default_widgets,
    reset_to_role_defaults
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get(
    "/dashboard",
    response_model=PreferenceResponse,
    summary="Get Dashboard Preferences",
    description="""
    Retrieve the current user's dashboard preferences.

    Returns existing preferences if saved, or default preferences
    based on the user's role if none exist.

    **Response includes:**
    - Layout type (grid, list, compact)
    - Widget configurations with positions and visibility
    - Theme preference
    - Auto-refresh interval
    - Default time range for data displays

    **Authentication:** Required (JWT Bearer token)
    """,
    responses={
        200: {"description": "Dashboard preferences retrieved successfully"},
        401: {"description": "Not authenticated"},
        500: {"description": "Internal server error"}
    }
)
async def get_dashboard_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PreferenceResponse:
    """
    GET /api/preferences/dashboard - Get user's dashboard preferences
    """
    try:
        preference_record, preferences = get_user_dashboard_preferences_full(
            db, current_user.user_id
        )

        # If no saved preference exists, return defaults with placeholder metadata
        if preference_record is None:
            return PreferenceResponse(
                preference_id=0,
                user_id=current_user.user_id,
                preference_type="dashboard",
                preferences=preferences,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

        return PreferenceResponse(
            preference_id=preference_record.preference_id,
            user_id=preference_record.user_id,
            preference_type=preference_record.preference_type,
            preferences=preferences,
            created_at=preference_record.created_at,
            updated_at=preference_record.updated_at
        )

    except Exception as e:
        logger.error(f"Error retrieving dashboard preferences: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard preferences"
        )


@router.put(
    "/dashboard",
    response_model=PreferenceResponse,
    summary="Save Dashboard Preferences",
    description="""
    Save or update the current user's dashboard preferences.

    **Request body:**
    - `layout`: Dashboard layout type (grid, list, compact)
    - `widgets`: List of widget configurations
    - `theme`: Color theme (light, dark, system)
    - `auto_refresh`: Refresh interval in seconds (0 to disable)
    - `default_time_range`: Default time range (1d, 7d, 30d, 90d)

    **Widget configuration:**
    - `widget_key`: Unique identifier for the widget
    - `widget_name`: Display name
    - `widget_order`: Position in layout (0-indexed)
    - `is_visible`: Whether widget is displayed
    - `custom_config`: Widget-specific settings (optional)

    **Authentication:** Required (JWT Bearer token)
    """,
    responses={
        200: {"description": "Dashboard preferences saved successfully"},
        400: {"description": "Invalid preference data"},
        401: {"description": "Not authenticated"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"}
    }
)
async def save_dashboard_preferences(
    preferences: DashboardPreferences,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PreferenceResponse:
    """
    PUT /api/preferences/dashboard - Save dashboard preferences
    """
    try:
        preference_record = save_user_dashboard_preferences(
            db, current_user.user_id, preferences
        )

        logger.info(f"Saved dashboard preferences for user {current_user.user_id}")

        return PreferenceResponse(
            preference_id=preference_record.preference_id,
            user_id=preference_record.user_id,
            preference_type=preference_record.preference_type,
            preferences=preferences,
            created_at=preference_record.created_at,
            updated_at=preference_record.updated_at
        )

    except ValueError as e:
        logger.warning(f"Validation error saving preferences: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error saving dashboard preferences: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save dashboard preferences"
        )


@router.patch(
    "/dashboard",
    response_model=PreferenceResponse,
    summary="Partially Update Dashboard Preferences",
    description="""
    Partially update dashboard preferences (PATCH semantics).

    Only provided fields will be updated; other fields retain their current values.

    **Authentication:** Required (JWT Bearer token)
    """,
    responses={
        200: {"description": "Dashboard preferences updated successfully"},
        400: {"description": "Invalid preference data"},
        401: {"description": "Not authenticated"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"}
    }
)
async def patch_dashboard_preferences(
    updates: DashboardPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PreferenceResponse:
    """
    PATCH /api/preferences/dashboard - Partially update dashboard preferences
    """
    try:
        preference_record = update_user_dashboard_preferences(
            db, current_user.user_id, updates
        )

        # Re-fetch to get updated preferences
        _, preferences = get_user_dashboard_preferences(db, current_user.user_id)

        logger.info(f"Updated dashboard preferences for user {current_user.user_id}")

        return PreferenceResponse(
            preference_id=preference_record.preference_id,
            user_id=preference_record.user_id,
            preference_type=preference_record.preference_type,
            preferences=preferences,
            created_at=preference_record.created_at,
            updated_at=preference_record.updated_at
        )

    except ValueError as e:
        logger.warning(f"Validation error updating preferences: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating dashboard preferences: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update dashboard preferences"
        )


@router.get(
    "/defaults/{role}",
    response_model=RoleDefaultsResponse,
    summary="Get Role Default Widgets",
    description="""
    Get the default widget configurations for a specific role.

    **Available roles:**
    - admin
    - supervisor
    - operator
    - viewer

    Returns the default widgets that would be applied when a user
    of the specified role first accesses their dashboard or resets
    to defaults.

    **Authentication:** Required (JWT Bearer token)
    """,
    responses={
        200: {"description": "Role defaults retrieved successfully"},
        401: {"description": "Not authenticated"},
        404: {"description": "No defaults configured for role"},
        500: {"description": "Internal server error"}
    }
)
async def get_role_defaults(
    role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RoleDefaultsResponse:
    """
    GET /api/preferences/defaults/{role} - Get role default widgets
    """
    try:
        # Normalize role to lowercase
        role = role.lower()

        # Validate role
        valid_roles = ["admin", "supervisor", "operator", "viewer", "poweruser", "leader"]
        if role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
            )

        defaults = get_role_default_widgets(db, role)

        return RoleDefaultsResponse(
            role=role,
            widgets=defaults,
            total_widgets=len(defaults)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving role defaults: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve role defaults"
        )


@router.post(
    "/reset",
    response_model=ResetPreferencesResponse,
    summary="Reset to Role Defaults",
    description="""
    Reset dashboard preferences to the default configuration for a role.

    **Request body:**
    - `role` (optional): Role to reset to. If not provided, uses the current user's role.

    This will replace all current widget configurations with the defaults
    for the specified role.

    **Authentication:** Required (JWT Bearer token)
    """,
    responses={
        200: {"description": "Preferences reset successfully"},
        400: {"description": "Invalid role specified"},
        401: {"description": "Not authenticated"},
        500: {"description": "Internal server error"}
    }
)
async def reset_preferences(
    request: ResetPreferencesRequest = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ResetPreferencesResponse:
    """
    POST /api/preferences/reset - Reset preferences to role defaults
    """
    try:
        # Determine role to use
        if request and request.role:
            role = request.role.lower()
        else:
            # Use current user's role
            role = current_user.role.lower() if current_user.role else "operator"

        # Validate role
        valid_roles = ["admin", "supervisor", "operator", "viewer", "poweruser", "leader"]
        if role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
            )

        # Reset to defaults
        preferences, widgets_applied = reset_to_role_defaults(
            db, current_user.user_id, role
        )

        logger.info(
            f"Reset preferences for user {current_user.user_id} to role '{role}' defaults "
            f"({widgets_applied} widgets)"
        )

        return ResetPreferencesResponse(
            success=True,
            message=f"Preferences reset to {role} defaults successfully",
            reset_to_role=role,
            widgets_applied=widgets_applied,
            preferences=preferences
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting preferences: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset preferences"
        )


@router.get(
    "/defaults",
    response_model=RoleDefaultsResponse,
    summary="Get Current User's Role Defaults",
    description="""
    Get the default widget configurations for the current user's role.

    This is a convenience endpoint that automatically uses the
    authenticated user's role.

    **Authentication:** Required (JWT Bearer token)
    """,
    responses={
        200: {"description": "Role defaults retrieved successfully"},
        401: {"description": "Not authenticated"},
        500: {"description": "Internal server error"}
    }
)
async def get_my_role_defaults(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> RoleDefaultsResponse:
    """
    GET /api/preferences/defaults - Get current user's role defaults
    """
    try:
        role = current_user.role.lower() if current_user.role else "operator"

        defaults = get_role_default_widgets(db, role)

        return RoleDefaultsResponse(
            role=role,
            widgets=defaults,
            total_widgets=len(defaults)
        )

    except Exception as e:
        logger.error(f"Error retrieving user role defaults: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve role defaults"
        )
