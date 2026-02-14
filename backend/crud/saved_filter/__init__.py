"""
Saved Filter CRUD module - Re-exports all public functions for backward compatibility.

This module has been split into submodules for better organization:
- filters.py: Core filter CRUD operations (create, get, update, delete)
- history.py: Filter history tracking operations
- utilities.py: Statistics and duplication utilities

All existing imports continue to work:
    from backend.crud.saved_filter import create_saved_filter
"""

# Core filter operations
from backend.crud.saved_filter.filters import (
    create_saved_filter,
    get_saved_filters,
    get_saved_filter,
    get_default_filter,
    update_saved_filter,
    delete_saved_filter,
    apply_filter,
    set_default_filter,
    unset_default_filter,
    _clear_default_filter,
)

# History operations
from backend.crud.saved_filter.history import (
    get_filter_history,
    add_to_filter_history,
    clear_filter_history,
)

# Utility operations
from backend.crud.saved_filter.utilities import (
    get_filter_statistics,
    duplicate_filter,
)

__all__ = [
    # Filters
    "create_saved_filter",
    "get_saved_filters",
    "get_saved_filter",
    "get_default_filter",
    "update_saved_filter",
    "delete_saved_filter",
    "apply_filter",
    "set_default_filter",
    "unset_default_filter",
    "_clear_default_filter",
    # History
    "get_filter_history",
    "add_to_filter_history",
    "clear_filter_history",
    # Utilities
    "get_filter_statistics",
    "duplicate_filter",
]
