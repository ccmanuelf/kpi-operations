"""
Work Order Service
Thin service layer wrapping Work Order CRUD operations.
Routes should import from this module instead of backend.crud.work_order directly.
"""

from typing import List, Optional
from datetime import date
from sqlalchemy.orm import Session

from backend.orm.user import User
from backend.crud.work_order import (
    create_work_order,
    get_work_order,
    get_work_orders,
    update_work_order,
    delete_work_order,
    get_work_orders_by_client,
    get_work_orders_by_status,
    get_work_orders_by_date_range,
    get_work_orders_by_capacity_order,
    get_capacity_order_for_work_order,
    link_work_order_to_capacity,
    unlink_work_order_from_capacity,
)


def create_order(db: Session, work_order_data: dict, current_user: User):
    """Create a new work order."""
    return create_work_order(db, work_order_data, current_user)


def get_order(db: Session, work_order_id: str, current_user: User):
    """Get a work order by ID."""
    return get_work_order(db, work_order_id, current_user)


def list_orders(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    style_model: Optional[str] = None,
):
    """List work orders with filters."""
    return get_work_orders(db, current_user, skip, limit, client_id, status, style_model)


def update_order(db: Session, work_order_id: str, work_order_data: dict, current_user: User):
    """Update a work order."""
    return update_work_order(db, work_order_id, work_order_data, current_user)


def delete_order(db: Session, work_order_id: str, current_user: User) -> bool:
    """Delete a work order."""
    return delete_work_order(db, work_order_id, current_user)


def list_orders_by_client(db: Session, client_id: str, current_user: User, skip: int = 0, limit: int = 100):
    """Get work orders for a specific client."""
    return get_work_orders_by_client(db, client_id, current_user, skip, limit)


def list_orders_by_status(db: Session, status: str, current_user: User, skip: int = 0, limit: int = 100):
    """Get work orders by status."""
    return get_work_orders_by_status(db, status, current_user, skip, limit)


def list_orders_by_date_range(
    db: Session, start_date: date, end_date: date, current_user: User, skip: int = 0, limit: int = 100
):
    """Get work orders within a date range."""
    return get_work_orders_by_date_range(db, start_date, end_date, current_user, skip, limit)


def list_orders_by_capacity_order(
    db: Session, capacity_order_id: int, current_user: User, skip: int = 0, limit: int = 100
):
    """Get work orders linked to a capacity order."""
    return get_work_orders_by_capacity_order(db, capacity_order_id, current_user, skip, limit)


def get_capacity_order_link(db: Session, work_order_id: str, current_user: User):
    """Get the capacity order linked to a work order."""
    return get_capacity_order_for_work_order(db, work_order_id, current_user)


def link_to_capacity(db: Session, work_order_id: str, capacity_order_id: int, current_user: User):
    """Link a work order to a capacity order."""
    return link_work_order_to_capacity(db, work_order_id, capacity_order_id, current_user)


def unlink_from_capacity(db: Session, work_order_id: str, current_user: User):
    """Unlink a work order from its capacity order."""
    return unlink_work_order_from_capacity(db, work_order_id, current_user)
