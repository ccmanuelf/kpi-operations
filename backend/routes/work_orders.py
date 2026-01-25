"""
Work Order API Routes
All work order CRUD endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from backend.database import get_db
from backend.models.work_order import (
    WorkOrderCreate,
    WorkOrderUpdate,
    WorkOrderResponse,
    WorkOrderWithMetrics
)
from backend.crud.work_order import (
    create_work_order,
    get_work_order,
    get_work_orders,
    update_work_order,
    delete_work_order,
    get_work_orders_by_client,
    get_work_orders_by_status,
    get_work_orders_by_date_range
)
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User


router = APIRouter(
    prefix="/api/work-orders",
    tags=["Work Orders"]
)


@router.post("", response_model=WorkOrderResponse, status_code=status.HTTP_201_CREATED)
def create_work_order_endpoint(
    work_order: WorkOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create new work order
    SECURITY: Enforces client filtering
    """
    work_order_data = work_order.model_dump()
    return create_work_order(db, work_order_data, current_user)


@router.get("", response_model=List[WorkOrderResponse])
def list_work_orders(
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    style_model: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List work orders with filters
    SECURITY: Returns only work orders for user's authorized clients
    """
    return get_work_orders(db, current_user, skip, limit, client_id, status_filter, style_model)


@router.get("/status/{status}", response_model=List[WorkOrderResponse])
def get_work_orders_by_status_endpoint(
    status: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get work orders by status
    SECURITY: Returns only work orders for user's authorized clients
    """
    return get_work_orders_by_status(db, status, current_user, skip, limit)


@router.get("/date-range", response_model=List[WorkOrderResponse])
def get_work_orders_by_date_range_endpoint(
    start_date: datetime,
    end_date: datetime,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get work orders within date range
    SECURITY: Returns only work orders for user's authorized clients
    """
    return get_work_orders_by_date_range(db, start_date, end_date, current_user, skip, limit)


@router.get("/{work_order_id}", response_model=WorkOrderResponse)
def get_work_order_endpoint(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get work order by ID
    SECURITY: Verifies user has access to work order's client
    """
    work_order = get_work_order(db, work_order_id, current_user)
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")
    return work_order


@router.put("/{work_order_id}", response_model=WorkOrderResponse)
def update_work_order_endpoint(
    work_order_id: str,
    work_order_update: WorkOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update work order
    SECURITY: Verifies user has access to work order's client
    """
    work_order_data = work_order_update.model_dump(exclude_unset=True)
    updated = update_work_order(db, work_order_id, work_order_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")
    return updated


@router.delete("/{work_order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_order_endpoint(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """
    Delete work order (supervisor only)
    SECURITY: Only deletes if user has access to work order's client
    """
    success = delete_work_order(db, work_order_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")


# Client work orders endpoint (separate prefix for /api/clients namespace)
client_work_orders_router = APIRouter(
    prefix="/api/clients",
    tags=["Work Orders"]
)


@client_work_orders_router.get("/{client_id}/work-orders", response_model=List[WorkOrderResponse])
def get_client_work_orders(
    client_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all work orders for a specific client
    SECURITY: Returns only work orders for user's authorized clients
    """
    return get_work_orders_by_client(db, client_id, current_user, skip, limit)
