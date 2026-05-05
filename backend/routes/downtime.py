"""
Downtime Tracking API Routes
All downtime CRUD and availability KPI endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any, List, Optional
from datetime import date, datetime, timezone

from backend.database import get_db
from backend.utils.logging_utils import get_module_logger, log_operation, log_error

logger = get_module_logger(__name__)
from backend.schemas.downtime import (
    DowntimeEventCreate,
    DowntimeEventUpdate,
    DowntimeEventResponse,
)
from backend.services.downtime_service import (
    create_event as create_downtime_event,
    get_event as get_downtime_event,
    list_events as get_downtime_events,
    update_event as update_downtime_event,
    delete_event as delete_downtime_event,
)
from backend.calculations.availability import calculate_availability
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.orm.user import User


router = APIRouter(prefix="/api/downtime", tags=["Downtime Tracking"])


@router.post("", response_model=DowntimeEventResponse, status_code=status.HTTP_201_CREATED)
def create_downtime(
    downtime: DowntimeEventCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Any:
    """Create downtime event"""
    try:
        result = create_downtime_event(db, downtime, current_user)
        log_operation(
            logger,
            "CREATE",
            "downtime",
            resource_id=str(result.downtime_entry_id),
            user_id=current_user.user_id,
            details={"reason": getattr(downtime, "downtime_reason", None)},
        )
        return result
    except Exception as e:
        log_error(logger, "CREATE", "downtime", e, user_id=current_user.user_id)
        raise


@router.get("", response_model=List[DowntimeEventResponse])
def list_downtime(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    downtime_reason: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """List downtime events with filters"""
    return get_downtime_events(
        db,
        current_user=current_user,
        skip=skip,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        client_id=client_id,
        work_order_id=work_order_id,
        downtime_reason=downtime_reason,
    )


@router.get("/{downtime_id}", response_model=DowntimeEventResponse)
def get_downtime(
    downtime_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Any:
    """Get downtime event by ID"""
    event = get_downtime_event(db, downtime_id, current_user)
    if not event:
        raise HTTPException(status_code=404, detail="Downtime event not found")
    return event


@router.put("/{downtime_id}", response_model=DowntimeEventResponse)
def update_downtime(
    downtime_id: str,
    downtime_update: DowntimeEventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Update downtime event"""
    try:
        updated = update_downtime_event(db, downtime_id, downtime_update, current_user)
        if not updated:
            raise HTTPException(status_code=404, detail="Downtime event not found")
        log_operation(logger, "UPDATE", "downtime", resource_id=str(downtime_id), user_id=current_user.user_id)
        return updated
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "UPDATE", "downtime", e, resource_id=str(downtime_id), user_id=current_user.user_id)
        raise


@router.delete("/{downtime_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_downtime(
    downtime_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_supervisor)
) -> None:
    """Delete downtime event (supervisor only)"""
    try:
        success = delete_downtime_event(db, downtime_id, current_user)
        if not success:
            raise HTTPException(status_code=404, detail="Downtime event not found")
        log_operation(logger, "DELETE", "downtime", resource_id=str(downtime_id), user_id=current_user.user_id)
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, "DELETE", "downtime", e, resource_id=str(downtime_id), user_id=current_user.user_id)
        raise


# Availability KPI endpoint (separate prefix for /api/kpi namespace)
availability_router = APIRouter(prefix="/api/kpi", tags=["Downtime Tracking"])


@availability_router.get("/availability")
def calculate_availability_kpi(
    work_order_id: Optional[str] = None,
    target_date: Optional[date] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    shift_id: Optional[str] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Calculate availability KPI.

    Previously took required (product_id: int, shift_id: int,
    production_date: date) and passed those positionally to
    calculate_availability(db, work_order_id: str, target_date: date,
    client_id: Optional[str]). Every dashboard load 422'd, and the
    return body used `availability_percentage` while the frontend reads
    `average_availability`. Reworked to:

    - All filters optional. If neither work_order_id nor a date is
      provided, defaults to today and aggregates over all downtime
      entries for the client window.
    - Returns both `availability_percentage` (typed numeric) and
      `average_availability` (dashboard alias) so existing consumers
      keep working.
    """
    from datetime import timedelta
    from sqlalchemy import func, cast as sa_cast, Date as SADate
    from decimal import Decimal as _Decimal
    from backend.orm.downtime_entry import DowntimeEntry

    # Effective client filter — admin pass-through, others scoped.
    effective_client_id = client_id
    if not effective_client_id and current_user.role != "admin" and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # If a specific work order + date were provided, delegate to the
    # per-work-order helper (which is what the original route name
    # implied).
    if work_order_id is not None and target_date is not None:
        availability, scheduled, downtime, events = calculate_availability(
            db, work_order_id, target_date, effective_client_id
        )
    else:
        # Aggregate path. Default to last 7 days when no window provided.
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=7)

        query = db.query(
            func.coalesce(func.sum(DowntimeEntry.downtime_duration_minutes), 0).label("dt_minutes"),
            func.count(DowntimeEntry.downtime_entry_id).label("event_count"),
        ).filter(
            sa_cast(DowntimeEntry.shift_date, SADate) >= start_date,
            sa_cast(DowntimeEntry.shift_date, SADate) <= end_date,
        )
        if effective_client_id:
            query = query.filter(DowntimeEntry.client_id == effective_client_id)
        row = query.first()

        days = max(1, (end_date - start_date).days + 1)
        scheduled = _Decimal("8.0") * _Decimal(days)
        dt_minutes = _Decimal(str(row.dt_minutes if row is not None else 0))
        downtime = dt_minutes / _Decimal("60")
        events = int(row.event_count if row is not None else 0)
        if scheduled > 0:
            availability = ((scheduled - downtime) / scheduled) * _Decimal("100")
        else:
            availability = _Decimal("0")

    return {
        "work_order_id": work_order_id,
        "shift_id": shift_id,
        "target_date": target_date.isoformat() if target_date else None,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "total_scheduled_hours": float(scheduled),
        "total_downtime_hours": float(downtime),
        "available_hours": float(scheduled - downtime),
        "availability_percentage": float(round(availability, 2)),
        "average_availability": float(round(availability, 2)),
        "downtime_events": events,
        "calculation_timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
