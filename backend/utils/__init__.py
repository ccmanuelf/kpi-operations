"""
Backend Utilities Module
========================
Shared utility functions for backend operations.

Available Utilities:
- soft_delete: Generic soft delete functionality for CRUD operations
"""

from .soft_delete import (
    soft_delete,
    soft_delete_with_timestamp,
    restore_soft_deleted,
    get_active_query,
    get_all_including_deleted,
    SoftDeleteMixin
)

__all__ = [
    "soft_delete",
    "soft_delete_with_timestamp",
    "restore_soft_deleted",
    "get_active_query",
    "get_all_including_deleted",
    "SoftDeleteMixin"
]
