"""
KPI Calculation and Dashboard API Routes
All KPI calculation, dashboard, trend, and threshold endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import Optional
from datetime import date, datetime, timedelta
import uuid

from backend.database import get_db
from backend.models.production import KPICalculationResponse
from backend.crud.production import get_production_entry, get_daily_summary
from backend.calculations.efficiency import calculate_efficiency
from backend.calculations.performance import calculate_performance, calculate_quality_rate
from backend.calculations.otd import identify_late_orders
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.schemas.product import Product


router = APIRouter(
    prefix="/api/kpi",
    tags=["KPI Calculations"]
)

# Separate router for thresholds (different prefix)
thresholds_router = APIRouter(
    prefix="/api/kpi-thresholds",
    tags=["KPI Thresholds"]
)


# ============================================================================
# KPI THRESHOLDS ROUTES
# ============================================================================

@thresholds_router.get("")
def get_kpi_thresholds(
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get KPI thresholds for a specific client or global defaults.
    If client_id is provided, returns client-specific thresholds merged with global defaults.
    If client_id is NULL/not provided, returns only global defaults.
    """
    from backend.schemas.kpi_threshold import KPIThreshold
    from backend.schemas.client import Client

    # Get global defaults
    global_thresholds = db.query(KPIThreshold).filter(
        KPIThreshold.client_id.is_(None)
    ).all()

    # Build response with global defaults
    result = {
        "client_id": client_id,
        "client_name": None,
        "thresholds": {}
    }

    # Add global defaults first
    for t in global_thresholds:
        result["thresholds"][t.kpi_key] = {
            "threshold_id": t.threshold_id,
            "kpi_key": t.kpi_key,
            "target_value": t.target_value,
            "warning_threshold": t.warning_threshold,
            "critical_threshold": t.critical_threshold,
            "unit": t.unit,
            "higher_is_better": t.higher_is_better,
            "is_global": True
        }

    # If client_id provided, override with client-specific values
    if client_id:
        client = db.query(Client).filter(Client.client_id == client_id).first()
        if client:
            result["client_name"] = client.client_name

        client_thresholds = db.query(KPIThreshold).filter(
            KPIThreshold.client_id == client_id
        ).all()

        for t in client_thresholds:
            result["thresholds"][t.kpi_key] = {
                "threshold_id": t.threshold_id,
                "kpi_key": t.kpi_key,
                "target_value": t.target_value,
                "warning_threshold": t.warning_threshold,
                "critical_threshold": t.critical_threshold,
                "unit": t.unit,
                "higher_is_better": t.higher_is_better,
                "is_global": False
            }

    return result


@thresholds_router.put("")
def update_kpi_thresholds(
    thresholds_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update KPI thresholds for a client or global.
    Expects: { "client_id": "xxx" or null, "thresholds": { "efficiency": { "target_value": 85 }, ... } }
    """
    if current_user.role not in ['admin', 'poweruser']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or supervisor access required"
        )

    from backend.schemas.kpi_threshold import KPIThreshold

    client_id = thresholds_data.get("client_id")
    thresholds = thresholds_data.get("thresholds", {})

    updated = []
    for kpi_key, values in thresholds.items():
        # Check if threshold exists
        existing = db.query(KPIThreshold).filter(
            KPIThreshold.client_id == client_id if client_id else KPIThreshold.client_id.is_(None),
            KPIThreshold.kpi_key == kpi_key
        ).first()

        if existing:
            # Update existing
            if "target_value" in values:
                existing.target_value = values["target_value"]
            if "warning_threshold" in values:
                existing.warning_threshold = values["warning_threshold"]
            if "critical_threshold" in values:
                existing.critical_threshold = values["critical_threshold"]
            if "unit" in values:
                existing.unit = values["unit"]
            if "higher_is_better" in values:
                existing.higher_is_better = values["higher_is_better"]
            existing.updated_at = datetime.utcnow()
            updated.append(kpi_key)
        else:
            # Create new client-specific threshold
            new_threshold = KPIThreshold(
                threshold_id=str(uuid.uuid4()),
                client_id=client_id,
                kpi_key=kpi_key,
                target_value=values.get("target_value", 0),
                warning_threshold=values.get("warning_threshold"),
                critical_threshold=values.get("critical_threshold"),
                unit=values.get("unit", "%"),
                higher_is_better=values.get("higher_is_better", "Y"),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_threshold)
            updated.append(kpi_key)

    db.commit()

    return {
        "message": f"Updated {len(updated)} thresholds",
        "client_id": client_id,
        "updated_kpis": updated
    }


@thresholds_router.delete("/{client_id}/{kpi_key}")
def delete_client_threshold(
    client_id: str,
    kpi_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a client-specific threshold (reverts to global default).
    Cannot delete global thresholds.
    """
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    from backend.schemas.kpi_threshold import KPIThreshold

    threshold = db.query(KPIThreshold).filter(
        KPIThreshold.client_id == client_id,
        KPIThreshold.kpi_key == kpi_key
    ).first()

    if not threshold:
        raise HTTPException(status_code=404, detail="Client threshold not found")

    db.delete(threshold)
    db.commit()

    return {"message": f"Threshold {kpi_key} deleted for client {client_id}, reverted to global default"}


# ============================================================================
# KPI CALCULATION ROUTES
# ============================================================================

@router.get("/calculate/{entry_id}", response_model=KPICalculationResponse)
def calculate_kpis(
    entry_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Calculate KPIs for a production entry"""
    entry = get_production_entry(db, entry_id, current_user)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Production entry {entry_id} not found"
        )

    product = db.query(Product).filter(Product.product_id == entry.product_id).first()

    efficiency, ideal_time, was_inferred = calculate_efficiency(db, entry, product)
    performance, _, _ = calculate_performance(db, entry, product)
    quality = calculate_quality_rate(entry)

    return KPICalculationResponse(
        entry_id=entry_id,
        efficiency_percentage=efficiency,
        performance_percentage=performance,
        quality_rate=quality,
        ideal_cycle_time_used=ideal_time,
        was_inferred=was_inferred,
        calculation_timestamp=datetime.utcnow()
    )


@router.get("/dashboard")
def get_kpi_dashboard(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get KPI dashboard data"""
    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    return get_daily_summary(db, current_user, start_date, end_date, client_id=client_id)


@router.get("/efficiency/by-shift")
def get_efficiency_by_shift(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get efficiency aggregated by shift"""
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.shift import Shift

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    query = db.query(
        ProductionEntry.shift_id,
        Shift.shift_name,
        func.sum(ProductionEntry.units_produced).label('actual_output'),
        func.avg(ProductionEntry.efficiency_percentage).label('efficiency'),
        func.count(ProductionEntry.production_entry_id).label('entry_count')
    ).join(
        Shift, ProductionEntry.shift_id == Shift.shift_id
    ).filter(
        ProductionEntry.shift_date >= start_date,
        ProductionEntry.shift_date <= end_date
    )

    if client_id:
        query = query.filter(ProductionEntry.client_id == client_id)

    results = query.group_by(
        ProductionEntry.shift_id,
        Shift.shift_name
    ).all()

    return [
        {
            "shift_id": r.shift_id,
            "shift_name": r.shift_name or f"Shift {r.shift_id}",
            "actual_output": r.actual_output or 0,
            "expected_output": int((r.actual_output or 0) / ((r.efficiency or 100) / 100)) if r.efficiency else 0,
            "efficiency": float(r.efficiency) if r.efficiency else 0
        }
        for r in results
    ]


@router.get("/efficiency/by-product")
def get_efficiency_by_product(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get top products by efficiency"""
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.product import Product

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    query = db.query(
        ProductionEntry.product_id,
        Product.product_name,
        func.sum(ProductionEntry.units_produced).label('actual_output'),
        func.avg(ProductionEntry.efficiency_percentage).label('efficiency'),
        func.count(ProductionEntry.production_entry_id).label('entry_count')
    ).join(
        Product, ProductionEntry.product_id == Product.product_id
    ).filter(
        ProductionEntry.shift_date >= start_date,
        ProductionEntry.shift_date <= end_date
    )

    if client_id:
        query = query.filter(ProductionEntry.client_id == client_id)

    results = query.group_by(
        ProductionEntry.product_id,
        Product.product_name
    ).order_by(
        func.avg(ProductionEntry.efficiency_percentage).desc()
    ).limit(limit).all()

    return [
        {
            "product_id": r.product_id,
            "product_name": r.product_name or f"Product {r.product_id}",
            "actual_output": r.actual_output or 0,
            "efficiency": float(r.efficiency) if r.efficiency else 0
        }
        for r in results
    ]


# ============================================================================
# OTD (On-Time Delivery) KPI ROUTES
# ============================================================================

@router.get("/otd")
def calculate_otd_kpi(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Build query with client filter - use required_date as the due date
    query = db.query(WorkOrder).filter(
        WorkOrder.required_date.isnot(None),
        WorkOrder.required_date >= datetime.combine(start_date, datetime.min.time()),
        WorkOrder.required_date <= datetime.combine(end_date, datetime.max.time())
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
        if hasattr(due_date, 'date'):
            due_date = due_date.date()

        # Consider on-time if delivered by due date or still open before due date
        if wo.actual_delivery_date:
            delivery_date = wo.actual_delivery_date
            if hasattr(delivery_date, 'date'):
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
        "calculation_timestamp": datetime.utcnow()
    }


@router.get("/late-orders")
def get_late_orders(
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Identify late orders"""
    return identify_late_orders(db, as_of_date or date.today())


@router.get("/otd/by-client")
def get_otd_by_client(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get OTD metrics aggregated by client"""
    from backend.schemas.work_order import WorkOrder
    from backend.schemas.client import Client

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Query work orders grouped by client
    query = db.query(
        WorkOrder.client_id,
        Client.client_name,
        func.count(WorkOrder.work_order_id).label('total_deliveries'),
        func.sum(
            case(
                (WorkOrder.actual_delivery_date <= WorkOrder.required_date, 1),
                (WorkOrder.actual_delivery_date.is_(None),
                 case((WorkOrder.required_date >= date.today(), 1), else_=0)),
                else_=0
            )
        ).label('on_time')
    ).join(
        Client, WorkOrder.client_id == Client.client_id
    ).filter(
        WorkOrder.required_date.isnot(None),
        WorkOrder.required_date >= datetime.combine(start_date, datetime.min.time()),
        WorkOrder.required_date <= datetime.combine(end_date, datetime.max.time())
    )

    # Non-admin users only see their assigned client
    if current_user.role != 'admin' and current_user.client_id_assigned:
        query = query.filter(WorkOrder.client_id == current_user.client_id_assigned)

    results = query.group_by(
        WorkOrder.client_id,
        Client.client_name
    ).all()

    return [
        {
            "client_id": r.client_id,
            "client_name": r.client_name or f"Client {r.client_id}",
            "total_deliveries": r.total_deliveries or 0,
            "on_time": r.on_time or 0,
            "otd_percentage": round((r.on_time / r.total_deliveries * 100) if r.total_deliveries > 0 else 0, 1)
        }
        for r in results
    ]


@router.get("/otd/late-deliveries")
def get_late_deliveries(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get recent late deliveries with details"""
    from backend.schemas.work_order import WorkOrder
    from backend.schemas.client import Client

    # Default to last 30 days if dates not provided
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Determine effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Query for late deliveries (actual_delivery_date > required_date)
    query = db.query(
        WorkOrder.work_order_id,
        WorkOrder.client_id,
        Client.client_name,
        WorkOrder.required_date,
        WorkOrder.actual_delivery_date,
        WorkOrder.style_model
    ).join(
        Client, WorkOrder.client_id == Client.client_id
    ).filter(
        WorkOrder.required_date.isnot(None),
        WorkOrder.actual_delivery_date.isnot(None),
        WorkOrder.actual_delivery_date > WorkOrder.required_date,
        WorkOrder.actual_delivery_date >= datetime.combine(start_date, datetime.min.time()),
        WorkOrder.actual_delivery_date <= datetime.combine(end_date, datetime.max.time())
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
        if hasattr(required, 'date'):
            required_dt = required
        else:
            required_dt = datetime.combine(required, datetime.min.time())

        if hasattr(actual, 'date'):
            actual_dt = actual
        else:
            actual_dt = datetime.combine(actual, datetime.min.time())

        delay_hours = int((actual_dt - required_dt).total_seconds() / 3600)

        late_deliveries.append({
            "delivery_date": str(actual.date() if hasattr(actual, 'date') else actual),
            "work_order": r.work_order_id,
            "client": r.client_name or r.client_id,
            "delay_hours": delay_hours,
            "style_model": r.style_model
        })

    return late_deliveries


# ============================================================================
# KPI TREND ENDPOINTS
# ============================================================================

@router.get("/efficiency/trend")
def get_efficiency_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily efficiency trend data"""
    from backend.schemas.production_entry import ProductionEntry

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = db.query(
        func.date(ProductionEntry.shift_date).label('date'),
        func.avg(ProductionEntry.efficiency_percentage).label('value')
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(ProductionEntry.client_id == effective_client_id)

    results = query.group_by(func.date(ProductionEntry.shift_date)).order_by(func.date(ProductionEntry.shift_date)).all()

    return [{"date": str(r.date), "value": round(float(r.value), 2) if r.value else 0} for r in results]


@router.get("/performance/trend")
def get_performance_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily performance trend data"""
    from backend.schemas.production_entry import ProductionEntry

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = db.query(
        func.date(ProductionEntry.shift_date).label('date'),
        func.avg(ProductionEntry.performance_percentage).label('value')
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(ProductionEntry.client_id == effective_client_id)

    results = query.group_by(func.date(ProductionEntry.shift_date)).order_by(func.date(ProductionEntry.shift_date)).all()

    return [{"date": str(r.date), "value": round(float(r.value), 2) if r.value else 0} for r in results]


@router.get("/performance/by-shift")
def get_performance_by_shift(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get performance aggregated by shift"""
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.shift import Shift

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = db.query(
        ProductionEntry.shift_id,
        Shift.shift_name,
        func.sum(ProductionEntry.units_produced).label('units'),
        func.sum(ProductionEntry.run_time_hours).label('hours'),
        func.avg(ProductionEntry.performance_percentage).label('performance'),
        func.count(ProductionEntry.production_entry_id).label('entry_count')
    ).outerjoin(
        Shift, ProductionEntry.shift_id == Shift.shift_id
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(ProductionEntry.client_id == effective_client_id)

    results = query.group_by(
        ProductionEntry.shift_id,
        Shift.shift_name
    ).order_by(
        func.avg(ProductionEntry.performance_percentage).desc()
    ).all()

    return [
        {
            "shift_id": r.shift_id,
            "shift_name": r.shift_name or f"Shift {r.shift_id}",
            "units": int(r.units) if r.units else 0,
            "rate": round(float(r.units) / float(r.hours), 1) if r.hours and r.hours > 0 else 0,
            "performance": round(float(r.performance), 1) if r.performance else 0
        }
        for r in results
    ]


@router.get("/performance/by-product")
def get_performance_by_product(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get performance aggregated by product"""
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.product import Product

    if not start_date:
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = db.query(
        ProductionEntry.product_id,
        Product.product_name,
        func.sum(ProductionEntry.units_produced).label('units'),
        func.sum(ProductionEntry.run_time_hours).label('hours'),
        func.avg(ProductionEntry.performance_percentage).label('performance'),
        func.count(ProductionEntry.production_entry_id).label('entry_count')
    ).join(
        Product, ProductionEntry.product_id == Product.product_id
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(ProductionEntry.client_id == effective_client_id)

    results = query.group_by(
        ProductionEntry.product_id,
        Product.product_name
    ).order_by(
        func.avg(ProductionEntry.performance_percentage).desc()
    ).limit(limit).all()

    return [
        {
            "product_id": r.product_id,
            "product_name": r.product_name or f"Product {r.product_id}",
            "units": int(r.units) if r.units else 0,
            "rate": round(float(r.units) / float(r.hours), 1) if r.hours and r.hours > 0 else 0,
            "performance": round(float(r.performance), 1) if r.performance else 0
        }
        for r in results
    ]


@router.get("/quality/trend")
def get_quality_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily quality (FPY) trend data"""
    from backend.schemas.quality_entry import QualityEntry

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    query = db.query(
        func.date(QualityEntry.shift_date).label('date'),
        func.sum(QualityEntry.units_passed).label('passed'),
        func.sum(QualityEntry.units_inspected).label('inspected')
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(QualityEntry.client_id == effective_client_id)

    results = query.group_by(func.date(QualityEntry.shift_date)).order_by(func.date(QualityEntry.shift_date)).all()

    return [
        {
            "date": str(r.date),
            "value": round((r.passed / r.inspected) * 100, 2) if r.inspected and r.inspected > 0 else 0
        }
        for r in results
    ]


@router.get("/availability/trend")
def get_availability_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily availability trend data (calculated from downtime)"""
    from backend.schemas.downtime_entry import DowntimeEntry
    from backend.schemas.production_entry import ProductionEntry

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Get production days (scheduled time proxy)
    prod_query = db.query(
        func.date(ProductionEntry.shift_date).label('date'),
        func.count(ProductionEntry.production_entry_id).label('entries')
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )
    if effective_client_id:
        prod_query = prod_query.filter(ProductionEntry.client_id == effective_client_id)
    prod_results = {str(r.date): r.entries * 8 for r in prod_query.group_by(func.date(ProductionEntry.shift_date)).all()}

    # Get downtime by day
    dt_query = db.query(
        func.date(DowntimeEntry.shift_date).label('date'),
        func.sum(DowntimeEntry.downtime_duration_minutes).label('downtime_mins')
    ).filter(
        DowntimeEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        DowntimeEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )
    if effective_client_id:
        dt_query = dt_query.filter(DowntimeEntry.client_id == effective_client_id)
    dt_results = {str(r.date): float(r.downtime_mins) / 60 if r.downtime_mins else 0 for r in dt_query.group_by(func.date(DowntimeEntry.shift_date)).all()}

    # Calculate availability per day
    trend_data = []
    for day in sorted(prod_results.keys()):
        scheduled = prod_results.get(day, 8)
        downtime = dt_results.get(day, 0)
        availability = ((scheduled - downtime) / scheduled * 100) if scheduled > 0 else 100
        trend_data.append({"date": day, "value": round(max(0, min(100, availability)), 2)})

    return trend_data


@router.get("/oee/trend")
def get_oee_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily OEE trend data (Availability x Performance x Quality)"""
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.quality_entry import QualityEntry
    from backend.schemas.downtime_entry import DowntimeEntry

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Get performance by day
    perf_query = db.query(
        func.date(ProductionEntry.shift_date).label('date'),
        func.avg(ProductionEntry.performance_percentage).label('performance'),
        func.count(ProductionEntry.production_entry_id).label('entries')
    ).filter(
        ProductionEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        ProductionEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )
    if effective_client_id:
        perf_query = perf_query.filter(ProductionEntry.client_id == effective_client_id)
    perf_results = {str(r.date): {"performance": float(r.performance) if r.performance else 95, "entries": r.entries} for r in perf_query.group_by(func.date(ProductionEntry.shift_date)).all()}

    # Get quality by day
    qual_query = db.query(
        func.date(QualityEntry.shift_date).label('date'),
        func.sum(QualityEntry.units_passed).label('passed'),
        func.sum(QualityEntry.units_inspected).label('inspected')
    ).filter(
        QualityEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        QualityEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )
    if effective_client_id:
        qual_query = qual_query.filter(QualityEntry.client_id == effective_client_id)
    qual_results = {str(r.date): (r.passed / r.inspected * 100) if r.inspected and r.inspected > 0 else 97 for r in qual_query.group_by(func.date(QualityEntry.shift_date)).all()}

    # Get downtime by day
    dt_query = db.query(
        func.date(DowntimeEntry.shift_date).label('date'),
        func.sum(DowntimeEntry.downtime_duration_minutes).label('downtime_mins')
    ).filter(
        DowntimeEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        DowntimeEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )
    if effective_client_id:
        dt_query = dt_query.filter(DowntimeEntry.client_id == effective_client_id)
    dt_results = {str(r.date): float(r.downtime_mins) / 60 if r.downtime_mins else 0 for r in dt_query.group_by(func.date(DowntimeEntry.shift_date)).all()}

    # Calculate OEE per day
    trend_data = []
    for day in sorted(perf_results.keys()):
        scheduled = perf_results[day]["entries"] * 8
        downtime = dt_results.get(day, 0)
        availability = ((scheduled - downtime) / scheduled * 100) if scheduled > 0 else 90
        performance = perf_results[day]["performance"]
        quality = qual_results.get(day, 97)
        oee = (availability / 100) * (performance / 100) * (quality / 100) * 100
        trend_data.append({"date": day, "value": round(min(100, oee), 2)})

    return trend_data


@router.get("/on-time-delivery/trend")
def get_otd_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily On-Time Delivery trend data"""
    from backend.schemas.work_order import WorkOrder

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Query work orders grouped by required_date
    query = db.query(
        func.date(WorkOrder.required_date).label('date'),
        func.count(WorkOrder.work_order_id).label('total'),
        func.sum(
            case(
                (WorkOrder.actual_delivery_date <= WorkOrder.required_date, 1),
                else_=0
            )
        ).label('on_time')
    ).filter(
        WorkOrder.required_date.isnot(None),
        WorkOrder.required_date >= datetime.combine(start_date, datetime.min.time()),
        WorkOrder.required_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(WorkOrder.client_id == effective_client_id)

    results = query.group_by(func.date(WorkOrder.required_date)).order_by(func.date(WorkOrder.required_date)).all()

    return [{"date": str(r.date), "value": round((r.on_time / r.total * 100) if r.total > 0 else 0, 2)} for r in results]


@router.get("/absenteeism/trend")
def get_absenteeism_trend(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get daily absenteeism trend data"""
    from backend.schemas.attendance_entry import AttendanceEntry

    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Query attendance grouped by shift_date
    query = db.query(
        func.date(AttendanceEntry.shift_date).label('date'),
        func.sum(AttendanceEntry.scheduled_hours).label('scheduled'),
        func.sum(func.coalesce(AttendanceEntry.absence_hours, 0)).label('absent')
    ).filter(
        AttendanceEntry.shift_date >= datetime.combine(start_date, datetime.min.time()),
        AttendanceEntry.shift_date <= datetime.combine(end_date, datetime.max.time())
    )

    if effective_client_id:
        query = query.filter(AttendanceEntry.client_id == effective_client_id)

    results = query.group_by(func.date(AttendanceEntry.shift_date)).order_by(func.date(AttendanceEntry.shift_date)).all()

    return [{"date": str(r.date), "value": round((r.absent / r.scheduled * 100) if r.scheduled and r.scheduled > 0 else 0, 2)} for r in results]


# ============================================================================
# AGGREGATED DASHBOARD ENDPOINT
# ============================================================================

@router.get("/dashboard/aggregated")
def get_aggregated_dashboard(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get aggregated KPI dashboard data in a single API call.

    Combines multiple KPI endpoints into one response to reduce frontend API calls:
    - Efficiency metrics and trends
    - Performance metrics and trends
    - Quality metrics (FPY, RTY, PPM, DPMO)
    - Availability
    - Absenteeism
    - WIP aging summary
    - OTD (On-Time Delivery)

    This endpoint reduces 10+ API calls to a single request.
    """
    from backend.schemas.production_entry import ProductionEntry
    from backend.schemas.quality_entry import QualityEntry
    from backend.schemas.attendance_entry import AttendanceEntry
    from backend.schemas.downtime_entry import DowntimeEntry
    from backend.schemas.work_order import WorkOrder
    from backend.schemas.hold_entry import HoldEntry
    from backend.calculations.ppm import calculate_ppm
    from backend.calculations.dpmo import calculate_dpmo
    from backend.calculations.fpy_rty import calculate_fpy

    # Default dates
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Effective client filter
    effective_client_id = client_id
    if not effective_client_id and current_user.role != 'admin' and current_user.client_id_assigned:
        effective_client_id = current_user.client_id_assigned

    # Build date filter conditions
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    result = {
        "date_range": {
            "start_date": str(start_date),
            "end_date": str(end_date)
        },
        "client_id": effective_client_id,
        "efficiency": None,
        "performance": None,
        "quality": None,
        "availability": None,
        "absenteeism": None,
        "wip_aging": None,
        "otd": None,
        "trends": {
            "efficiency": [],
            "performance": []
        }
    }

    # ---- EFFICIENCY & PERFORMANCE ----
    try:
        prod_query = db.query(
            func.avg(ProductionEntry.efficiency_percentage).label('avg_efficiency'),
            func.avg(ProductionEntry.performance_percentage).label('avg_performance'),
            func.sum(ProductionEntry.units_produced).label('total_units'),
            func.sum(ProductionEntry.run_time_hours).label('total_hours')
        ).filter(
            ProductionEntry.shift_date >= start_dt,
            ProductionEntry.shift_date <= end_dt
        )
        if effective_client_id:
            prod_query = prod_query.filter(ProductionEntry.client_id == effective_client_id)

        prod_result = prod_query.first()
        result["efficiency"] = {
            "current": round(float(prod_result.avg_efficiency or 0), 1),
            "target": 85.0,
            "total_units": int(prod_result.total_units or 0),
            "total_hours": round(float(prod_result.total_hours or 0), 1)
        }
        result["performance"] = {
            "current": round(float(prod_result.avg_performance or 0), 1),
            "target": 90.0
        }

        # Efficiency trend
        trend_query = db.query(
            func.date(ProductionEntry.shift_date).label('date'),
            func.avg(ProductionEntry.efficiency_percentage).label('efficiency'),
            func.avg(ProductionEntry.performance_percentage).label('performance')
        ).filter(
            ProductionEntry.shift_date >= start_dt,
            ProductionEntry.shift_date <= end_dt
        )
        if effective_client_id:
            trend_query = trend_query.filter(ProductionEntry.client_id == effective_client_id)

        trend_results = trend_query.group_by(
            func.date(ProductionEntry.shift_date)
        ).order_by(func.date(ProductionEntry.shift_date)).all()

        result["trends"]["efficiency"] = [
            {"date": str(r.date), "value": round(float(r.efficiency or 0), 1)}
            for r in trend_results
        ]
        result["trends"]["performance"] = [
            {"date": str(r.date), "value": round(float(r.performance or 0), 1)}
            for r in trend_results
        ]
    except Exception as e:
        result["efficiency"] = {"current": 0, "target": 85.0, "error": str(e)}
        result["performance"] = {"current": 0, "target": 90.0, "error": str(e)}

    # ---- QUALITY (FPY, RTY, PPM, DPMO) ----
    try:
        fpy_rty = calculate_fpy_rty(db, effective_client_id, start_date, end_date)
        ppm_data = calculate_ppm(db, effective_client_id, start_date, end_date)
        dpmo_data = calculate_dpmo(db, effective_client_id, start_date, end_date)

        result["quality"] = {
            "fpy": round(fpy_rty.get("fpy", 0), 1),
            "rty": round(fpy_rty.get("rty", 0), 1),
            "ppm": int(ppm_data.get("ppm", 0)),
            "dpmo": int(dpmo_data.get("dpmo", 0)),
            "total_inspected": ppm_data.get("total_inspected", 0),
            "total_defective": ppm_data.get("total_defective", 0)
        }
    except Exception as e:
        result["quality"] = {"fpy": 0, "rty": 0, "ppm": 0, "dpmo": 0, "error": str(e)}

    # ---- AVAILABILITY ----
    try:
        downtime_query = db.query(
            func.sum(DowntimeEntry.downtime_duration_minutes / 60.0).label('downtime_hours')
        ).filter(
            DowntimeEntry.shift_date >= start_dt,
            DowntimeEntry.shift_date <= end_dt
        )
        if effective_client_id:
            downtime_query = downtime_query.filter(DowntimeEntry.client_id == effective_client_id)

        downtime_result = downtime_query.first()
        downtime_hours = float(downtime_result.downtime_hours or 0)

        # Calculate scheduled hours from production entries
        scheduled_hours = float(prod_result.total_hours or 480)  # Default to 480 if no data
        availability = ((scheduled_hours - downtime_hours) / scheduled_hours * 100) if scheduled_hours > 0 else 100

        result["availability"] = {
            "current": round(max(0, min(100, availability)), 1),
            "target": 95.0,
            "downtime_hours": round(downtime_hours, 1),
            "scheduled_hours": round(scheduled_hours, 1)
        }
    except Exception as e:
        result["availability"] = {"current": 100, "target": 95.0, "error": str(e)}

    # ---- ABSENTEEISM ----
    try:
        att_query = db.query(
            func.sum(AttendanceEntry.scheduled_hours).label('scheduled'),
            func.sum(func.coalesce(AttendanceEntry.absence_hours, 0)).label('absent'),
            func.count(func.distinct(AttendanceEntry.employee_id)).label('employee_count')
        ).filter(
            AttendanceEntry.shift_date >= start_dt,
            AttendanceEntry.shift_date <= end_dt
        )
        if effective_client_id:
            att_query = att_query.filter(AttendanceEntry.client_id == effective_client_id)

        att_result = att_query.first()
        scheduled = float(att_result.scheduled or 0)
        absent = float(att_result.absent or 0)
        absenteeism_rate = (absent / scheduled * 100) if scheduled > 0 else 0

        result["absenteeism"] = {
            "rate": round(absenteeism_rate, 2),
            "target": 5.0,
            "total_scheduled_hours": round(scheduled, 1),
            "total_absent_hours": round(absent, 1),
            "employee_count": att_result.employee_count or 0
        }
    except Exception as e:
        result["absenteeism"] = {"rate": 0, "target": 5.0, "error": str(e)}

    # ---- WIP AGING ----
    try:
        from backend.schemas.hold_entry import HoldStatus

        # Count active holds (ON_HOLD status)
        wip_query = db.query(
            func.count(HoldEntry.hold_entry_id).label('total_count')
        ).filter(
            HoldEntry.hold_status == HoldStatus.ON_HOLD
        )
        if effective_client_id:
            wip_query = wip_query.filter(HoldEntry.client_id == effective_client_id)

        wip_result = wip_query.first()
        total_active = wip_result.total_count or 0

        # For simplicity, set defaults - proper aging calculation would need hold_date analysis
        result["wip_aging"] = {
            "total_active": total_active,
            "within_target": total_active,
            "overdue": 0,
            "avg_aging_days": 0
        }
    except Exception as e:
        result["wip_aging"] = {"total_active": 0, "within_target": 0, "overdue": 0, "error": str(e)}

    # ---- OTD (On-Time Delivery) ----
    try:
        otd_query = db.query(
            func.count(WorkOrder.work_order_id).label('total'),
            func.sum(case(
                (WorkOrder.actual_delivery_date <= WorkOrder.required_date, 1),
                else_=0
            )).label('on_time')
        ).filter(
            WorkOrder.required_date.isnot(None),
            WorkOrder.required_date >= start_dt,
            WorkOrder.required_date <= end_dt,
            WorkOrder.actual_delivery_date.isnot(None)
        )
        if effective_client_id:
            otd_query = otd_query.filter(WorkOrder.client_id == effective_client_id)

        otd_result = otd_query.first()
        total_orders = otd_result.total or 0
        on_time_orders = otd_result.on_time or 0
        otd_rate = (on_time_orders / total_orders * 100) if total_orders > 0 else 100

        result["otd"] = {
            "rate": round(otd_rate, 1),
            "target": 95.0,
            "total_orders": total_orders,
            "on_time_orders": on_time_orders,
            "late_orders": total_orders - on_time_orders
        }
    except Exception as e:
        result["otd"] = {"rate": 100, "target": 95.0, "error": str(e)}

    return result
