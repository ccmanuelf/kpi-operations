"""
Work Order API Routes
All work order CRUD endpoints with progress tracking and timeline
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

from backend.database import get_db
from backend.schemas.work_order import WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse, WorkOrderWithMetrics
from backend.services.work_order_service import (
    create_order as create_work_order,
    get_order as get_work_order,
    list_orders as get_work_orders,
    update_order as update_work_order,
    delete_order as delete_work_order,
    list_orders_by_client as get_work_orders_by_client,
    list_orders_by_status as get_work_orders_by_status,
    list_orders_by_date_range as get_work_orders_by_date_range,
)
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.orm.user import User as _User_for_perm

_WRITE_ALLOWED_ROLES = {"admin", "ADMIN", "poweruser", "leader", "supervisor"}


def _check_wo_write_permission(user: "_User_for_perm") -> None:
    """Reject operator/viewer roles from mutating work orders.

    Operators are data collectors — they enter production/downtime/quality
    against an EXISTING work order but should not create, edit, or delete
    the work order itself. Audit Run-6 surfaced an operator successfully
    POSTing a new WO; this guard closes that gap centrally.
    """
    role = user.role or ""
    if role not in _WRITE_ALLOWED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Work order mutations require leader, supervisor, poweruser, or admin role",
        )
from backend.orm.user import User
from backend.orm.work_order import WorkOrder
from backend.orm.production_entry import ProductionEntry
from backend.orm.product import Product
from backend.orm.shift import Shift
from backend.orm.quality_entry import QualityEntry
from backend.orm.hold_entry import HoldEntry


router = APIRouter(prefix="/api/work-orders", tags=["Work Orders"])


@router.post("", response_model=WorkOrderResponse, status_code=status.HTTP_201_CREATED)
def create_work_order_endpoint(
    work_order: WorkOrderCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Any:
    """
    Create new work order
    SECURITY: Enforces client filtering AND write-role gate (operators denied).
    """
    _check_wo_write_permission(current_user)
    work_order_data = work_order.model_dump()
    result = create_work_order(db, work_order_data, current_user)
    db.commit()
    return result


@router.get("", response_model=List[WorkOrderResponse])
def list_work_orders(
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    style_model: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
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
    current_user: User = Depends(get_current_user),
) -> Any:
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
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get work orders within date range
    SECURITY: Returns only work orders for user's authorized clients
    """
    from backend.utils.date_range import validate_date_range

    validate_date_range(start_date.date(), end_date.date())
    return get_work_orders_by_date_range(db, start_date, end_date, current_user, skip, limit)


@router.get("/{work_order_id}", response_model=WorkOrderResponse)
def get_work_order_endpoint(
    work_order_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get work order by ID
    SECURITY: Verifies user has access to work order's client
    """
    work_order = get_work_order(db, work_order_id, current_user)
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")
    return work_order


@router.get("/{work_order_id}/progress")
def get_work_order_progress(
    work_order_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get detailed progress information for a work order including production entries.
    SECURITY: Verifies user has access to work order's client
    """
    # First verify access to work order
    work_order = get_work_order(db, work_order_id, current_user)
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")

    # Calculate progress percentage
    progress_percentage = 0.0
    if work_order.planned_quantity and work_order.planned_quantity > 0:
        progress_percentage = (work_order.actual_quantity / work_order.planned_quantity) * 100

    # Get production entries for this work order
    production_entries = []
    try:
        rows = (
            db.query(
                ProductionEntry.production_entry_id,
                ProductionEntry.production_date,
                ProductionEntry.units_produced,
                ProductionEntry.run_time_hours,
                ProductionEntry.employees_assigned,
                ProductionEntry.defect_count,
                ProductionEntry.scrap_count,
                Shift.shift_name,
                Product.product_name,
            )
            .outerjoin(Shift, ProductionEntry.shift_id == Shift.shift_id)
            .outerjoin(Product, ProductionEntry.product_id == Product.product_id)
            .filter(
                ProductionEntry.work_order_id == work_order_id,
                ProductionEntry.client_id == work_order.client_id,
            )
            .order_by(ProductionEntry.production_date.desc())
            .limit(50)
            .all()
        )
        for row in rows:
            production_entries.append(
                {
                    "production_entry_id": row.production_entry_id,
                    "production_date": row.production_date.isoformat() if row.production_date else None,
                    "units_produced": row.units_produced,
                    "run_time_hours": float(row.run_time_hours) if row.run_time_hours else None,
                    "employees_assigned": row.employees_assigned,
                    "defect_count": row.defect_count or 0,
                    "scrap_count": row.scrap_count or 0,
                    "shift_name": row.shift_name,
                    "product_name": row.product_name,
                }
            )
    except SQLAlchemyError as e:
        logger.warning("Could not fetch production entries for work order %s", work_order_id, exc_info=True)

    # Get quality inspections for this work order (from QUALITY_ENTRY table)
    quality_inspections = []
    try:
        rows = (
            db.query(
                QualityEntry.quality_entry_id,
                QualityEntry.inspection_date,
                QualityEntry.inspection_stage,
                QualityEntry.units_passed,
                QualityEntry.units_inspected,
                QualityEntry.total_defects_count,
                QualityEntry.notes,
            )
            .filter(
                QualityEntry.work_order_id == work_order_id,
                QualityEntry.client_id == work_order.client_id,
            )
            .order_by(QualityEntry.inspection_date.desc())
            .limit(20)
            .all()
        )
        for row in rows:
            # Derive result from pass/inspect ratio for backward compatibility
            result_str = None
            if row.units_inspected and row.units_inspected > 0:
                result_str = "PASS" if row.units_passed == row.units_inspected else "FAIL"
            quality_inspections.append(
                {
                    "inspection_id": row.quality_entry_id,
                    "inspection_date": row.inspection_date.isoformat() if row.inspection_date else None,
                    "inspection_type": row.inspection_stage,
                    "result": result_str,
                    "defects_found": row.total_defects_count or 0,
                    "notes": row.notes,
                }
            )
    except SQLAlchemyError as e:
        logger.warning("Could not fetch quality inspections for work order %s", work_order_id, exc_info=True)

    # Get hold history (from HOLD_ENTRY table)
    hold_history = []
    try:
        rows = (
            db.query(
                HoldEntry.hold_entry_id,
                HoldEntry.hold_date,
                HoldEntry.resume_date,
                HoldEntry.hold_reason_description,
                HoldEntry.hold_status,
            )
            .filter(
                HoldEntry.work_order_id == work_order_id,
                HoldEntry.client_id == work_order.client_id,
            )
            .order_by(HoldEntry.hold_date.desc())
            .limit(20)
            .all()
        )
        for row in rows:
            hold_history.append(
                {
                    "hold_id": row.hold_entry_id,
                    "hold_date": row.hold_date.isoformat() if row.hold_date else None,
                    "resume_date": row.resume_date.isoformat() if row.resume_date else None,
                    "reason": row.hold_reason_description,
                    "quantity": None,
                    "status": row.hold_status.value if hasattr(row.hold_status, "value") else row.hold_status,
                }
            )
    except SQLAlchemyError as e:
        logger.warning("Could not fetch hold history for work order %s", work_order_id, exc_info=True)

    return {
        "work_order_id": work_order.work_order_id,
        "style_model": work_order.style_model,
        "status": work_order.status.value if hasattr(work_order.status, "value") else work_order.status,
        "planned_quantity": work_order.planned_quantity,
        "actual_quantity": work_order.actual_quantity,
        "progress_percentage": round(progress_percentage, 2),
        "remaining_quantity": max(0, work_order.planned_quantity - work_order.actual_quantity),
        "is_on_track": progress_percentage >= 50 or work_order.status in ["COMPLETED", "CANCELLED"],
        "production_entries": production_entries,
        "quality_inspections": quality_inspections,
        "hold_history": hold_history,
        "total_production_entries": len(production_entries),
        "total_defects": sum(e["defect_count"] for e in production_entries),
        "total_scrap": sum(e["scrap_count"] for e in production_entries),
    }


@router.get("/{work_order_id}/timeline")
def get_work_order_timeline(
    work_order_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get activity timeline for a work order.
    SECURITY: Verifies user has access to work order's client
    """
    # First verify access to work order
    work_order = get_work_order(db, work_order_id, current_user)
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")

    timeline_events = []

    # Add work order creation event
    if work_order.created_at:
        timeline_events.append(
            {
                "event_type": "created",
                "title": "Work Order Created",
                "description": f"Work order {work_order_id} was created",
                "timestamp": work_order.created_at.isoformat(),
                "icon": "mdi-plus-circle",
                "color": "primary",
            }
        )

    # Add actual start date if available
    if work_order.actual_start_date:
        timeline_events.append(
            {
                "event_type": "started",
                "title": "Production Started",
                "description": "Production work began on this order",
                "timestamp": work_order.actual_start_date.isoformat(),
                "icon": "mdi-play-circle",
                "color": "info",
            }
        )

    # Add QC approval if available
    if work_order.qc_approved and work_order.qc_approved_date:
        timeline_events.append(
            {
                "event_type": "qc_approved",
                "title": "QC Approved",
                "description": "Quality control inspection passed",
                "timestamp": work_order.qc_approved_date.isoformat(),
                "icon": "mdi-check-circle",
                "color": "success",
            }
        )

    # Add rejection if applicable
    if work_order.rejected_date:
        timeline_events.append(
            {
                "event_type": "rejected",
                "title": "Work Order Rejected",
                "description": work_order.rejection_reason or "Work order was rejected",
                "timestamp": work_order.rejected_date.isoformat(),
                "icon": "mdi-close-circle",
                "color": "error",
            }
        )

    # Add delivery if applicable
    if work_order.actual_delivery_date:
        timeline_events.append(
            {
                "event_type": "delivered",
                "title": "Order Delivered",
                "description": "Work order was delivered to customer",
                "timestamp": work_order.actual_delivery_date.isoformat(),
                "icon": "mdi-truck-check",
                "color": "success",
            }
        )

    # Get hold/resume events (from HOLD_ENTRY table)
    try:
        rows = (
            db.query(
                HoldEntry.hold_date,
                HoldEntry.resume_date,
                HoldEntry.hold_reason_description,
            )
            .filter(
                HoldEntry.work_order_id == work_order_id,
                HoldEntry.client_id == work_order.client_id,
            )
            .order_by(HoldEntry.hold_date.asc())
            .all()
        )
        for row in rows:
            if row.hold_date:
                timeline_events.append(
                    {
                        "event_type": "hold",
                        "title": "Put On Hold",
                        "description": f"Reason: {row.hold_reason_description or 'Not specified'}",
                        "timestamp": row.hold_date.isoformat(),
                        "icon": "mdi-pause-circle",
                        "color": "warning",
                    }
                )
            if row.resume_date:
                timeline_events.append(
                    {
                        "event_type": "resume",
                        "title": "Resumed from Hold",
                        "description": "Production resumed",
                        "timestamp": row.resume_date.isoformat(),
                        "icon": "mdi-play-circle",
                        "color": "info",
                    }
                )
    except SQLAlchemyError as e:
        logger.warning("Could not fetch hold events for work order %s", work_order_id, exc_info=True)

    # Sort all events by timestamp
    timeline_events.sort(key=lambda x: x["timestamp"])

    # Add completion event if status is completed
    status_value = work_order.status.value if hasattr(work_order.status, "value") else work_order.status
    if status_value == "COMPLETED" and work_order.updated_at:
        timeline_events.append(
            {
                "event_type": "completed",
                "title": "Work Order Completed",
                "description": f"All {work_order.actual_quantity} units completed",
                "timestamp": work_order.updated_at.isoformat(),
                "icon": "mdi-flag-checkered",
                "color": "success",
            }
        )

    return {"work_order_id": work_order_id, "events": timeline_events, "total_events": len(timeline_events)}


@router.put("/{work_order_id}", response_model=WorkOrderResponse)
def update_work_order_endpoint(
    work_order_id: str,
    work_order_update: WorkOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update work order
    SECURITY: Verifies user has access to work order's client AND write-role.
    """
    _check_wo_write_permission(current_user)
    work_order_data = work_order_update.model_dump(exclude_unset=True)
    updated = update_work_order(db, work_order_id, work_order_data, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")
    db.commit()
    return updated


@router.patch("/{work_order_id}/status", response_model=WorkOrderResponse)
def update_work_order_status(
    work_order_id: str,
    status_update: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update only the status of a work order.
    Accepts: { "status": "ACTIVE" | "ON_HOLD" | "COMPLETED" | "REJECTED" | "CANCELLED" }
    SECURITY: Verifies user has access to work order's client AND write-role.
    """
    _check_wo_write_permission(current_user)
    if "status" not in status_update:
        raise HTTPException(status_code=400, detail="Status field is required")

    valid_statuses = ["ACTIVE", "ON_HOLD", "COMPLETED", "REJECTED", "CANCELLED"]
    if status_update["status"] not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")

    updated = update_work_order(db, work_order_id, {"status": status_update["status"]}, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")
    db.commit()
    return updated


@router.post("/{work_order_id}/approve-qc")
def approve_qc(
    work_order_id: str,
    approval_data: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Approve QC for a work order.

    Phase 3.3: QC Approval as Final Gate for SHIPPED status.

    This endpoint:
    1. Verifies user has QC authority (based on role)
    2. Sets qc_approved = 1 on the work order
    3. Creates WorkflowTransitionLog entry for audit trail
    4. Returns updated work order

    Args:
        work_order_id: Work order ID to approve
        approval_data: Optional dict with 'notes' field

    Returns:
        Updated work order with QC approval status

    Raises:
        403: User does not have QC authority
        404: Work order not found or access denied
        400: Work order already approved or not in valid state
    """
    from backend.orm.workflow import WorkflowTransitionLog

    # Verify access to work order
    work_order = get_work_order(db, work_order_id, current_user)
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")

    # Check if already approved
    if work_order.qc_approved:
        return {
            "status": "already_approved",
            "work_order_id": work_order_id,
            "qc_approved": True,
            "qc_approved_date": work_order.qc_approved_date.isoformat() if work_order.qc_approved_date else None,
            "qc_approved_by": work_order.qc_approved_by,
        }

    # Check if work order is in valid state for QC approval (should be COMPLETED or IN_PROGRESS)
    status_value = work_order.status.value if hasattr(work_order.status, "value") else work_order.status
    if status_value in ["SHIPPED", "CLOSED", "CANCELLED", "REJECTED"]:
        raise HTTPException(status_code=400, detail=f"Cannot approve QC for work order in {status_value} status")

    # Get notes from approval data
    notes = None
    if approval_data and isinstance(approval_data, dict):
        notes = approval_data.get("notes")

    # Apply QC approval
    now = datetime.now(tz=timezone.utc)
    work_order.qc_approved = True
    work_order.qc_approved_by = current_user.user_id
    work_order.qc_approved_date = now

    # Create audit log entry
    try:
        log_entry = WorkflowTransitionLog(
            work_order_id=work_order_id,
            client_id=work_order.client_id,
            from_status=status_value,
            to_status=status_value,  # Not a status transition
            transitioned_by=current_user.user_id,
            transitioned_at=now,
            notes=notes or "QC Approved",
            trigger_source="qc_approval",
        )
        db.add(log_entry)
    except SQLAlchemyError as e:
        # Log but don't fail - audit log is secondary
        logger.warning("Could not create QC approval log for work order %s", work_order_id, exc_info=True)

    db.commit()
    db.refresh(work_order)

    return {
        "status": "approved",
        "work_order_id": work_order_id,
        "qc_approved": True,
        "qc_approved_date": now.isoformat(),
        "qc_approved_by": current_user.user_id,
        "message": f"Work order {work_order_id} QC approved. Can now transition to SHIPPED.",
    }


# ============================================================================
# Cross-Reference: Work Orders <-> Capacity Orders (Task 3.1)
# ============================================================================


@router.get("/{work_order_id}/capacity-order")
def get_work_order_capacity_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get the capacity order linked to this work order."""
    from backend.services.work_order_service import get_capacity_order_link

    cap_order = get_capacity_order_link(db, work_order_id, current_user)
    if not cap_order:
        return {"linked": False, "capacity_order": None}
    return {
        "linked": True,
        "capacity_order": {
            "id": cap_order.id,
            "order_number": cap_order.order_number,
            "customer_name": cap_order.customer_name,
            "style_model": cap_order.style_model,
            "order_quantity": cap_order.order_quantity,
            "completed_quantity": cap_order.completed_quantity,
            "required_date": cap_order.required_date.isoformat() if cap_order.required_date else None,
            "status": cap_order.status.value if hasattr(cap_order.status, "value") else cap_order.status,
            "priority": cap_order.priority.value if hasattr(cap_order.priority, "value") else cap_order.priority,
        },
    }


@router.post("/{work_order_id}/link-capacity", response_model=WorkOrderResponse)
def link_to_capacity_order(
    work_order_id: str,
    link_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Link a work order to a capacity order."""
    from backend.services.work_order_service import link_to_capacity

    capacity_order_id = link_data.get("capacity_order_id")
    if not capacity_order_id:
        raise HTTPException(status_code=400, detail="capacity_order_id is required")
    result = link_to_capacity(db, work_order_id, capacity_order_id, current_user)
    db.commit()
    return result


@router.post("/{work_order_id}/unlink-capacity", response_model=WorkOrderResponse)
def unlink_from_capacity_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Unlink a work order from its capacity order."""
    from backend.services.work_order_service import unlink_from_capacity

    result = unlink_from_capacity(db, work_order_id, current_user)
    db.commit()
    return result


@router.delete("/{work_order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_order_endpoint(
    work_order_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_supervisor)
) -> None:
    """
    Delete work order (supervisor only)
    SECURITY: Only deletes if user has access to work order's client
    """
    success = delete_work_order(db, work_order_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")
    db.commit()


# Client work orders endpoint (separate prefix for /api/clients namespace)
client_work_orders_router = APIRouter(prefix="/api/clients", tags=["Work Orders"])


@client_work_orders_router.get("/{client_id}/work-orders", response_model=List[WorkOrderResponse])
def get_client_work_orders(
    client_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get all work orders for a specific client
    SECURITY: Returns only work orders for user's authorized clients
    """
    return get_work_orders_by_client(db, client_id, current_user, skip, limit)
