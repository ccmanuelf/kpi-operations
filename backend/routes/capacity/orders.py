"""
Capacity Planning - Orders Endpoints

Planning order CRUD operations and scheduling queries.
"""

import logging
from typing import List, Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.constants import DEFAULT_PAGE_SIZE
from backend.crud.capacity import orders
from backend.schemas.capacity.orders import OrderStatus

from ._models import (
    OrderCreate,
    OrderUpdate,
    OrderResponse,
    MessageResponse,
)

logger = logging.getLogger(__name__)

orders_router = APIRouter()


@orders_router.get("/orders", response_model=List[OrderResponse])
def list_orders(
    client_id: str = Query(..., description="Client ID"),
    status_filter: Optional[OrderStatus] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get orders for a client."""
    verify_client_access(current_user, client_id, db)
    return orders.get_orders(db, client_id, skip, limit, status_filter)


@orders_router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order: OrderCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new order."""
    verify_client_access(current_user, client_id, db)
    return orders.create_order(
        db,
        client_id,
        order.order_number,
        order.style_code,
        order.order_quantity,
        order.required_date,
        order.customer_name,
        order.style_description,
        order.order_date,
        order.planned_start_date,
        order.planned_end_date,
        order.priority,
        order.status,
        order.order_sam_minutes,
        order.notes,
    )


@orders_router.get("/orders/scheduling", response_model=List[OrderResponse])
def get_orders_for_scheduling(
    client_id: str = Query(..., description="Client ID"),
    start_date: date = Query(..., description="Schedule period start"),
    end_date: date = Query(..., description="Schedule period end"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get confirmed orders ready for scheduling within a date range."""
    verify_client_access(current_user, client_id, db)
    return orders.get_orders_for_scheduling(db, client_id, start_date, end_date)


@orders_router.get("/orders/{order_id}", response_model=OrderResponse, responses={404: {"description": "Order not found"}})
def get_order(
    order_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific order."""
    verify_client_access(current_user, client_id, db)
    order = orders.get_order(db, client_id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@orders_router.put("/orders/{order_id}", response_model=OrderResponse, responses={404: {"description": "Order not found"}})
def update_order(
    order_id: int,
    update: OrderUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an order."""
    verify_client_access(current_user, client_id, db)
    order = orders.update_order(db, client_id, order_id, **update.model_dump(exclude_unset=True))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@orders_router.patch("/orders/{order_id}/status", response_model=OrderResponse, responses={404: {"description": "Order not found"}})
def update_order_status(
    order_id: int,
    new_status: OrderStatus,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update order status."""
    verify_client_access(current_user, client_id, db)
    order = orders.update_order_status(db, client_id, order_id, new_status)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@orders_router.delete("/orders/{order_id}", response_model=MessageResponse, responses={404: {"description": "Order not found"}})
def delete_order(
    order_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an order."""
    verify_client_access(current_user, client_id, db)
    if not orders.delete_order(db, client_id, order_id):
        raise HTTPException(status_code=404, detail="Order not found")
    return {"message": "Order deleted"}
