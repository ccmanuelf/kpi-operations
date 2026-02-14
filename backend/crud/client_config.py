"""
CRUD operations for ClientConfig
Create, Read, Update, Delete for client-level KPI calculation overrides
Implements Phase 7.2: Client-Level Calculation Overrides

Phase A.1: Added caching for client config lookups
"""

from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.schemas.client_config import ClientConfig
from backend.schemas.client import Client
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.cache import get_cache
from backend.cache.kpi_cache import build_cache_key


# Global default values (used when no config exists)
GLOBAL_DEFAULTS = {
    "otd_mode": "STANDARD",
    "default_cycle_time_hours": 0.25,
    "efficiency_target_percent": 85.0,
    "quality_target_ppm": 10000.0,
    "fpy_target_percent": 95.0,
    "dpmo_opportunities_default": 1,
    "availability_target_percent": 90.0,
    "performance_target_percent": 95.0,
    "oee_target_percent": 85.0,
    "absenteeism_target_percent": 3.0,
    "wip_aging_threshold_days": 7,
    "wip_critical_threshold_days": 14,
}


def create_client_config(db: Session, config_data: dict, current_user: User) -> ClientConfig:
    """
    Create client configuration.
    SECURITY: User must have access to the client.

    Args:
        db: Database session
        config_data: Configuration data dictionary
        current_user: Authenticated user

    Returns:
        Created ClientConfig

    Raises:
        HTTPException 403: If user doesn't have access
        HTTPException 400: If config already exists for client
        HTTPException 404: If client doesn't exist
    """
    client_id = config_data.get("client_id")

    # SECURITY: Verify user has access to this client
    verify_client_access(current_user, client_id)

    # Verify client exists
    client = db.query(Client).filter(Client.client_id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {client_id} not found")

    # Check if config already exists
    existing = db.query(ClientConfig).filter(ClientConfig.client_id == client_id).first()

    if existing:
        raise HTTPException(
            status_code=400, detail=f"Configuration already exists for client {client_id}. Use update instead."
        )

    # Create config
    db_config = ClientConfig(**config_data)

    db.add(db_config)
    db.commit()
    db.refresh(db_config)

    return db_config


def get_client_config(
    db: Session, client_id: str, current_user: User, create_if_missing: bool = False
) -> Optional[ClientConfig]:
    """
    Get client configuration by client ID.
    SECURITY: Verifies user has access to the client.

    Args:
        db: Database session
        client_id: Client ID
        current_user: Authenticated user
        create_if_missing: If True, create config with defaults if not found

    Returns:
        ClientConfig or None if not found (and create_if_missing=False)

    Raises:
        HTTPException 403: If user doesn't have access to client
    """
    # SECURITY: Verify user has access to this client
    verify_client_access(current_user, client_id)

    config = db.query(ClientConfig).filter(ClientConfig.client_id == client_id).first()

    if not config and create_if_missing:
        # Create with defaults
        config_data = {"client_id": client_id, **GLOBAL_DEFAULTS}
        # Remove otd_mode string and set enum
        db_config = ClientConfig(
            client_id=client_id,
            # Other fields use defaults from schema
        )
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        return db_config

    return config


def get_client_config_or_defaults(db: Session, client_id: str) -> dict:
    """
    Get client configuration values, falling back to global defaults.
    This function is for use by calculation modules - no auth required.

    Phase A.1: Added caching with 15 minute TTL to reduce database queries.

    Args:
        db: Database session
        client_id: Client ID

    Returns:
        Dictionary with configuration values (client-specific or defaults)
    """
    cache = get_cache()
    cache_key = build_cache_key("client_config", client_id)

    def fetch_config():
        config = db.query(ClientConfig).filter(ClientConfig.client_id == client_id).first()

        if config:
            return {
                "otd_mode": config.otd_mode.value if hasattr(config.otd_mode, "value") else str(config.otd_mode),
                "default_cycle_time_hours": config.default_cycle_time_hours,
                "efficiency_target_percent": config.efficiency_target_percent,
                "quality_target_ppm": config.quality_target_ppm,
                "fpy_target_percent": config.fpy_target_percent,
                "dpmo_opportunities_default": config.dpmo_opportunities_default,
                "availability_target_percent": config.availability_target_percent,
                "performance_target_percent": config.performance_target_percent,
                "oee_target_percent": config.oee_target_percent,
                "absenteeism_target_percent": config.absenteeism_target_percent,
                "wip_aging_threshold_days": config.wip_aging_threshold_days,
                "wip_critical_threshold_days": config.wip_critical_threshold_days,
                "is_default": False,
            }

        # Return global defaults
        return {**GLOBAL_DEFAULTS, "is_default": True}

    return cache.get_or_set(cache_key, fetch_config, ttl_seconds=900)


def update_client_config(
    db: Session, client_id: str, config_update: dict, current_user: User
) -> Optional[ClientConfig]:
    """
    Update client configuration.
    SECURITY: Verifies user has access to the client.

    Args:
        db: Database session
        client_id: Client ID
        config_update: Update data dictionary
        current_user: Authenticated user

    Returns:
        Updated ClientConfig

    Raises:
        HTTPException 404: If config not found
        HTTPException 403: If user doesn't have access to client
    """
    # SECURITY: Verify user has access to this client
    verify_client_access(current_user, client_id)

    db_config = db.query(ClientConfig).filter(ClientConfig.client_id == client_id).first()

    if not db_config:
        raise HTTPException(status_code=404, detail=f"Configuration not found for client {client_id}. Create it first.")

    # Update fields
    for field, value in config_update.items():
        if hasattr(db_config, field) and value is not None:
            setattr(db_config, field, value)

    db.commit()
    db.refresh(db_config)

    # Phase A.1: Invalidate cache after update
    cache = get_cache()
    cache_key = build_cache_key("client_config", client_id)
    cache.delete(cache_key)

    return db_config


def delete_client_config(db: Session, client_id: str, current_user: User) -> bool:
    """
    Delete client configuration (resets to defaults).
    SECURITY: Only admins can delete configs.

    Args:
        db: Database session
        client_id: Client ID
        current_user: Authenticated user

    Returns:
        True if deleted

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 404: If config not found
    """
    # SECURITY: Only admins can delete configs
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete client configurations")

    db_config = db.query(ClientConfig).filter(ClientConfig.client_id == client_id).first()

    if not db_config:
        raise HTTPException(status_code=404, detail=f"Configuration not found for client {client_id}")

    db.delete(db_config)
    db.commit()

    # Phase A.1: Invalidate cache after delete
    cache = get_cache()
    cache_key = build_cache_key("client_config", client_id)
    cache.delete(cache_key)

    return True


def get_all_client_configs(db: Session, current_user: User, skip: int = 0, limit: int = 100) -> list:
    """
    Get all client configurations (for admin overview).
    SECURITY: Only admins can see all configs.

    Args:
        db: Database session
        current_user: Authenticated user
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        List of ClientConfig objects
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view all client configurations")

    return db.query(ClientConfig).offset(skip).limit(limit).all()


def get_global_defaults() -> dict:
    """
    Get global default configuration values.

    Returns:
        Dictionary with default configuration values
    """
    return GLOBAL_DEFAULTS.copy()
