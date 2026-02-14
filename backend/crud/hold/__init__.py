"""
Hold CRUD module - Re-exports all public functions for backward compatibility.

This module has been split into submodules for better organization:
- core.py: Basic CRUD operations (create, get, update, delete)
- queries.py: List and filter operations
- duration.py: Hold duration auto-calculation (P2-001)
- aging.py: Aging calculations and batch updates

All existing imports continue to work:
    from backend.crud.hold import create_wip_hold
"""

# Core CRUD operations
from backend.crud.hold.core import (
    create_wip_hold,
    get_wip_hold,
    update_wip_hold,
    delete_wip_hold,
)

# Query operations
from backend.crud.hold.queries import (
    get_wip_holds,
    get_holds_by_work_order,
)

# Duration operations (P2-001)
from backend.crud.hold.duration import (
    resume_hold,
    get_total_hold_duration,
    release_hold,
)

# Aging operations
from backend.crud.hold.aging import (
    bulk_update_aging,
)

__all__ = [
    # Core
    "create_wip_hold",
    "get_wip_hold",
    "update_wip_hold",
    "delete_wip_hold",
    # Queries
    "get_wip_holds",
    "get_holds_by_work_order",
    # Duration
    "resume_hold",
    "get_total_hold_duration",
    "release_hold",
    # Aging
    "bulk_update_aging",
]
