"""
Saved Filter Service
Thin service layer wrapping Saved Filter CRUD operations.
Routes should import from this module instead of backend.crud.saved_filter directly.
"""

from typing import Any, TYPE_CHECKING, List, Optional

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from backend.orm.saved_filter import FilterHistory
    from backend.schemas.filters import FilterConfig

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


def create_filter(db: Session, user_id: str, filter_data: Any) -> Any:
    """Create a new saved filter."""
    return create_saved_filter(db, user_id, filter_data)


def list_filters(db: Session, user_id: str, filter_type: Optional[str] = None, skip: int = 0, limit: int = 100) -> Any:
    """List saved filters for a user."""
    return get_saved_filters(db, user_id, filter_type, skip, limit)


def get_filter(db: Session, filter_id: int, user_id: str) -> Any:
    """Get a specific filter by ID."""
    return get_saved_filter(db, filter_id, user_id)


def get_user_default_filter(db: Session, user_id: str, filter_type: str) -> Any:
    """Get the user's default filter for a type."""
    return get_default_filter(db, user_id, filter_type)


def update_filter(db: Session, filter_id: int, user_id: str, update_data: Any) -> Any:
    """Update a saved filter."""
    return update_saved_filter(db, filter_id, user_id, update_data)


def delete_filter(db: Session, filter_id: int, user_id: str) -> bool:
    """Delete a saved filter."""
    return delete_saved_filter(db, filter_id, user_id)


def apply_saved_filter(db: Session, filter_id: int, user_id: str) -> Any:
    """Apply a saved filter."""
    return apply_filter(db, filter_id, user_id)


def set_filter_as_default(db: Session, filter_id: int, user_id: str) -> Any:
    """Set a filter as default for its type."""
    return set_default_filter(db, filter_id, user_id)


def unset_filter_as_default(db: Session, filter_id: int, user_id: str) -> Any:
    """Unset a filter as default."""
    return unset_default_filter(db, filter_id, user_id)


def get_user_filter_history(db: Session, user_id: str, limit: int = 10) -> List["FilterHistory"]:
    """Get filter usage history for a user (most recent first)."""
    return get_filter_history(db, user_id, limit)


def add_filter_to_history(db: Session, user_id: str, filter_config: "FilterConfig") -> "FilterHistory":
    """Add a filter usage to history (records the configuration that was applied)."""
    return add_to_filter_history(db, user_id, filter_config)


def clear_user_filter_history(db: Session, user_id: str) -> int:
    """Clear all filter history for a user. Returns the number of rows deleted."""
    return clear_filter_history(db, user_id)


def get_user_filter_statistics(db: Session, user_id: str) -> Any:
    """Get filter usage statistics for a user."""
    return get_filter_statistics(db, user_id)


def duplicate_saved_filter(db: Session, filter_id: int, user_id: str, new_name: Optional[str] = None) -> Any:
    """Duplicate an existing filter."""
    return duplicate_filter(db, filter_id, user_id, new_name)
