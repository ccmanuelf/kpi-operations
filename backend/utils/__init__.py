"""
Backend Utilities Module
========================
Shared utility functions for backend operations.

Available Utilities:
- soft_delete: Generic soft delete functionality for CRUD operations
- logging_utils: Structured logging for data operations and security events
"""

from .soft_delete import (
    soft_delete,
    soft_delete_with_timestamp,
    restore_soft_deleted,
    get_active_query,
    get_all_including_deleted,
    SoftDeleteMixin
)

from .logging_utils import (
    get_module_logger,
    log_operation,
    log_error,
    log_security_event,
    log_performance,
    with_logging
)

__all__ = [
    # Soft delete utilities
    "soft_delete",
    "soft_delete_with_timestamp",
    "restore_soft_deleted",
    "get_active_query",
    "get_all_including_deleted",
    "SoftDeleteMixin",
    # Logging utilities
    "get_module_logger",
    "log_operation",
    "log_error",
    "log_security_event",
    "log_performance",
    "with_logging"
]
