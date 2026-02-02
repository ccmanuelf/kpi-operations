"""
CRUD operations for Filter History
Track recently applied filters for a user
SECURITY: All operations enforce user ownership
"""
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.schemas.saved_filter import FilterHistory
from backend.models.filters import FilterConfig


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
    # Get IDs of entries to keep (fetch as list to avoid SQLAlchemy subquery coercion warning)
    keep_ids_query = db.query(FilterHistory.history_id).filter(
        FilterHistory.user_id == user_id
    ).order_by(
        FilterHistory.applied_at.desc()
    ).limit(max_entries)

    keep_ids = [row.history_id for row in keep_ids_query.all()]

    # Delete entries not in keep list
    if keep_ids:
        db.query(FilterHistory).filter(
            and_(
                FilterHistory.user_id == user_id,
                ~FilterHistory.history_id.in_(keep_ids)
            )
        ).delete(synchronize_session='fetch')
    else:
        # If no entries to keep, delete all for user
        db.query(FilterHistory).filter(
            FilterHistory.user_id == user_id
        ).delete(synchronize_session='fetch')

    db.commit()


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
