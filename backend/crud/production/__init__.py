"""
Production CRUD module - Re-exports all public functions for backward compatibility.

This module has been split into submodules for better organization:
- core.py: Basic CRUD operations (create, get, update, delete)
- queries.py: List and filter operations
- batch.py: Bulk operations
- kpi.py: KPI-related operations with detailed breakdowns

All existing imports continue to work:
    from backend.crud.production import create_production_entry
"""

# Core CRUD operations
from backend.crud.production.core import (
    create_production_entry,
    get_production_entry,
    update_production_entry,
    delete_production_entry,
    _calculate_entry_kpis,
)

# Query operations
from backend.crud.production.queries import (
    get_production_entries,
    get_daily_summary,
)

# Batch operations
from backend.crud.production.batch import (
    batch_create_entries,
)

# KPI operations
from backend.crud.production.kpi import (
    get_production_entry_with_details,
)

__all__ = [
    # Core
    'create_production_entry',
    'get_production_entry',
    'update_production_entry',
    'delete_production_entry',
    '_calculate_entry_kpis',
    # Queries
    'get_production_entries',
    'get_daily_summary',
    # Batch
    'batch_create_entries',
    # KPI
    'get_production_entry_with_details',
]
