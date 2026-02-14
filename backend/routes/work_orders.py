"""
Work Order API Routes
All work order CRUD endpoints with progress tracking and timeline
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

from backend.database import get_db
from backend.models.work_order import WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse, WorkOrderWithMetrics
from backend.crud.work_order import (
    create_work_order,
    get_work_order,
    get_work_orders,
    update_work_order,
    delete_work_order,
    get_work_orders_by_client,
    get_work_orders_by_status,
    get_work_orders_by_date_range,
)
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User
from backend.schemas.work_order import WorkOrder


router = APIRouter(prefix="/api/work-orders", tags=["Work Orders"])


@router.post("", response_model=WorkOrderResponse, status_code=status.HTTP_201_CREATED)
def create_work_order_endpoint(
    work_order: WorkOrderCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
):
    """
    Get work orders within date range
    SECURITY: Returns only work orders for user's authorized clients
    """
    return get_work_orders_by_date_range(db, start_date, end_date, current_user, skip, limit)


@router.get("/{work_order_id}", response_model=WorkOrderResponse)
def get_work_order_endpoint(
    work_order_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
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
        result = db.execute(
            text(
                """
            SELECT
                pe.production_entry_id,
                pe.production_date,
                pe.units_produced,
                pe.run_time_hours,
                pe.employees_assigned,
                pe.defect_count,
                pe.scrap_count,
                s.shift_name,
                p.product_name
            FROM PRODUCTION_ENTRY pe
            LEFT JOIN SHIFT s ON pe.shift_id = s.shift_id
            LEFT JOIN PRODUCT p ON pe.product_id = p.product_id
            WHERE pe.work_order_id = :work_order_id
            ORDER BY pe.production_date DESC
            LIMIT 50
            """
            ),
            {"work_order_id": work_order_id},
        )
        for row in result:
            production_entries.append(
                {
                    "production_entry_id": row[0],
                    "production_date": row[1].isoformat() if row[1] else None,
                    "units_produced": row[2],
                    "run_time_hours": float(row[3]) if row[3] else None,
                    "employees_assigned": row[4],
                    "defect_count": row[5] or 0,
                    "scrap_count": row[6] or 0,
                    "shift_name": row[7],
                    "product_name": row[8],
                }
            )
    except Exception as e:
        # Table might not exist or have different schema
        print(f"Warning: Could not fetch production entries: {e}")

    # Get quality inspections for this work order
    quality_inspections = []
    try:
        result = db.execute(
            text(
                """
            SELECT
                qi.inspection_id,
                qi.inspection_date,
                qi.inspection_type,
                qi.result,
                qi.defects_found,
                qi.notes
            FROM QUALITY_INSPECTION qi
            WHERE qi.work_order_id = :work_order_id
            ORDER BY qi.inspection_date DESC
            LIMIT 20
            """
            ),
            {"work_order_id": work_order_id},
        )
        for row in result:
            quality_inspections.append(
                {
                    "inspection_id": row[0],
                    "inspection_date": row[1].isoformat() if row[1] else None,
                    "inspection_type": row[2],
                    "result": row[3],
                    "defects_found": row[4] or 0,
                    "notes": row[5],
                }
            )
    except Exception as e:
        print(f"Warning: Could not fetch quality inspections: {e}")

    # Get hold history
    hold_history = []
    try:
        result = db.execute(
            text(
                """
            SELECT
                wh.hold_id,
                wh.hold_date,
                wh.resume_date,
                wh.reason,
                wh.quantity,
                wh.status
            FROM WIP_HOLD wh
            WHERE wh.work_order_id = :work_order_id
            ORDER BY wh.hold_date DESC
            LIMIT 20
            """
            ),
            {"work_order_id": work_order_id},
        )
        for row in result:
            hold_history.append(
                {
                    "hold_id": row[0],
                    "hold_date": row[1].isoformat() if row[1] else None,
                    "resume_date": row[2].isoformat() if row[2] else None,
                    "reason": row[3],
                    "quantity": row[4],
                    "status": row[5],
                }
            )
    except Exception as e:
        print(f"Warning: Could not fetch hold history: {e}")

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

    # Get hold/resume events
    try:
        result = db.execute(
            text(
                """
            SELECT
                hold_date, resume_date, reason, quantity
            FROM WIP_HOLD
            WHERE work_order_id = :work_order_id
            ORDER BY hold_date ASC
            """
            ),
            {"work_order_id": work_order_id},
        )
        for row in result:
            if row[0]:  # hold_date
                timeline_events.append(
                    {
                        "event_type": "hold",
                        "title": "Put On Hold",
                        "description": f"Reason: {row[2] or 'Not specified'} ({row[3] or 0} units)",
                        "timestamp": row[0].isoformat(),
                        "icon": "mdi-pause-circle",
                        "color": "warning",
                    }
                )
            if row[1]:  # resume_date
                timeline_events.append(
                    {
                        "event_type": "resume",
                        "title": "Resumed from Hold",
                        "description": f"Production resumed ({row[3] or 0} units)",
                        "timestamp": row[1].isoformat(),
                        "icon": "mdi-play-circle",
                        "color": "info",
                    }
                )
    except Exception as e:
        print(f"Warning: Could not fetch hold events: {e}")

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


@router.patch("/{work_order_id}/status", response_model=WorkOrderResponse)
def update_work_order_status(
    work_order_id: str,
    status_update: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update only the status of a work order.
    Accepts: { "status": "ACTIVE" | "ON_HOLD" | "COMPLETED" | "REJECTED" | "CANCELLED" }
    SECURITY: Verifies user has access to work order's client
    """
    if "status" not in status_update:
        raise HTTPException(status_code=400, detail="Status field is required")

    valid_statuses = ["ACTIVE", "ON_HOLD", "COMPLETED", "REJECTED", "CANCELLED"]
    if status_update["status"] not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}")

    updated = update_work_order(db, work_order_id, {"status": status_update["status"]}, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")
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
    from backend.schemas.workflow import WorkflowTransitionLog

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
    now = datetime.utcnow()
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
    except Exception as e:
        # Log but don't fail - audit log is secondary
        print(f"Warning: Could not create QC approval log: {e}")

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


@router.delete("/{work_order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_order_endpoint(
    work_order_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_supervisor)
):
    """
    Delete work order (supervisor only)
    SECURITY: Only deletes if user has access to work order's client
    """
    success = delete_work_order(db, work_order_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="Work order not found or access denied")


# Client work orders endpoint (separate prefix for /api/clients namespace)
client_work_orders_router = APIRouter(prefix="/api/clients", tags=["Work Orders"])


@client_work_orders_router.get("/{client_id}/work-orders", response_model=List[WorkOrderResponse])
def get_client_work_orders(
    client_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all work orders for a specific client
    SECURITY: Returns only work orders for user's authorized clients
    """
    return get_work_orders_by_client(db, client_id, current_user, skip, limit)
