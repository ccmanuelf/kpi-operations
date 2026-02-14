"""
Workflow CRUD module - Re-exports all public functions for backward compatibility.

This module has been split into submodules for better organization:
- transition_log.py: Transition log CRUD operations
- configuration.py: Workflow configuration management
- operations.py: Transition operations (execute, validate, bulk)
- analytics.py: Statistics and reporting queries

All existing imports continue to work:
    from backend.crud.workflow import create_transition_log
"""

# Transition log operations
from backend.crud.workflow.transition_log import (
    create_transition_log,
    get_transition_log_by_id,
    get_work_order_transitions,
    get_client_transitions,
)

# Configuration operations
from backend.crud.workflow.configuration import (
    get_workflow_configuration,
    update_workflow_configuration,
    apply_workflow_template,
)

# Transition operations
from backend.crud.workflow.operations import (
    transition_work_order,
    validate_transition,
    get_allowed_transitions_for_work_order,
    bulk_transition_work_orders,
)

# Analytics operations
from backend.crud.workflow.analytics import (
    get_transition_statistics,
    get_status_distribution,
)

__all__ = [
    # Transition log
    "create_transition_log",
    "get_transition_log_by_id",
    "get_work_order_transitions",
    "get_client_transitions",
    # Configuration
    "get_workflow_configuration",
    "update_workflow_configuration",
    "apply_workflow_template",
    # Operations
    "transition_work_order",
    "validate_transition",
    "get_allowed_transitions_for_work_order",
    "bulk_transition_work_orders",
    # Analytics
    "get_transition_statistics",
    "get_status_distribution",
]
