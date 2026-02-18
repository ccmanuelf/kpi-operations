"""
KPI On-Time Delivery (OTD) Routes

OTD calculation, late order identification, and client-level OTD aggregation.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import Optional
from datetime import date, datetime, timedelta, timezone

from backend.utils.logging_utils import get_module_logger
from backend.database import get_db
from backend.calculations.otd import identify_late_orders
from backend.auth.jwt import get_current_user
from backend.schemas.user import User

logger = get_module_logger(__name__)

otd_router = APIRouter(prefix="/api/kpi", tags=["KPI Calculations"])


@otd_router.get("/otd")
def calculate_otd_kpi(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate On-Time Delivery KPI with client filtering

    OTD = (Orders Delivered On Time / Total Orders with Due Dates) x 100
    Uses required_date as the due date and actual_delivery_date for completion.
    Parameters are optional - defaults to last 30 days.
    """
    from backend.schemas.work_order import WorkOrder

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Build query with client filter - use required_date as the due date
    query = db.query(WorkOrder).filter(
        WorkOrder.required_date.isnot(None),
        WorkOrder.required_date >= datetime.combine(start_date, datetime.min.time()),
        WorkOrder.required_date <= datetime.combine(end_date, datetime.max.time()),
    )

    # Apply client filter
    if effective_client_id:
        query = query.filter(WorkOrder.client_id == effective_client_id)

    work_orders = query.all()

    # Calculate OTD metrics
    total_orders = len(work_orders)
    on_time_count = 0

    for wo in work_orders:
        # Get the due date (required_date)
        due_date = wo.required_date
        if hasattr(due_date, "date"):
            due_date = due_date.date()

        # Consider on-time if delivered by due date or still open before due date
        if wo.actual_delivery_date:
            delivery_date = wo.actual_delivery_date
            if hasattr(delivery_date, "date"):
                delivery_date = delivery_date.date()
            if delivery_date <= due_date:
                on_time_count += 1
        elif due_date >= date.today():
            # Still open and not past due
            on_time_count += 1

    otd_percentage = (on_time_count / total_orders * 100) if total_orders > 0 else 0

    return {
        "start_date": start_date,
        "end_date": end_date,
        "client_id": effective_client_id,
        "otd_percentage": round(otd_percentage, 2),
        "on_time_count": on_time_count,
        "total_orders": total_orders,
        "calculation_timestamp": datetime.now(tz=timezone.utc),
    }


@otd_router.get("/late-orders")
def get_late_orders(
    as_of_date: Optional[date] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Identify late orders.

    Returns work orders whose required_date has passed without delivery.
    Uses the specified as_of_date or today as the reference point.

    SECURITY: Requires authentication; client filtering applied in identify_late_orders.
    """
    return identify_late_orders(db, as_of_date or date.today())


@otd_router.get("/otd/by-client")
def get_otd_by_client(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get OTD metrics aggregated by client.

    Returns on-time delivery counts and percentages grouped by client
    for the specified date range.

    SECURITY: Requires authentication; non-admin users see only their assigned client.
    """
    from backend.schemas.work_order import WorkOrder
    from backend.schemas.client import Client

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Query work orders grouped by client
    query = (
        db.query(
            WorkOrder.client_id,
            Client.client_name,
            func.count(WorkOrder.work_order_id).label("total_deliveries"),
            func.sum(
                case(
                    (WorkOrder.actual_delivery_date <= WorkOrder.required_date, 1),
                    (
                        WorkOrder.actual_delivery_date.is_(None),
                        case((WorkOrder.required_date >= date.today(), 1), else_=0),
                    ),
                    else_=0,
                )
            ).label("on_time"),
        )
        .join(Client, WorkOrder.client_id == Client.client_id)
        .filter(
            WorkOrder.required_date.isnot(None),
            WorkOrder.required_date >= datetime.combine(start_date, datetime.min.time()),
            WorkOrder.required_date <= datetime.combine(end_date, datetime.max.time()),
        )
    )

    # Non-admin users only see their assigned client
    if current_user.role != "admin" and current_user.client_id_assigned:
        query = query.filter(WorkOrder.client_id == current_user.client_id_assigned)

    results = query.group_by(WorkOrder.client_id, Client.client_name).all()

    return [
        {
            "client_id": r.client_id,
            "client_name": r.client_name or f"Client {r.client_id}",
            "total_deliveries": r.total_deliveries or 0,
            "on_time": r.on_time or 0,
            "otd_percentage": round((r.on_time / r.total_deliveries * 100) if r.total_deliveries > 0 else 0, 1),
        }
        for r in results
    ]


@otd_router.get("/otd/late-deliveries")
def get_late_deliveries(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get recent late deliveries with details.

    Returns work orders delivered after their required_date, ordered by most recent,
    including delay duration in hours and style/model information.

    SECURITY: Requires authentication; non-admin users see only their assigned client.
    """
    from backend.schemas.work_order import WorkOrder
    from backend.schemas.client import Client

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Query for late deliveries (actual_delivery_date > required_date)
    query = (
        db.query(
            WorkOrder.work_order_id,
            WorkOrder.client_id,
            Client.client_name,
            WorkOrder.required_date,
            WorkOrder.actual_delivery_date,
            WorkOrder.style_model,
        )
        .join(Client, WorkOrder.client_id == Client.client_id)
        .filter(
            WorkOrder.required_date.isnot(None),
            WorkOrder.actual_delivery_date.isnot(None),
            WorkOrder.actual_delivery_date > WorkOrder.required_date,
            WorkOrder.actual_delivery_date >= datetime.combine(start_date, datetime.min.time()),
            WorkOrder.actual_delivery_date <= datetime.combine(end_date, datetime.max.time()),
        )
    )

    # Apply client filter
    if effective_client_id:
        query = query.filter(WorkOrder.client_id == effective_client_id)

    # Order by delivery date (most recent first) and limit
    results = query.order_by(WorkOrder.actual_delivery_date.desc()).limit(limit).all()

    late_deliveries = []
    for r in results:
        # Calculate delay in hours
        required = r.required_date
        actual = r.actual_delivery_date

        # Handle datetime vs date conversion
        if hasattr(required, "date"):
            required_dt = required
        else:
            required_dt = datetime.combine(required, datetime.min.time())

        if hasattr(actual, "date"):
            actual_dt = actual
        else:
            actual_dt = datetime.combine(actual, datetime.min.time())

        delay_hours = int((actual_dt - required_dt).total_seconds() / 3600)

        late_deliveries.append(
            {
                "delivery_date": str(actual.date() if hasattr(actual, "date") else actual),
                "work_order": r.work_order_id,
                "client": r.client_name or r.client_id,
                "delay_hours": delay_hours,
                "style_model": r.style_model,
            }
        )

    return late_deliveries
