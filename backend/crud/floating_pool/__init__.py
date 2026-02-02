"""
Floating Pool CRUD module - Re-exports all public functions for backward compatibility.

This module has been split into submodules for better organization:
- core.py: Basic CRUD operations (create, get, update, delete)
- assignments.py: Assignment and unassignment operations
- queries.py: List, filter, and summary queries

All existing imports continue to work:
    from backend.crud.floating_pool import create_floating_pool_entry
"""

# Core CRUD operations
from backend.crud.floating_pool.core import (
    create_floating_pool_entry,
    get_floating_pool_entry,
    update_floating_pool_entry,
    delete_floating_pool_entry,
)

# Assignment operations
from backend.crud.floating_pool.assignments import (
    assign_floating_pool_to_client,
    unassign_floating_pool_from_client,
    is_employee_available_for_assignment,
)

# Query operations
from backend.crud.floating_pool.queries import (
    get_floating_pool_entries,
    get_available_floating_pool_employees,
    get_floating_pool_assignments_by_client,
    get_floating_pool_summary,
)

__all__ = [
    # Core
    'create_floating_pool_entry',
    'get_floating_pool_entry',
    'update_floating_pool_entry',
    'delete_floating_pool_entry',
    # Assignments
    'assign_floating_pool_to_client',
    'unassign_floating_pool_from_client',
    'is_employee_available_for_assignment',
    # Queries
    'get_floating_pool_entries',
    'get_available_floating_pool_employees',
    'get_floating_pool_assignments_by_client',
    'get_floating_pool_summary',
]
