"""
WIP Hold Tracking API Routes
All holds CRUD and WIP aging KPI endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime, timedelta

from backend.database import get_db
from backend.models.hold import (
    WIPHoldCreate,
    WIPHoldUpdate,
    WIPHoldResponse,
    WIPAgingResponse
)
from backend.crud.hold import (
    create_wip_hold,
    get_wip_hold,
    get_wip_holds,
    update_wip_hold,
    delete_wip_hold
)
from backend.calculations.wip_aging import identify_chronic_holds
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User


router = APIRouter(
    prefix="/api/holds",
    tags=["WIP Holds"]
)


@router.post("", response_model=WIPHoldResponse, status_code=status.HTTP_201_CREATED)
def create_hold(
    hold: WIPHoldCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create WIP hold record"""
    return create_wip_hold(db, hold, current_user)


@router.get("", response_model=List[WIPHoldResponse])
def list_holds(
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    released: Optional[bool] = None,
    hold_reason_category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List WIP holds with filters - uses HOLD_ENTRY schema"""
    return get_wip_holds(
        db, current_user=current_user, skip=skip, limit=limit, start_date=start_date,
        end_date=end_date, client_id=client_id, work_order_id=work_order_id,
        released=released, hold_reason_category=hold_reason_category
    )


@router.get("/{hold_id}", response_model=WIPHoldResponse)
def get_hold(
    hold_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get WIP hold by ID"""
    hold = get_wip_hold(db, hold_id, current_user)
    if not hold:
        raise HTTPException(status_code=404, detail="WIP hold not found")
    return hold


@router.put("/{hold_id}", response_model=WIPHoldResponse)
def update_hold(
    hold_id: int,
    hold_update: WIPHoldUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update WIP hold record"""
    updated = update_wip_hold(db, hold_id, hold_update, current_user)
    if not updated:
        raise HTTPException(status_code=404, detail="WIP hold not found")
    return updated


@router.delete("/{hold_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hold(
    hold_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor)
):
    """Delete WIP hold (supervisor only)"""
    success = delete_wip_hold(db, hold_id, current_user)
    if not success:
        raise HTTPException(status_code=404, detail="WIP hold not found")


# WIP Aging KPI endpoints (separate prefix for /api/kpi namespace)
wip_aging_router = APIRouter(
    prefix="/api/kpi",
    tags=["WIP Holds"]
)


@wip_aging_router.get("/wip-aging", response_model=WIPAgingResponse)
def calculate_wip_aging_kpi(
    product_id: Optional[int] = None,
    as_of_date: Optional[date] = None,
    client_id: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate WIP aging analysis with client filtering"""
    from backend.schemas.hold_entry import HoldEntry, HoldStatus

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Build query for hold entries - only active holds
    query = db.query(HoldEntry).filter(HoldEntry.hold_status == HoldStatus.ON_HOLD)

    # Apply client filter
    if effective_client_id:
        query = query.filter(HoldEntry.client_id == effective_client_id)

    # Apply date filters if provided (on hold_date)
    if start_date:
        query = query.filter(HoldEntry.hold_date >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(HoldEntry.hold_date <= datetime.combine(end_date, datetime.max.time()))

    # Get all active holds
    holds = query.all()

    # Calculate aging metrics
    calculation_date = as_of_date or date.today()
    total_held = len(holds)
    total_age = 0
    aging_0_7 = 0
    aging_8_14 = 0
    aging_15_30 = 0
    aging_over_30 = 0

    for hold in holds:
        # Properly convert DateTime to date for comparison
        hold_date = hold.hold_date
        if hold_date is None:
            continue

        # Handle both datetime and date types, and string from SQLite
        if hasattr(hold_date, 'date'):
            hold_date = hold_date.date()
        elif isinstance(hold_date, str):
            # Parse date string from SQLite
            hold_date = datetime.strptime(hold_date.split()[0], '%Y-%m-%d').date()

        age_days = (calculation_date - hold_date).days
        total_age += age_days

        if age_days <= 7:
            aging_0_7 += 1
        elif age_days <= 14:
            aging_8_14 += 1
        elif age_days <= 30:
            aging_15_30 += 1
        else:
            aging_over_30 += 1

    avg_aging = total_age / total_held if total_held > 0 else 0

    return WIPAgingResponse(
        total_held_quantity=total_held,
        average_aging_days=round(avg_aging, 1),
        aging_0_7_days=aging_0_7,
        aging_8_14_days=aging_8_14,
        aging_15_30_days=aging_15_30,
        aging_over_30_days=aging_over_30,
        total_hold_events=total_held,
        calculation_timestamp=datetime.utcnow()
    )


@wip_aging_router.get("/wip-aging/top")
def get_top_aging_items(
    limit: int = 10,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get top aging WIP items - for WIP Aging view table"""
    from backend.schemas.hold_entry import HoldEntry, HoldStatus
    from backend.schemas.work_order import WorkOrder

    query = db.query(
        HoldEntry.work_order_id,
        WorkOrder.style_model,
        HoldEntry.hold_date,
        func.julianday('now') - func.julianday(HoldEntry.hold_date)
    ).outerjoin(
        WorkOrder, HoldEntry.work_order_id == WorkOrder.work_order_id
    ).filter(
        HoldEntry.hold_status == HoldStatus.ON_HOLD
    )

    # Apply client filter
    if client_id:
        query = query.filter(HoldEntry.client_id == client_id)
    elif current_user.role != 'admin' and current_user.client_id_assigned:
        query = query.filter(HoldEntry.client_id == current_user.client_id_assigned)

    results = query.order_by(
        (func.julianday('now') - func.julianday(HoldEntry.hold_date)).desc()
    ).limit(limit).all()

    return [
        {
            "work_order": r[0],
            "product": r[1] or "N/A",
            "age": int(r[3]) if r[3] else 0,
            "quantity": 1  # Placeholder - HOLD_ENTRY doesn't track quantity
        }
        for r in results
    ]


@wip_aging_router.get("/wip-aging/trend")
def get_wip_aging_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get WIP aging trend data - for WIP Aging view chart"""
    from backend.schemas.hold_entry import HoldEntry, HoldStatus

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    # Get daily average aging for the date range
    # We calculate for each day how old the active holds were on that day
    trend_data = []
    current_date = start_date

    while current_date <= end_date:
        # Query holds that were active on this date
        query = db.query(
            func.avg(func.julianday(current_date) - func.julianday(HoldEntry.hold_date))
        ).filter(
            HoldEntry.hold_date <= current_date,
            (HoldEntry.resume_date.is_(None)) | (HoldEntry.resume_date > current_date)
        )

        # Apply client filter
        if client_id:
            query = query.filter(HoldEntry.client_id == client_id)
        elif current_user.role != 'admin' and current_user.client_id_assigned:
            query = query.filter(HoldEntry.client_id == current_user.client_id_assigned)

        result = query.scalar()
        avg_age = float(result) if result else 0

        trend_data.append({
            "date": current_date.isoformat(),
            "value": round(avg_age, 1)
        })

        current_date += timedelta(days=1)

    return trend_data


@wip_aging_router.get("/chronic-holds")
def get_chronic_holds(
    threshold_days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Identify chronic WIP holds"""
    return identify_chronic_holds(db, threshold_days)
