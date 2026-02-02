"""
CRUD utility operations for Saved Filters
Statistics and duplication utilities
SECURITY: All operations enforce user ownership
"""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from backend.schemas.saved_filter import SavedFilter
from backend.crud.saved_filter.filters import get_saved_filter


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
