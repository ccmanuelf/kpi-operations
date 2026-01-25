"""
Client Management API Routes
All client CRUD endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.models.client import (
    ClientCreate,
    ClientUpdate,
    ClientResponse,
    ClientSummary
)
from backend.crud.client import (
    create_client,
    get_client,
    get_clients,
    update_client,
    delete_client,
    get_active_clients
)
from backend.auth.jwt import get_current_user
from backend.schemas.user import User


router = APIRouter(
    prefix="/api/clients",
    tags=["Clients"]
)


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client_endpoint(
    client: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new client
    SECURITY: Admin only
    """
    client_data = client.model_dump()
    return create_client(db, client_data, current_user)


@router.get("", response_model=List[ClientResponse])
def list_clients(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List clients with filters
    SECURITY: Returns only clients user has access to
    """
    return get_clients(db, current_user, skip, limit, is_active)


@router.get("/active/list", response_model=List[ClientResponse])
def get_active_clients_endpoint(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all active clients
    SECURITY: Returns only clients user has access to
    """
    return get_active_clients(db, current_user, skip, limit)


@router.get("/{client_id}", response_model=ClientResponse)
def get_client_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get client by ID
    SECURITY: Verifies user has access to client
    """
    client = get_client(db, client_id, current_user)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found or access denied")
    return client


@router.put("/{client_id}", response_model=ClientResponse)
def update_client_endpoint(
    client_id: str,
    client_update: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update client
    SECURITY: Verifies user has access to client
    """
    client_data = client_update.model_dump(exclude_unset=True)
    updated = update_client(db, client_id, client_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Client not found or access denied")
    return updated


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete client (soft delete - admin only)
    SECURITY: Admin only
    """
    success = delete_client(db, client_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Client not found or access denied")
