"""
Database Configuration API Endpoints

Provides admin read-only diagnostics for:
- Checking current database provider status
- Listing available database providers

Runtime database migration was removed (D1): schema evolution is handled by
Alembic at deploy time, not via an in-app HTTP endpoint.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Any, Dict

from backend.database import engine
from backend.db.factory import DatabaseProviderFactory

from backend.auth.jwt import get_current_active_supervisor
from backend.orm.user import User

router = APIRouter(
    prefix="/api/admin/database",
    tags=["database-config"],
    responses={404: {"description": "Not found"}},
)


# ============================================================================
# Request/Response Models
# ============================================================================


class DatabaseStatus(BaseModel):
    """Current database provider status."""

    current_provider: str
    connection_info: Dict[str, Any] = Field(default_factory=dict)


class AvailableProvidersResponse(BaseModel):
    """Available database providers."""

    providers: Dict[str, Dict[str, Any]]


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/status", response_model=DatabaseStatus)
async def get_database_status(
    current_user: User = Depends(get_current_active_supervisor),
) -> Any:
    """Get current database provider status.

    Provider and connection info are derived from the live application engine
    (the ONLY database the app is bound to), so the response reflects reality
    in every environment. Schema evolution is handled by Alembic at deploy
    time. Requires supervisor or admin role.
    """
    factory = DatabaseProviderFactory.get_instance()
    provider = factory.create_provider(str(engine.url))

    return DatabaseStatus(
        current_provider=provider.provider_name,
        connection_info=provider.get_connection_info(engine),
    )


@router.get("/providers", response_model=AvailableProvidersResponse)
async def get_available_providers(
    current_user: User = Depends(get_current_active_supervisor),
) -> Any:
    """Get information about available database providers.

    Requires supervisor or admin role.
    """
    factory = DatabaseProviderFactory.get_instance()
    return AvailableProvidersResponse(providers=factory.get_available_providers())
