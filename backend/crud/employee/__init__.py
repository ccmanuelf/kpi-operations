"""
Employee CRUD module - Re-exports all public functions for backward compatibility.

This module has been split into submodules for better organization:
- core.py: Basic CRUD operations (create, get, update, delete)
- floating_pool.py: Floating pool membership management
- client_assignment.py: Client assignment operations

All existing imports continue to work:
    from backend.crud.employee import create_employee
"""

# Core CRUD operations
from backend.crud.employee.core import (
    create_employee,
    get_employee,
    get_employees,
    update_employee,
    delete_employee,
)

# Floating pool operations
from backend.crud.employee.floating_pool import (
    get_floating_pool_employees,
    assign_to_floating_pool,
    remove_from_floating_pool,
)

# Client assignment operations
from backend.crud.employee.client_assignment import (
    get_employees_by_client,
    assign_employee_to_client,
)

__all__ = [
    # Core
    'create_employee',
    'get_employee',
    'get_employees',
    'update_employee',
    'delete_employee',
    # Floating pool
    'get_floating_pool_employees',
    'assign_to_floating_pool',
    'remove_from_floating_pool',
    # Client assignment
    'get_employees_by_client',
    'assign_employee_to_client',
]
