"""
Saved Filters API Routes
User-specific filter configuration management
SECURITY: All endpoints enforce user ownership - filters are not shared
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.models.filters import (
    SavedFilterCreate,
    SavedFilterUpdate,
    SavedFilterResponse,
    FilterHistoryResponse,
    FilterConfig,
    ApplyFilterResponse,
    SetDefaultResponse,
    FilterType,
)
from backend.crud.saved_filter import (
    create_saved_filter,
    get_saved_filters,
    get_saved_filter,
    get_default_filter,
    update_saved_filter,
    delete_saved_filter,
    apply_filter,
    set_default_filter,
    unset_default_filter,
    get_filter_history,
    add_to_filter_history,
    clear_filter_history,
    get_filter_statistics,
    duplicate_filter,
)


router = APIRouter(prefix="/api/filters", tags=["Saved Filters"])


# ============================================================================
# SAVED FILTER ENDPOINTS
# ============================================================================


@router.get("", response_model=List[SavedFilterResponse])
def list_saved_filters(
    filter_type: Optional[str] = Query(
        None,
        description="Filter by type (dashboard, production, quality, attendance, downtime, hold, coverage, custom)",
    ),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all saved filters for the authenticated user

    SECURITY: Only returns filters owned by the current user

    Results are ordered by:
    1. Default filters first
    2. Most recently used
    3. Alphabetically by name
    """
    try:
        filters = get_saved_filters(db, user_id=current_user.user_id, filter_type=filter_type, skip=skip, limit=limit)

        # Transform to response model with parsed config
        return [_to_filter_response(f) for f in filters]
    except Exception as e:
        # Return empty list if table doesn't exist or other DB error
        import logging

        logging.getLogger(__name__).warning(f"Error fetching saved filters: {e}")
        return []


@router.post("", response_model=SavedFilterResponse, status_code=status.HTTP_201_CREATED)
def create_filter(
    filter_data: SavedFilterCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Create a new saved filter

    SECURITY: Filter is created with the authenticated user's ID

    If is_default is True, any existing default filter for the same type
    will have its default status removed.
    """
    db_filter = create_saved_filter(db, user_id=current_user.user_id, filter_data=filter_data)

    return _to_filter_response(db_filter)


@router.get("/default/{filter_type}", response_model=Optional[SavedFilterResponse])
def get_default_filter_by_type(
    filter_type: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get the default filter for a specific type

    SECURITY: Only returns user's own default filter

    Returns null if no default is set for the type.
    """
    db_filter = get_default_filter(db, user_id=current_user.user_id, filter_type=filter_type)

    if not db_filter:
        return None

    return _to_filter_response(db_filter)


@router.get("/statistics")
def get_user_filter_statistics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get filter usage statistics for the current user

    Returns:
    - Total number of saved filters
    - Filters grouped by type
    - Most used filter details
    - Total usage count across all filters
    """
    return get_filter_statistics(db, user_id=current_user.user_id)


@router.get("/{filter_id}", response_model=SavedFilterResponse)
def get_filter(filter_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get a specific saved filter by ID

    SECURITY: Verifies user owns the filter
    """
    db_filter = get_saved_filter(db, filter_id=filter_id, user_id=current_user.user_id)

    return _to_filter_response(db_filter)


@router.put("/{filter_id}", response_model=SavedFilterResponse)
def update_filter(
    filter_id: int,
    filter_data: SavedFilterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update an existing saved filter

    SECURITY: Verifies user owns the filter

    All fields are optional - only provided fields will be updated.
    If is_default is set to True, existing default for the type is cleared.
    """
    db_filter = update_saved_filter(db, filter_id=filter_id, user_id=current_user.user_id, filter_data=filter_data)

    return _to_filter_response(db_filter)


@router.delete("/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_filter(filter_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Delete a saved filter

    SECURITY: Verifies user owns the filter
    """
    delete_saved_filter(db, filter_id=filter_id, user_id=current_user.user_id)


@router.post("/{filter_id}/apply", response_model=ApplyFilterResponse)
def apply_saved_filter(filter_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Apply a saved filter and track usage

    SECURITY: Verifies user owns the filter

    This increments the usage_count and updates last_used_at timestamp.
    Returns the filter configuration to be applied by the client.
    """
    db_filter = apply_filter(db, filter_id=filter_id, user_id=current_user.user_id)

    # Also add to history
    filter_config = FilterConfig.from_json_string(db_filter.filter_config)
    add_to_filter_history(db, user_id=current_user.user_id, filter_config=filter_config)

    return ApplyFilterResponse(
        filter_id=db_filter.filter_id,
        filter_name=db_filter.filter_name,
        filter_config=filter_config,
        usage_count=db_filter.usage_count,
        last_used_at=db_filter.last_used_at,
        message="Filter applied successfully",
    )


@router.post("/{filter_id}/set-default", response_model=SetDefaultResponse)
def set_filter_as_default(
    filter_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Set a filter as the default for its type

    SECURITY: Verifies user owns the filter

    Only one filter per type can be default. Setting a new default
    automatically removes the previous default for that type.
    """
    db_filter = set_default_filter(db, filter_id=filter_id, user_id=current_user.user_id)

    return SetDefaultResponse(
        filter_id=db_filter.filter_id,
        filter_name=db_filter.filter_name,
        filter_type=db_filter.filter_type,
        is_default=db_filter.is_default,
        message=f"'{db_filter.filter_name}' is now the default filter for '{db_filter.filter_type}'",
    )


@router.post("/{filter_id}/unset-default", response_model=SetDefaultResponse)
def unset_filter_as_default(
    filter_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Remove default status from a filter

    SECURITY: Verifies user owns the filter
    """
    db_filter = unset_default_filter(db, filter_id=filter_id, user_id=current_user.user_id)

    return SetDefaultResponse(
        filter_id=db_filter.filter_id,
        filter_name=db_filter.filter_name,
        filter_type=db_filter.filter_type,
        is_default=db_filter.is_default,
        message=f"'{db_filter.filter_name}' is no longer the default filter",
    )


@router.post("/{filter_id}/duplicate", response_model=SavedFilterResponse, status_code=status.HTTP_201_CREATED)
def duplicate_saved_filter(
    filter_id: int,
    new_name: Optional[str] = Query(None, max_length=100, description="Name for the duplicate"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Duplicate an existing filter

    SECURITY: User can only duplicate their own filters

    Creates a copy with:
    - New name (defaults to "Copy of {original_name}")
    - is_default = False
    - usage_count = 0
    - Same filter_config
    """
    db_filter = duplicate_filter(db, filter_id=filter_id, user_id=current_user.user_id, new_name=new_name)

    return _to_filter_response(db_filter)


# ============================================================================
# FILTER HISTORY ENDPOINTS
# ============================================================================


@router.get("/history/recent", response_model=List[FilterHistoryResponse])
def get_recent_filter_history(
    limit: int = Query(10, ge=1, le=50, description="Maximum entries to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get recent filter history

    SECURITY: Only returns history owned by the current user

    Returns the most recent filter configurations that were applied,
    including both saved and ad-hoc filters.
    """
    history = get_filter_history(db, user_id=current_user.user_id, limit=limit)

    return [_to_history_response(h) for h in history]


@router.post("/history", response_model=FilterHistoryResponse, status_code=status.HTTP_201_CREATED)
def add_filter_to_history(
    filter_config: FilterConfig, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Add a filter configuration to history

    SECURITY: History entry is created with the authenticated user's ID

    Use this endpoint when applying ad-hoc filters that are not saved.
    History is automatically limited to 50 entries per user.
    """
    history_entry = add_to_filter_history(db, user_id=current_user.user_id, filter_config=filter_config)

    return _to_history_response(history_entry)


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
def clear_user_filter_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Clear all filter history for the current user

    SECURITY: Only clears history owned by the current user
    """
    clear_filter_history(db, user_id=current_user.user_id)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _to_filter_response(db_filter) -> SavedFilterResponse:
    """
    Convert database SavedFilter to response model

    Parses the JSON filter_config string back to FilterConfig object
    """
    return SavedFilterResponse(
        filter_id=db_filter.filter_id,
        user_id=db_filter.user_id,
        filter_name=db_filter.filter_name,
        filter_type=db_filter.filter_type,
        filter_config=FilterConfig.from_json_string(db_filter.filter_config),
        is_default=db_filter.is_default,
        usage_count=db_filter.usage_count or 0,
        last_used_at=db_filter.last_used_at,
        created_at=db_filter.created_at,
        updated_at=db_filter.updated_at,
    )


def _to_history_response(history_entry) -> FilterHistoryResponse:
    """
    Convert database FilterHistory to response model

    Parses the JSON filter_config string back to FilterConfig object
    """
    return FilterHistoryResponse(
        history_id=history_entry.history_id,
        user_id=history_entry.user_id,
        filter_config=FilterConfig.from_json_string(history_entry.filter_config),
        applied_at=history_entry.applied_at,
    )
