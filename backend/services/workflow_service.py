"""
Workflow State Machine Service
Implements Phase 10: Flexible Workflow Foundation

Re-exports all workflow engine functions from backend.calculations.workflow_engine.
The core domain logic has been moved to the calculations layer to eliminate
the upward CRUD->Service dependency.

This module is kept for backward compatibility. All new code should import
from backend.calculations.workflow_engine directly.
"""

from backend.calculations.workflow_engine import (
    # Core domain class
    WorkflowStateMachine,
    # Constants
    DEFAULT_WORKFLOW_TRANSITIONS,
    UNIVERSAL_FROM_STATUSES,
    UNIVERSAL_TO_STATUSES,
    # Functions
    get_workflow_config,
    validate_transition,
    get_allowed_transitions,
    calculate_elapsed_hours,
    execute_transition,
    get_transition_history,
    bulk_transition,
    apply_workflow_template,
)

__all__ = [
    "WorkflowStateMachine",
    "DEFAULT_WORKFLOW_TRANSITIONS",
    "UNIVERSAL_FROM_STATUSES",
    "UNIVERSAL_TO_STATUSES",
    "get_workflow_config",
    "validate_transition",
    "get_allowed_transitions",
    "calculate_elapsed_hours",
    "execute_transition",
    "get_transition_history",
    "bulk_transition",
    "apply_workflow_template",
]
