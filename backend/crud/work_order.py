"""
CRUD operations for Work Order
Create, Read, Update, Delete with multi-tenant security
SECURITY: Multi-tenant client filtering enabled
Phase 10: Integrated with Workflow State Machine
"""

import logging
from typing import List, Optional
from datetime import date, datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import HTTPException

logger = logging.getLogger(__name__)

from sqlalchemy.exc import SQLAlchemyError

from backend.orm.work_order import WorkOrder, WorkOrderStatus
from backend.orm.user import User
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.utils.soft_delete import soft_delete
from backend.calculations.workflow_engine import WorkflowStateMachine, execute_transition


def create_work_order(db: Session, work_order_data: dict, current_user: User) -> WorkOrder:
    """
    Create new work order
    SECURITY: Verifies user has access to the specified client
    Phase 10: Logs initial transition and sets received_date

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
    if "client_id" in work_order_data and work_order_data["client_id"]:
        verify_client_access(current_user, work_order_data["client_id"])

    # Phase 10: Set default status to RECEIVED if not specified
    if "status" not in work_order_data or not work_order_data["status"]:
        work_order_data["status"] = "RECEIVED"

    # Phase 10: Set received_date if not provided
    if "received_date" not in work_order_data or not work_order_data["received_date"]:
        work_order_data["received_date"] = datetime.now(tz=timezone.utc)

    # Create work order
    db_work_order = WorkOrder(**work_order_data)

    db.add(db_work_order)
    db.flush()
    db.refresh(db_work_order)

    # Phase 10: Log initial status transition
    try:
        from backend.orm.workflow import WorkflowTransitionLog

        initial_log = WorkflowTransitionLog(
            work_order_id=db_work_order.work_order_id,
            client_id=db_work_order.client_id,
            from_status=None,
            to_status=db_work_order.status,
            transitioned_by=current_user.user_id if current_user else None,
            transitioned_at=datetime.now(tz=timezone.utc),
            notes="Initial creation",
            trigger_source="api",
        )
        db.add(initial_log)
        db.flush()
    except SQLAlchemyError as e:
        # Don't fail creation if logging fails
        logger.exception("Failed to log initial status transition for work_order_id=%s", db_work_order.work_order_id)

    return db_work_order


def get_work_order(db: Session, work_order_id: str, current_user: User) -> Optional[WorkOrder]:
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
    work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == work_order_id).first()

    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    # SECURITY: Verify user has access to this work order's client
    if hasattr(work_order, "client_id") and work_order.client_id:
        verify_client_access(current_user, work_order.client_id)

    return work_order


def get_work_orders(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[str] = None,
    status: Optional[str] = None,
    style_model: Optional[str] = None,
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

    return query.order_by(WorkOrder.created_at.desc()).offset(skip).limit(limit).all()


def update_work_order(
    db: Session,
    work_order_id: str,
    work_order_update: dict,
    current_user: User,
    validate_status_transition: bool = True,
) -> Optional[WorkOrder]:
    """
    Update work order
    SECURITY: Verifies user has access to the work order's client
    Phase 10: Validates status transitions through workflow state machine

    Args:
        db: Database session
        work_order_id: Work order ID to update
        work_order_update: Update data dictionary
        current_user: Authenticated user
        validate_status_transition: If True, validate status changes (default True)

    Returns:
        Updated work order or None if not found

    Raises:
        HTTPException 404: If work order not found
        HTTPException 403: If user doesn't have access to work order's client
        HTTPException 400: If status transition is invalid (Phase 10)
    """
    db_work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == work_order_id).first()

    if not db_work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    # SECURITY: Verify user has access to this work order's client
    if hasattr(db_work_order, "client_id") and db_work_order.client_id:
        verify_client_access(current_user, db_work_order.client_id)

    # Phase 10: Validate status transition if status is being changed
    new_status = work_order_update.get("status")
    if new_status and new_status != db_work_order.status and validate_status_transition:
        sm = WorkflowStateMachine(db, db_work_order.client_id)
        is_valid, reason = sm.validate_transition(db_work_order, new_status)

        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid status transition: {reason}")

        # Store previous status for ON_HOLD tracking
        old_status = db_work_order.status

        # Update status and log transition. NOTE: WorkflowTransitionLog
        # and WorkOrder.closed_by are Mapped[Optional[int]] in the ORM,
        # but the FK references USER.user_id which is a String(50).
        # That's a pre-existing schema inconsistency outside this fix.
        # User.user_id is `str`, so coerce when it parses as int and
        # log None otherwise — the alternative was passing a str into
        # an int column and triggering an SQLAlchemy type error.
        user_id_int: Optional[int] = None
        if current_user is not None:
            try:
                user_id_int = int(current_user.user_id)
            except (TypeError, ValueError):
                user_id_int = None

        try:
            db_work_order, transition_log = execute_transition(
                db=db,
                work_order=db_work_order,
                to_status=new_status,
                user_id=user_id_int,
                notes=work_order_update.get("notes"),
                trigger_source="api",
            )
            # Remove status from update dict since it's already handled
            work_order_update = {k: v for k, v in work_order_update.items() if k != "status"}
        except HTTPException:
            raise
        except SQLAlchemyError as e:
            # Log but don't fail the update
            logger.exception("Database error executing status transition for work_order_id=%s", work_order_id)

    # Update remaining fields
    for field, value in work_order_update.items():
        if hasattr(db_work_order, field):
            setattr(db_work_order, field, value)

    db.flush()
    db.refresh(db_work_order)

    return db_work_order


def delete_work_order(db: Session, work_order_id: str, current_user: User) -> bool:
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
    db_work_order = db.query(WorkOrder).filter(WorkOrder.work_order_id == work_order_id).first()

    if not db_work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    # SECURITY: Verify user has access to this work order's client
    if hasattr(db_work_order, "client_id") and db_work_order.client_id:
        verify_client_access(current_user, db_work_order.client_id)

    # Soft delete - preserves data integrity (commit=False: route handler commits)
    return soft_delete(db, db_work_order, commit=False)


def get_work_orders_by_client(
    db: Session, client_id: str, current_user: User, skip: int = 0, limit: int = 100
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

    return (
        db.query(WorkOrder)
        .filter(WorkOrder.client_id == client_id)
        .order_by(WorkOrder.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_work_orders_by_status(
    db: Session, status: str, current_user: User, skip: int = 0, limit: int = 100
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

    return query.order_by(WorkOrder.created_at.desc()).offset(skip).limit(limit).all()


def get_work_orders_by_date_range(
    db: Session, start_date: datetime, end_date: datetime, current_user: User, skip: int = 0, limit: int = 100
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
        and_(WorkOrder.planned_ship_date >= start_date, WorkOrder.planned_ship_date <= end_date)
    )

    # SECURITY: Apply client filtering
    client_filter = build_client_filter_clause(current_user, WorkOrder.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    return query.order_by(WorkOrder.planned_ship_date).offset(skip).limit(limit).all()


# ============================================================================
# Cross-Reference: Work Orders <-> Capacity Orders (Task 3.1)
# ============================================================================


def get_work_orders_by_capacity_order(
    db: Session, capacity_order_id: int, current_user: User, skip: int = 0, limit: int = 100
) -> List[WorkOrder]:
    """Get all work orders linked to a specific capacity order."""
    query = db.query(WorkOrder).filter(WorkOrder.capacity_order_id == capacity_order_id)
    client_filter = build_client_filter_clause(current_user, WorkOrder.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)
    return query.order_by(WorkOrder.created_at.desc()).offset(skip).limit(limit).all()


def get_capacity_order_for_work_order(db: Session, work_order_id: str, current_user: User):
    """Get the capacity order linked to a work order. Returns None if no link."""
    from backend.orm.capacity.orders import CapacityOrder

    work_order = get_work_order(db, work_order_id, current_user)
    if not work_order or not work_order.capacity_order_id:
        return None
    return db.query(CapacityOrder).filter(CapacityOrder.id == work_order.capacity_order_id).first()


def link_work_order_to_capacity(
    db: Session, work_order_id: str, capacity_order_id: int, current_user: User
) -> WorkOrder:
    """Link a work order to a capacity order. Sets origin to PLANNED."""
    work_order = get_work_order(db, work_order_id, current_user)
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")
    # Verify capacity order exists
    from backend.orm.capacity.orders import CapacityOrder

    cap_order = db.query(CapacityOrder).filter(CapacityOrder.id == capacity_order_id).first()
    if not cap_order:
        raise HTTPException(status_code=404, detail="Capacity order not found")
    work_order.capacity_order_id = capacity_order_id
    work_order.origin = "PLANNED"
    db.flush()
    db.refresh(work_order)
    return work_order


def unlink_work_order_from_capacity(db: Session, work_order_id: str, current_user: User) -> WorkOrder:
    """Unlink a work order from its capacity order. Sets origin to AD_HOC."""
    work_order = get_work_order(db, work_order_id, current_user)
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")
    work_order.capacity_order_id = None
    work_order.origin = "AD_HOC"
    db.flush()
    db.refresh(work_order)
    return work_order
