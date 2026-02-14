"""
CRUD operations for Capacity Orders

Provides operations for managing planning orders used in capacity
planning and scheduling. Separate from operational work orders.

Multi-tenant: All operations enforce client_id isolation.
"""

from typing import List, Optional
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from backend.schemas.capacity.orders import CapacityOrder, OrderStatus, OrderPriority
from backend.utils.tenant_guard import ensure_client_id


def create_order(
    db: Session,
    client_id: str,
    order_number: str,
    style_code: str,
    order_quantity: int,
    required_date: date,
    customer_name: Optional[str] = None,
    style_description: Optional[str] = None,
    order_date: Optional[date] = None,
    planned_start_date: Optional[date] = None,
    planned_end_date: Optional[date] = None,
    priority: OrderPriority = OrderPriority.NORMAL,
    status: OrderStatus = OrderStatus.DRAFT,
    order_sam_minutes: Optional[float] = None,
    notes: Optional[str] = None,
) -> CapacityOrder:
    """
    Create a new capacity planning order.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        order_number: Unique order number
        style_code: Style/product code
        order_quantity: Quantity ordered
        required_date: Customer need date
        customer_name: Customer name
        style_description: Style description
        order_date: Date order was received
        planned_start_date: Planned production start
        planned_end_date: Planned production end
        priority: Order priority (LOW, NORMAL, HIGH, URGENT)
        status: Order status (DRAFT, CONFIRMED, etc.)
        order_sam_minutes: Order-specific SAM override
        notes: Additional notes

    Returns:
        Created CapacityOrder
    """
    ensure_client_id(client_id, "order creation")

    order = CapacityOrder(
        client_id=client_id,
        order_number=order_number,
        customer_name=customer_name,
        style_code=style_code,
        style_description=style_description,
        order_quantity=order_quantity,
        completed_quantity=0,
        order_date=order_date,
        required_date=required_date,
        planned_start_date=planned_start_date,
        planned_end_date=planned_end_date,
        priority=priority,
        status=status,
        order_sam_minutes=Decimal(str(order_sam_minutes)) if order_sam_minutes else None,
        notes=notes,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_orders(
    db: Session, client_id: str, skip: int = 0, limit: int = 100, status_filter: Optional[str] = None
) -> List[CapacityOrder]:
    """
    Get all orders for a client.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        skip: Number of records to skip (pagination)
        limit: Maximum records to return
        status_filter: Optional status to filter by

    Returns:
        List of CapacityOrder entries
    """
    ensure_client_id(client_id, "orders query")
    query = db.query(CapacityOrder).filter(CapacityOrder.client_id == client_id)
    if status_filter:
        query = query.filter(CapacityOrder.status == status_filter)
    return query.order_by(CapacityOrder.required_date).offset(skip).limit(limit).all()


def get_order(db: Session, client_id: str, order_id: int) -> Optional[CapacityOrder]:
    """
    Get a specific order by ID.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        order_id: Order ID

    Returns:
        CapacityOrder or None if not found
    """
    ensure_client_id(client_id, "order query")
    return (
        db.query(CapacityOrder).filter(and_(CapacityOrder.client_id == client_id, CapacityOrder.id == order_id)).first()
    )


def get_order_by_number(db: Session, client_id: str, order_number: str) -> Optional[CapacityOrder]:
    """
    Get a specific order by order number.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        order_number: Order number

    Returns:
        CapacityOrder or None if not found
    """
    ensure_client_id(client_id, "order query")
    return (
        db.query(CapacityOrder)
        .filter(and_(CapacityOrder.client_id == client_id, CapacityOrder.order_number == order_number))
        .first()
    )


def update_order(db: Session, client_id: str, order_id: int, **updates) -> Optional[CapacityOrder]:
    """
    Update an order.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        order_id: Order ID to update
        **updates: Fields to update

    Returns:
        Updated CapacityOrder or None if not found
    """
    order = get_order(db, client_id, order_id)
    if not order:
        return None

    for key, value in updates.items():
        if hasattr(order, key) and value is not None:
            if key == "order_sam_minutes" and value is not None:
                value = Decimal(str(value))
            setattr(order, key, value)

    db.commit()
    db.refresh(order)
    return order


def delete_order(db: Session, client_id: str, order_id: int) -> bool:
    """
    Delete an order.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        order_id: Order ID to delete

    Returns:
        True if deleted, False if not found
    """
    order = get_order(db, client_id, order_id)
    if not order:
        return False

    db.delete(order)
    db.commit()
    return True


def get_orders_for_scheduling(
    db: Session, client_id: str, start_date: Optional[date] = None, end_date: Optional[date] = None
) -> List[CapacityOrder]:
    """
    Get orders ready for scheduling.

    Returns orders that are CONFIRMED or SCHEDULED status within
    the optional date range.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        start_date: Optional start date filter (on required_date)
        end_date: Optional end date filter (on required_date)

    Returns:
        List of CapacityOrder entries ready for scheduling
    """
    ensure_client_id(client_id, "scheduling orders query")

    filters = [
        CapacityOrder.client_id == client_id,
        CapacityOrder.status.in_([OrderStatus.CONFIRMED, OrderStatus.SCHEDULED]),
    ]

    if start_date:
        filters.append(CapacityOrder.required_date >= start_date)
    if end_date:
        filters.append(CapacityOrder.required_date <= end_date)

    return (
        db.query(CapacityOrder)
        .filter(and_(*filters))
        .order_by(CapacityOrder.priority.desc(), CapacityOrder.required_date)
        .all()
    )


def get_orders_by_status(db: Session, client_id: str, status: OrderStatus) -> List[CapacityOrder]:
    """
    Get orders by status.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        status: Order status to filter by

    Returns:
        List of CapacityOrder entries with the given status
    """
    ensure_client_id(client_id, "orders by status query")
    return (
        db.query(CapacityOrder)
        .filter(and_(CapacityOrder.client_id == client_id, CapacityOrder.status == status))
        .order_by(CapacityOrder.required_date)
        .all()
    )


def get_orders_by_style(db: Session, client_id: str, style_code: str) -> List[CapacityOrder]:
    """
    Get orders by style code.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        style_code: Style code to filter by

    Returns:
        List of CapacityOrder entries for the style
    """
    ensure_client_id(client_id, "orders by style query")
    return (
        db.query(CapacityOrder)
        .filter(and_(CapacityOrder.client_id == client_id, CapacityOrder.style_code == style_code))
        .order_by(CapacityOrder.required_date)
        .all()
    )


def update_order_status(db: Session, client_id: str, order_id: int, new_status: OrderStatus) -> Optional[CapacityOrder]:
    """
    Update order status.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        order_id: Order ID to update
        new_status: New status to set

    Returns:
        Updated CapacityOrder or None if not found
    """
    return update_order(db, client_id, order_id, status=new_status)


def update_order_progress(
    db: Session, client_id: str, order_id: int, completed_quantity: int
) -> Optional[CapacityOrder]:
    """
    Update order production progress.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        order_id: Order ID to update
        completed_quantity: New completed quantity

    Returns:
        Updated CapacityOrder or None if not found
    """
    order = get_order(db, client_id, order_id)
    if not order:
        return None

    order.completed_quantity = completed_quantity

    # Auto-update status if completed
    if completed_quantity >= order.order_quantity:
        order.status = OrderStatus.COMPLETED

    db.commit()
    db.refresh(order)
    return order


def get_overdue_orders(db: Session, client_id: str, as_of_date: Optional[date] = None) -> List[CapacityOrder]:
    """
    Get orders that are overdue.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        as_of_date: Date to check against (defaults to today)

    Returns:
        List of overdue CapacityOrder entries
    """
    ensure_client_id(client_id, "overdue orders query")

    check_date = as_of_date or date.today()

    return (
        db.query(CapacityOrder)
        .filter(
            and_(
                CapacityOrder.client_id == client_id,
                CapacityOrder.required_date < check_date,
                CapacityOrder.status.notin_([OrderStatus.COMPLETED, OrderStatus.CANCELLED]),
            )
        )
        .order_by(CapacityOrder.required_date)
        .all()
    )


def get_priority_orders(
    db: Session, client_id: str, min_priority: OrderPriority = OrderPriority.HIGH
) -> List[CapacityOrder]:
    """
    Get high priority orders.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        min_priority: Minimum priority level (default HIGH)

    Returns:
        List of high priority CapacityOrder entries
    """
    ensure_client_id(client_id, "priority orders query")

    priority_values = {OrderPriority.LOW: 1, OrderPriority.NORMAL: 2, OrderPriority.HIGH: 3, OrderPriority.URGENT: 4}

    min_value = priority_values.get(min_priority, 3)
    high_priorities = [p for p, v in priority_values.items() if v >= min_value]

    return (
        db.query(CapacityOrder)
        .filter(
            and_(
                CapacityOrder.client_id == client_id,
                CapacityOrder.priority.in_(high_priorities),
                CapacityOrder.status.notin_([OrderStatus.COMPLETED, OrderStatus.CANCELLED]),
            )
        )
        .order_by(CapacityOrder.priority.desc(), CapacityOrder.required_date)
        .all()
    )
