"""
Client Service
Thin service layer wrapping Client CRUD operations.
Routes should import from this module instead of backend.crud.client directly.
"""

from typing import Any, Optional
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.crud.client import (
    create_client,
    get_client,
    get_clients,
    update_client,
    delete_client,
    get_active_clients,
)


def create_client_record(db: Session, client_data: dict, current_user: User) -> Any:
    """Create a new client."""
    return create_client(db, client_data, current_user)


def get_client_by_id(db: Session, client_id: str, current_user: User) -> Any:
    """Get client by ID with access control."""
    return get_client(db, client_id, current_user)


def list_clients(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
) -> Any:
    """List clients with optional filters."""
    return get_clients(db, current_user, skip, limit, is_active)


def update_client_record(db: Session, client_id: str, client_update: dict, current_user: User) -> Any:
    """Update a client record."""
    return update_client(db, client_id, client_update, current_user)


def delete_client_record(db: Session, client_id: str, current_user: User) -> bool:
    """Delete a client record."""
    return delete_client(db, client_id, current_user)


def list_active_clients(db: Session, current_user: User, skip: int = 0, limit: int = 100) -> Any:
    """Get active clients."""
    return get_active_clients(db, current_user, skip, limit)
