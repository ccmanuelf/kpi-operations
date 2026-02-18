"""
Client Configuration Routes
API endpoints for managing client-level KPI calculation overrides
Implements Phase 7.2: Client-Level Calculation Overrides
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.models.client_config import (
    ClientConfigCreate,
    ClientConfigUpdate,
    ClientConfigResponse,
    ClientConfigWithDefaults,
    GlobalDefaults,
)
from backend.crud import client_config as crud
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(
    prefix="/api/client-config", tags=["Client Configuration"], responses={404: {"description": "Not found"}}
)


@router.post("/", response_model=ClientConfigResponse, status_code=201)
def create_client_config(
    config: ClientConfigCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Create a new client configuration.

    Only users with access to the client can create its configuration.
    Configuration cannot be created if one already exists for the client.
    """
    return crud.create_client_config(db=db, config_data=config.model_dump(), current_user=current_user)


@router.get("/defaults", response_model=GlobalDefaults)
def get_global_defaults():
    """
    Get global default configuration values.

    These are the values used when a client has no custom configuration.
    """
    defaults = crud.get_global_defaults()
    return GlobalDefaults(**defaults)


@router.get("/{client_id}", response_model=ClientConfigWithDefaults)
def get_client_config(
    client_id: str,
    create_if_missing: bool = Query(default=False, description="Create config with defaults if not found"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get client configuration by client ID.

    Returns the client's custom configuration or indicates if defaults are being used.
    If create_if_missing=True, creates a new config with defaults if none exists.
    """
    config = crud.get_client_config(
        db=db, client_id=client_id, current_user=current_user, create_if_missing=create_if_missing
    )

    if not config:
        # Return defaults indicator
        defaults = crud.get_global_defaults()
        return ClientConfigWithDefaults(
            config=ClientConfigResponse(config_id=0, client_id=client_id, **defaults, created_at=None, updated_at=None),
            is_default=True,
        )

    # Convert SQLAlchemy model to Pydantic model to trigger JSON field parsing
    return ClientConfigWithDefaults(config=ClientConfigResponse.model_validate(config), is_default=False)


@router.get("/{client_id}/effective")
def get_effective_config(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get effective configuration values for a client.

    Returns client-specific values where configured, otherwise defaults.
    This is what the KPI calculations actually use.
    """
    from backend.middleware.client_auth import verify_client_access

    verify_client_access(current_user, client_id)

    return crud.get_client_config_or_defaults(db=db, client_id=client_id)


@router.put("/{client_id}", response_model=ClientConfigResponse)
def update_client_config(
    client_id: str,
    config_update: ClientConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update client configuration.

    Only provided fields will be updated.
    Configuration must already exist (use POST to create).
    """
    return crud.update_client_config(
        db=db, client_id=client_id, config_update=config_update.model_dump(exclude_none=True), current_user=current_user
    )


@router.delete("/{client_id}", status_code=204)
def delete_client_config(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Delete client configuration.

    This resets the client to use global defaults.
    Only admins can delete configurations.
    """
    crud.delete_client_config(db=db, client_id=client_id, current_user=current_user)
    return None


@router.get("/", response_model=List[ClientConfigResponse])
def list_client_configs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all client configurations.

    Only admins can view all configurations.
    """
    return crud.get_all_client_configs(db=db, current_user=current_user, skip=skip, limit=limit)


@router.post("/{client_id}/reset-to-defaults", response_model=ClientConfigResponse)
def reset_to_defaults(client_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Reset client configuration to global defaults.

    This updates all fields to their default values without deleting the config.
    Useful for preserving the config record while resetting all values.
    """
    defaults = crud.get_global_defaults()
    return crud.update_client_config(db=db, client_id=client_id, config_update=defaults, current_user=current_user)
