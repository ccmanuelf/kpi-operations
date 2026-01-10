"""
CRUD operations for Work Order
Create, Read, Update, Delete with multi-tenant security
SECURITY: Multi-tenant client filtering enabled
"""
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import HTTPException

from backend.schemas.work_order import WorkOrder, WorkOrderStatus
from backend.schemas.user import User
from middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.utils.soft_delete import soft_delete


def create_work_order(
    db: Session,
    work_order_data: dict,
    current_user: User
) -> WorkOrder:
    """
    Create new work order
    SECURITY: Verifies user has access to the specified client

    Args:
        db: Database session
        work_order_data: Work order data dictionary
        current_user: Authenticated user

    Returns:
        Created work order

    Raises:
        HTTPException 400: If validation fails
        HTTPException 403: If user doesn't have access to client
    """
    # SECURITY: Verify user has access to this client
    if 'client_id' in work_order_data and work_order_data['client_id']:
        verify_client_access(current_user, work_order_data['client_id'])

    # Create work order
    db_work_order = WorkOrder(**work_order_data)

    db.add(db_work_order)
    db.commit()
    db.refresh(db_work_order)

    return db_work_order


def get_work_order(
    db: Session,
    work_order_id: str,
    current_user: User
) -> Optional[WorkOrder]:
    """
    Get work order by ID
    SECURITY: Verifies user has access to the work order's client

    Args:
        db: Database session
        work_order_id: Work order ID
        current_user: Authenticated user

    Returns:
        Work order or None if not found

    Raises:
        HTTPException 404: If work order not found
        HTTPException 403: If user doesn't have access to work order's client
    """
    work_order = db.query(WorkOrder).filter(
        WorkOrder.work_order_id == work_order_id
    ).first()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    # SECURITY: Verify user has access to this work order's client
    if hasattr(work_order, 'client_id') and work_order.client_id:
        verify_client_access(current_user, work_order.client_id)

    return work_order


def get_work_orders(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    style_model: Optional[str] = None
) -> List[WorkOrder]:
    """
    Get work orders with filtering
    SECURITY: Automatically filters by user's authorized clients

    Args:
        db: Database session
        current_user: Authenticated user
        skip: Number of records to skip
        limit: Maximum records to return
        client_id: Filter by client
        status: Filter by status
        style_model: Filter by style/model

    Returns:
        List of work orders (filtered by user's client access)
    """
    query = db.query(WorkOrder)

    # SECURITY: Apply client filtering based on user's role
    client_filter = build_client_filter_clause(current_user, WorkOrder.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Apply additional filters
    if client_id:
        query = query.filter(WorkOrder.client_id == client_id)
    if status:
        query = query.filter(WorkOrder.status == status)
    if style_model:
        query = query.filter(WorkOrder.style_model.like(f"%{style_model}%"))

    return query.order_by(
        WorkOrder.created_at.desc()
    ).offset(skip).limit(limit).all()


def update_work_order(
    db: Session,
    work_order_id: str,
    work_order_update: dict,
    current_user: User
) -> Optional[WorkOrder]:
    """
    Update work order
    SECURITY: Verifies user has access to the work order's client

    Args:
        db: Database session
        work_order_id: Work order ID to update
        work_order_update: Update data dictionary
        current_user: Authenticated user

    Returns:
        Updated work order or None if not found

    Raises:
        HTTPException 404: If work order not found
        HTTPException 403: If user doesn't have access to work order's client
    """
    db_work_order = db.query(WorkOrder).filter(
        WorkOrder.work_order_id == work_order_id
    ).first()

    if not db_work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    # SECURITY: Verify user has access to this work order's client
    if hasattr(db_work_order, 'client_id') and db_work_order.client_id:
        verify_client_access(current_user, db_work_order.client_id)

    # Update fields
    for field, value in work_order_update.items():
        if hasattr(db_work_order, field):
            setattr(db_work_order, field, value)

    db.commit()
    db.refresh(db_work_order)

    return db_work_order


def delete_work_order(
    db: Session,
    work_order_id: str,
    current_user: User
) -> bool:
    """
    Soft delete work order (sets is_active = False)
    SECURITY: Verifies user has access to the work order's client

    Args:
        db: Database session
        work_order_id: Work order ID to delete
        current_user: Authenticated user

    Returns:
        True if soft deleted, False if not found

    Raises:
        HTTPException 404: If work order not found
        HTTPException 403: If user doesn't have access to work order's client
    """
    db_work_order = db.query(WorkOrder).filter(
        WorkOrder.work_order_id == work_order_id
    ).first()

    if not db_work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    # SECURITY: Verify user has access to this work order's client
    if hasattr(db_work_order, 'client_id') and db_work_order.client_id:
        verify_client_access(current_user, db_work_order.client_id)

    # Soft delete - preserves data integrity
    return soft_delete(db, db_work_order)


def get_work_orders_by_client(
    db: Session,
    client_id: str,
    current_user: User,
    skip: int = 0,
    limit: int = 100
) -> List[WorkOrder]:
    """
    Get all work orders for a specific client
    SECURITY: Verifies user has access to the client

    Args:
        db: Database session
        client_id: Client ID
        current_user: Authenticated user
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        List of work orders for the client

    Raises:
        HTTPException 403: If user doesn't have access to client
    """
    # SECURITY: Verify user has access to this client
    verify_client_access(current_user, client_id)

    return db.query(WorkOrder).filter(
        WorkOrder.client_id == client_id
    ).order_by(
        WorkOrder.created_at.desc()
    ).offset(skip).limit(limit).all()


def get_work_orders_by_status(
    db: Session,
    status: str,
    current_user: User,
    skip: int = 0,
    limit: int = 100
) -> List[WorkOrder]:
    """
    Get work orders by status
    SECURITY: Automatically filters by user's authorized clients

    Args:
        db: Database session
        status: Work order status
        current_user: Authenticated user
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        List of work orders with specified status (filtered by user's client access)
    """
    query = db.query(WorkOrder).filter(WorkOrder.status == status)

    # SECURITY: Apply client filtering
    client_filter = build_client_filter_clause(current_user, WorkOrder.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.order_by(
        WorkOrder.created_at.desc()
    ).offset(skip).limit(limit).all()


def get_work_orders_by_date_range(
    db: Session,
    start_date: datetime,
    end_date: datetime,
    current_user: User,
    skip: int = 0,
    limit: int = 100
) -> List[WorkOrder]:
    """
    Get work orders within date range (by planned_ship_date)
    SECURITY: Automatically filters by user's authorized clients

    Args:
        db: Database session
        start_date: Start date
        end_date: End date
        current_user: Authenticated user
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        List of work orders within date range (filtered by user's client access)
    """
    query = db.query(WorkOrder).filter(
        and_(
            WorkOrder.planned_ship_date >= start_date,
            WorkOrder.planned_ship_date <= end_date
        )
    )

    # SECURITY: Apply client filtering
    client_filter = build_client_filter_clause(current_user, WorkOrder.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.order_by(
        WorkOrder.planned_ship_date
    ).offset(skip).limit(limit).all()
