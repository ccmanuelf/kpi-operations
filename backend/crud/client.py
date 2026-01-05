"""
CRUD operations for Client
Create, Read, Update, Delete with multi-tenant security
SECURITY: Multi-tenant client filtering enabled
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from backend.schemas.client import Client
from backend.schemas.user import User
from middleware.client_auth import verify_client_access, build_client_filter_clause


def create_client(
    db: Session,
    client_data: dict,
    current_user: User
) -> Client:
    """
    Create new client
    SECURITY: Only admins can create clients

    Args:
        db: Database session
        client_data: Client data dictionary
        current_user: Authenticated user

    Returns:
        Created client

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 400: If client_id already exists
    """
    # SECURITY: Only admins can create clients
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=403,
            detail="Only admins can create clients"
        )

    # Check if client_id already exists
    existing = db.query(Client).filter(
        Client.client_id == client_data.get('client_id')
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Client with ID {client_data.get('client_id')} already exists"
        )

    # Create client
    db_client = Client(**client_data)

    db.add(db_client)
    db.commit()
    db.refresh(db_client)

    return db_client


def get_client(
    db: Session,
    client_id: str,
    current_user: User
) -> Optional[Client]:
    """
    Get client by ID
    SECURITY: Verifies user has access to the client

    Args:
        db: Database session
        client_id: Client ID
        current_user: Authenticated user

    Returns:
        Client or None if not found

    Raises:
        HTTPException 404: If client not found
        HTTPException 403: If user doesn't have access to client
    """
    client = db.query(Client).filter(
        Client.client_id == client_id
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # SECURITY: Verify user has access to this client
    verify_client_access(current_user, client_id)

    return client


def get_clients(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None
) -> List[Client]:
    """
    Get clients with filtering
    SECURITY: Automatically filters by user's authorized clients

    Args:
        db: Database session
        current_user: Authenticated user
        skip: Number of records to skip
        limit: Maximum records to return
        is_active: Filter by active status

    Returns:
        List of clients (filtered by user's client access)
    """
    query = db.query(Client)

    # SECURITY: Apply client filtering based on user's role
    client_filter = build_client_filter_clause(current_user, Client.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Apply additional filters
    if is_active is not None:
        query = query.filter(Client.is_active == (1 if is_active else 0))

    return query.order_by(
        Client.client_name
    ).offset(skip).limit(limit).all()


def update_client(
    db: Session,
    client_id: str,
    client_update: dict,
    current_user: User
) -> Optional[Client]:
    """
    Update client
    SECURITY: Verifies user has access to the client

    Args:
        db: Database session
        client_id: Client ID to update
        client_update: Update data dictionary
        current_user: Authenticated user

    Returns:
        Updated client or None if not found

    Raises:
        HTTPException 404: If client not found
        HTTPException 403: If user doesn't have access to client
    """
    db_client = db.query(Client).filter(
        Client.client_id == client_id
    ).first()

    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")

    # SECURITY: Verify user has access to this client
    verify_client_access(current_user, client_id)

    # Update fields
    for field, value in client_update.items():
        if hasattr(db_client, field) and field != 'client_id':  # Don't allow changing PK
            setattr(db_client, field, value)

    db.commit()
    db.refresh(db_client)

    return db_client


def delete_client(
    db: Session,
    client_id: str,
    current_user: User
) -> bool:
    """
    Delete client (soft delete by setting is_active=0)
    SECURITY: Only admins can delete clients

    Args:
        db: Database session
        client_id: Client ID to delete
        current_user: Authenticated user

    Returns:
        True if deleted, False if not found

    Raises:
        HTTPException 403: If user is not admin
        HTTPException 404: If client not found
    """
    # SECURITY: Only admins can delete clients
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=403,
            detail="Only admins can delete clients"
        )

    db_client = db.query(Client).filter(
        Client.client_id == client_id
    ).first()

    if not db_client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Soft delete
    db_client.is_active = 0
    db.commit()

    return True


def get_active_clients(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100
) -> List[Client]:
    """
    Get all active clients
    SECURITY: Automatically filters by user's authorized clients

    Args:
        db: Database session
        current_user: Authenticated user
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        List of active clients (filtered by user's client access)
    """
    query = db.query(Client).filter(Client.is_active == 1)

    # SECURITY: Apply client filtering
    client_filter = build_client_filter_clause(current_user, Client.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.order_by(
        Client.client_name
    ).offset(skip).limit(limit).all()
