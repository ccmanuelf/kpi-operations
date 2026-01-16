"""
CRUD operations for Saved Filters
Create, Read, Update, Delete with user-level security
SECURITY: All operations enforce user ownership - no filter sharing
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from fastapi import HTTPException

from backend.schemas.saved_filter import SavedFilter, FilterHistory
from backend.schemas.user import User
from backend.models.filters import (
    SavedFilterCreate,
    SavedFilterUpdate,
    FilterConfig,
    FilterHistoryCreate
)


def create_saved_filter(
    db: Session,
    user_id: str,
    filter_data: SavedFilterCreate
) -> SavedFilter:
    """
    Create a new saved filter for a user

    SECURITY: Filter is created with the authenticated user's ID

    Args:
        db: Database session
        user_id: Authenticated user ID
        filter_data: Filter creation data

    Returns:
        Created SavedFilter object

    Raises:
        HTTPException 400: If filter name already exists for user and type
    """
    # Check for duplicate name within same type for user
    existing = db.query(SavedFilter).filter(
        and_(
            SavedFilter.user_id == user_id,
            SavedFilter.filter_name == filter_data.filter_name,
            SavedFilter.filter_type == filter_data.filter_type.value
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Filter with name '{filter_data.filter_name}' already exists for type '{filter_data.filter_type.value}'"
        )

    # If setting as default, clear existing default for this type
    if filter_data.is_default:
        _clear_default_filter(db, user_id, filter_data.filter_type.value)

    # Create filter
    db_filter = SavedFilter(
        user_id=user_id,
        filter_name=filter_data.filter_name,
        filter_type=filter_data.filter_type.value,
        filter_config=filter_data.filter_config.to_json_string(),
        is_default=filter_data.is_default,
        usage_count=0,
        last_used_at=None
    )

    db.add(db_filter)
    db.commit()
    db.refresh(db_filter)

    return db_filter


def get_saved_filters(
    db: Session,
    user_id: str,
    filter_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[SavedFilter]:
    """
    Get all saved filters for a user

    SECURITY: Only returns filters owned by the authenticated user

    Args:
        db: Database session
        user_id: Authenticated user ID
        filter_type: Optional filter type to filter by
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        List of SavedFilter objects
    """
    query = db.query(SavedFilter).filter(SavedFilter.user_id == user_id)

    if filter_type:
        query = query.filter(SavedFilter.filter_type == filter_type)

    return query.order_by(
        SavedFilter.is_default.desc(),  # Default filters first
        SavedFilter.last_used_at.desc().nullslast(),  # Recently used next
        SavedFilter.filter_name.asc()  # Alphabetical fallback
    ).offset(skip).limit(limit).all()


def get_saved_filter(
    db: Session,
    filter_id: int,
    user_id: str
) -> Optional[SavedFilter]:
    """
    Get a specific saved filter by ID

    SECURITY: Verifies user owns the filter

    Args:
        db: Database session
        filter_id: Filter ID
        user_id: Authenticated user ID

    Returns:
        SavedFilter object or None if not found

    Raises:
        HTTPException 403: If user doesn't own the filter
        HTTPException 404: If filter not found
    """
    db_filter = db.query(SavedFilter).filter(
        SavedFilter.filter_id == filter_id
    ).first()

    if not db_filter:
        raise HTTPException(status_code=404, detail="Filter not found")

    # SECURITY: Verify ownership
    if db_filter.user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this filter"
        )

    return db_filter


def get_default_filter(
    db: Session,
    user_id: str,
    filter_type: str
) -> Optional[SavedFilter]:
    """
    Get the default filter for a user and type

    SECURITY: Only returns user's own default filter

    Args:
        db: Database session
        user_id: Authenticated user ID
        filter_type: Filter type category

    Returns:
        Default SavedFilter or None
    """
    return db.query(SavedFilter).filter(
        and_(
            SavedFilter.user_id == user_id,
            SavedFilter.filter_type == filter_type,
            SavedFilter.is_default == True
        )
    ).first()


def update_saved_filter(
    db: Session,
    filter_id: int,
    user_id: str,
    filter_data: SavedFilterUpdate
) -> SavedFilter:
    """
    Update an existing saved filter

    SECURITY: Verifies user owns the filter

    Args:
        db: Database session
        filter_id: Filter ID to update
        user_id: Authenticated user ID
        filter_data: Update data

    Returns:
        Updated SavedFilter object

    Raises:
        HTTPException 403: If user doesn't own the filter
        HTTPException 404: If filter not found
        HTTPException 400: If duplicate name would be created
    """
    db_filter = get_saved_filter(db, filter_id, user_id)

    # Check for duplicate name if name is being changed
    if filter_data.filter_name and filter_data.filter_name != db_filter.filter_name:
        check_type = filter_data.filter_type.value if filter_data.filter_type else db_filter.filter_type
        existing = db.query(SavedFilter).filter(
            and_(
                SavedFilter.user_id == user_id,
                SavedFilter.filter_name == filter_data.filter_name,
                SavedFilter.filter_type == check_type,
                SavedFilter.filter_id != filter_id
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Filter with name '{filter_data.filter_name}' already exists for type '{check_type}'"
            )

    # Handle default flag change
    if filter_data.is_default is True and not db_filter.is_default:
        new_type = filter_data.filter_type.value if filter_data.filter_type else db_filter.filter_type
        _clear_default_filter(db, user_id, new_type)

    # Update fields
    if filter_data.filter_name is not None:
        db_filter.filter_name = filter_data.filter_name
    if filter_data.filter_type is not None:
        db_filter.filter_type = filter_data.filter_type.value
    if filter_data.filter_config is not None:
        db_filter.filter_config = filter_data.filter_config.to_json_string()
    if filter_data.is_default is not None:
        db_filter.is_default = filter_data.is_default

    db.commit()
    db.refresh(db_filter)

    return db_filter


def delete_saved_filter(
    db: Session,
    filter_id: int,
    user_id: str
) -> bool:
    """
    Delete a saved filter

    SECURITY: Verifies user owns the filter

    Args:
        db: Database session
        filter_id: Filter ID to delete
        user_id: Authenticated user ID

    Returns:
        True if deleted

    Raises:
        HTTPException 403: If user doesn't own the filter
        HTTPException 404: If filter not found
    """
    db_filter = get_saved_filter(db, filter_id, user_id)

    db.delete(db_filter)
    db.commit()

    return True


def apply_filter(
    db: Session,
    filter_id: int,
    user_id: str
) -> SavedFilter:
    """
    Apply a filter and update usage statistics

    SECURITY: Verifies user owns the filter

    This increments usage_count and updates last_used_at timestamp.

    Args:
        db: Database session
        filter_id: Filter ID to apply
        user_id: Authenticated user ID

    Returns:
        Updated SavedFilter object

    Raises:
        HTTPException 403: If user doesn't own the filter
        HTTPException 404: If filter not found
    """
    db_filter = get_saved_filter(db, filter_id, user_id)

    # Update usage statistics
    db_filter.usage_count = (db_filter.usage_count or 0) + 1
    db_filter.last_used_at = datetime.utcnow()

    db.commit()
    db.refresh(db_filter)

    return db_filter


def set_default_filter(
    db: Session,
    filter_id: int,
    user_id: str
) -> SavedFilter:
    """
    Set a filter as the default for its type

    SECURITY: Verifies user owns the filter

    Clears any existing default for the same filter_type before setting new default.

    Args:
        db: Database session
        filter_id: Filter ID to set as default
        user_id: Authenticated user ID

    Returns:
        Updated SavedFilter object

    Raises:
        HTTPException 403: If user doesn't own the filter
        HTTPException 404: If filter not found
    """
    db_filter = get_saved_filter(db, filter_id, user_id)

    # Clear existing default for this type
    _clear_default_filter(db, user_id, db_filter.filter_type)

    # Set this filter as default
    db_filter.is_default = True

    db.commit()
    db.refresh(db_filter)

    return db_filter


def unset_default_filter(
    db: Session,
    filter_id: int,
    user_id: str
) -> SavedFilter:
    """
    Remove default status from a filter

    SECURITY: Verifies user owns the filter

    Args:
        db: Database session
        filter_id: Filter ID to unset as default
        user_id: Authenticated user ID

    Returns:
        Updated SavedFilter object
    """
    db_filter = get_saved_filter(db, filter_id, user_id)

    db_filter.is_default = False

    db.commit()
    db.refresh(db_filter)

    return db_filter


def _clear_default_filter(
    db: Session,
    user_id: str,
    filter_type: str
) -> None:
    """
    Internal: Clear default flag for all filters of a type for a user

    Args:
        db: Database session
        user_id: User ID
        filter_type: Filter type to clear default for
    """
    db.query(SavedFilter).filter(
        and_(
            SavedFilter.user_id == user_id,
            SavedFilter.filter_type == filter_type,
            SavedFilter.is_default == True
        )
    ).update({SavedFilter.is_default: False})


# ============================================================================
# FILTER HISTORY CRUD OPERATIONS
# ============================================================================

def get_filter_history(
    db: Session,
    user_id: str,
    limit: int = 10
) -> List[FilterHistory]:
    """
    Get recent filter history for a user

    SECURITY: Only returns history owned by the authenticated user

    Args:
        db: Database session
        user_id: Authenticated user ID
        limit: Maximum records to return (default 10)

    Returns:
        List of FilterHistory objects, most recent first
    """
    return db.query(FilterHistory).filter(
        FilterHistory.user_id == user_id
    ).order_by(
        FilterHistory.applied_at.desc()
    ).limit(limit).all()


def add_to_filter_history(
    db: Session,
    user_id: str,
    filter_config: FilterConfig
) -> FilterHistory:
    """
    Add a filter configuration to history

    SECURITY: History entry is created with the authenticated user's ID

    Limits history to 50 entries per user by removing oldest entries.

    Args:
        db: Database session
        user_id: Authenticated user ID
        filter_config: Filter configuration that was applied

    Returns:
        Created FilterHistory object
    """
    # Create history entry
    history_entry = FilterHistory(
        user_id=user_id,
        filter_config=filter_config.to_json_string(),
        applied_at=datetime.utcnow()
    )

    db.add(history_entry)
    db.commit()
    db.refresh(history_entry)

    # Cleanup: keep only the most recent 50 entries
    _cleanup_old_history(db, user_id, max_entries=50)

    return history_entry


def clear_filter_history(
    db: Session,
    user_id: str
) -> int:
    """
    Clear all filter history for a user

    SECURITY: Only clears history owned by the authenticated user

    Args:
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Number of entries deleted
    """
    result = db.query(FilterHistory).filter(
        FilterHistory.user_id == user_id
    ).delete()

    db.commit()

    return result


def _cleanup_old_history(
    db: Session,
    user_id: str,
    max_entries: int = 50
) -> None:
    """
    Internal: Remove oldest history entries beyond max_entries

    Args:
        db: Database session
        user_id: User ID
        max_entries: Maximum entries to keep
    """
    # Get IDs of entries to keep
    keep_ids = db.query(FilterHistory.history_id).filter(
        FilterHistory.user_id == user_id
    ).order_by(
        FilterHistory.applied_at.desc()
    ).limit(max_entries).subquery()

    # Delete entries not in keep list
    db.query(FilterHistory).filter(
        and_(
            FilterHistory.user_id == user_id,
            ~FilterHistory.history_id.in_(keep_ids)
        )
    ).delete(synchronize_session='fetch')

    db.commit()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_filter_statistics(
    db: Session,
    user_id: str
) -> dict:
    """
    Get filter usage statistics for a user

    Args:
        db: Database session
        user_id: Authenticated user ID

    Returns:
        Dictionary with filter statistics
    """
    from sqlalchemy import func

    # Total filters
    total_filters = db.query(func.count(SavedFilter.filter_id)).filter(
        SavedFilter.user_id == user_id
    ).scalar()

    # Filters by type
    by_type = db.query(
        SavedFilter.filter_type,
        func.count(SavedFilter.filter_id).label('count')
    ).filter(
        SavedFilter.user_id == user_id
    ).group_by(SavedFilter.filter_type).all()

    # Most used filter
    most_used = db.query(SavedFilter).filter(
        SavedFilter.user_id == user_id
    ).order_by(SavedFilter.usage_count.desc()).first()

    # Total usage count
    total_usage = db.query(func.sum(SavedFilter.usage_count)).filter(
        SavedFilter.user_id == user_id
    ).scalar() or 0

    return {
        "total_filters": total_filters,
        "filters_by_type": {row.filter_type: row.count for row in by_type},
        "most_used_filter": {
            "filter_id": most_used.filter_id,
            "filter_name": most_used.filter_name,
            "usage_count": most_used.usage_count
        } if most_used else None,
        "total_usage_count": total_usage
    }


def duplicate_filter(
    db: Session,
    filter_id: int,
    user_id: str,
    new_name: Optional[str] = None
) -> SavedFilter:
    """
    Duplicate an existing filter

    SECURITY: User can only duplicate their own filters

    Args:
        db: Database session
        filter_id: Filter ID to duplicate
        user_id: Authenticated user ID
        new_name: Optional new name (defaults to "Copy of {original_name}")

    Returns:
        New SavedFilter object
    """
    original = get_saved_filter(db, filter_id, user_id)

    # Generate new name
    if not new_name:
        new_name = f"Copy of {original.filter_name}"

    # Ensure unique name
    counter = 1
    base_name = new_name
    while db.query(SavedFilter).filter(
        and_(
            SavedFilter.user_id == user_id,
            SavedFilter.filter_name == new_name,
            SavedFilter.filter_type == original.filter_type
        )
    ).first():
        new_name = f"{base_name} ({counter})"
        counter += 1

    # Create duplicate (not default, zero usage)
    duplicate = SavedFilter(
        user_id=user_id,
        filter_name=new_name,
        filter_type=original.filter_type,
        filter_config=original.filter_config,
        is_default=False,
        usage_count=0,
        last_used_at=None
    )

    db.add(duplicate)
    db.commit()
    db.refresh(duplicate)

    return duplicate
