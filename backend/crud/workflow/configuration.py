"""
CRUD operations for Workflow Configuration
Implements Phase 10: Flexible Workflow Foundation - Configuration management
"""

from typing import Dict
from sqlalchemy.orm import Session
from fastapi import HTTPException
import json

from backend.schemas.client_config import ClientConfig
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.services.workflow_service import get_workflow_config, apply_workflow_template as service_apply_template


def get_workflow_configuration(db: Session, client_id: str, current_user: User) -> Dict:
    """
    Get workflow configuration for a client.
    SECURITY: Verifies user access to the client.

    Args:
        db: Database session
        client_id: Client ID
        current_user: Authenticated user

    Returns:
        Dictionary with workflow configuration
    """
    verify_client_access(current_user, client_id)
    return get_workflow_config(db, client_id)


def update_workflow_configuration(db: Session, client_id: str, config_update: Dict, current_user: User) -> Dict:
    """
    Update workflow configuration for a client.
    SECURITY: Only admins can update workflow configuration.

    Args:
        db: Database session
        client_id: Client ID
        config_update: Configuration updates
        current_user: Authenticated user

    Returns:
        Updated workflow configuration

    Raises:
        HTTPException 403: If user is not admin
    """
    verify_client_access(current_user, client_id)

    # Only admins can modify workflow configuration
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update workflow configuration")

    # Get or create client config
    config = db.query(ClientConfig).filter(ClientConfig.client_id == client_id).first()

    if not config:
        config = ClientConfig(client_id=client_id)
        db.add(config)

    # Update workflow fields
    if "workflow_statuses" in config_update:
        config.workflow_statuses = json.dumps(config_update["workflow_statuses"])

    if "workflow_transitions" in config_update:
        config.workflow_transitions = json.dumps(config_update["workflow_transitions"])

    if "workflow_optional_statuses" in config_update:
        config.workflow_optional_statuses = json.dumps(config_update["workflow_optional_statuses"])

    if "workflow_closure_trigger" in config_update:
        config.workflow_closure_trigger = config_update["workflow_closure_trigger"]

    # Increment version
    config.workflow_version = (config.workflow_version or 0) + 1

    db.commit()
    db.refresh(config)

    return get_workflow_config(db, client_id)


def apply_workflow_template(db: Session, client_id: str, template_id: str, current_user: User) -> Dict:
    """
    Apply a workflow template to a client.
    SECURITY: Only admins can apply workflow templates.

    Args:
        db: Database session
        client_id: Client ID
        template_id: Template ID
        current_user: Authenticated user

    Returns:
        Updated workflow configuration

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 404: If template not found
    """
    verify_client_access(current_user, client_id)

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can apply workflow templates")

    return service_apply_template(db, client_id, template_id)
