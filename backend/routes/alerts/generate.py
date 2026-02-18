"""
Alerts - Alert Generation Endpoints and Helper Functions

Covers: generate/check-all, generate/otd-risk, generate/quality,
generate/capacity, and the private _check_* helpers.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone
from decimal import Decimal

from backend.database import get_db
from backend.models.alert import Alert
from backend.schemas.kpi_threshold import KPIThreshold
from backend.schemas.alert import (
    AlertResponse,
    AlertCategory,
)
from backend.calculations.alerts import (
    generate_alert_id,
    generate_otd_risk_alert,
    generate_capacity_alert,
    generate_hold_alert,
)
from backend.auth.jwt import get_current_user
from backend.middleware.client_auth import verify_client_access
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

generate_router = APIRouter()


# ==================== Alert Generation Endpoints ====================


@generate_router.post("/generate/check-all")
async def generate_all_alerts(
    client_id: Optional[str] = Query(None, description="Check for specific client"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Run all alert checks and generate new alerts

    This endpoint should be called periodically (e.g., every hour) to check
    for new alert conditions across all KPIs.
    """
    if client_id:
        verify_client_access(current_user, client_id)

    generated_alerts = []
    errors = []

    # Get thresholds
    threshold_query = db.query(KPIThreshold)
    if client_id:
        threshold_query = threshold_query.filter(
            (KPIThreshold.client_id == client_id) | (KPIThreshold.client_id.is_(None))
        )
    thresholds = {t.kpi_key: t for t in threshold_query.all()}

    # Check efficiency
    try:
        efficiency_result = _check_efficiency_alerts(db, client_id, thresholds)
        generated_alerts.extend(efficiency_result)
    except (SQLAlchemyError, ValueError):
        logger.exception("Efficiency alert check failed")
        errors.append("Efficiency check failed")

    # Check OTD
    try:
        otd_result = _check_otd_alerts(db, client_id)
        generated_alerts.extend(otd_result)
    except (SQLAlchemyError, ValueError):
        logger.exception("OTD alert check failed")
        errors.append("OTD check failed")

    # Check quality
    try:
        quality_result = _check_quality_alerts(db, client_id, thresholds)
        generated_alerts.extend(quality_result)
    except (SQLAlchemyError, ValueError):
        logger.exception("Quality alert check failed")
        errors.append("Quality check failed")

    # Check holds
    try:
        hold_result = _check_hold_alerts(db, client_id)
        generated_alerts.extend(hold_result)
    except (SQLAlchemyError, ValueError):
        logger.exception("Hold alert check failed")
        errors.append("Hold check failed")

    return {
        "status": "completed",
        "alerts_generated": len(generated_alerts),
        "alerts": [AlertResponse.model_validate(a) for a in generated_alerts],
        "errors": errors if errors else None,
    }


@generate_router.post("/generate/otd-risk", response_model=List[AlertResponse])
async def check_otd_risk_alerts(
    client_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Check for OTD risk alerts on pending work orders"""
    if client_id:
        verify_client_access(current_user, client_id)
    alerts = _check_otd_alerts(db, client_id)
    return [AlertResponse.model_validate(a) for a in alerts]


@generate_router.post("/generate/quality", response_model=List[AlertResponse])
async def check_quality_alerts(
    client_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Check for quality KPI alerts"""
    if client_id:
        verify_client_access(current_user, client_id)
    thresholds = {t.kpi_key: t for t in db.query(KPIThreshold).all()}
    alerts = _check_quality_alerts(db, client_id, thresholds)
    return [AlertResponse.model_validate(a) for a in alerts]


@generate_router.post("/generate/capacity", response_model=List[AlertResponse])
async def check_capacity_alerts(
    load_percent: Decimal = Query(..., description="Current capacity load %"),
    predicted_idle_days: Optional[int] = Query(None),
    overtime_hours_needed: Optional[Decimal] = Query(None),
    bottleneck_station: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Check for capacity planning alerts

    This is typically called from capacity planning simulation results.
    """
    if client_id:
        verify_client_access(current_user, client_id)

    result = generate_capacity_alert(
        load_percent=load_percent,
        predicted_idle_days=predicted_idle_days,
        overtime_hours_needed=overtime_hours_needed,
        bottleneck_station=bottleneck_station,
    )

    if not result:
        return []

    alert = Alert(
        alert_id=generate_alert_id(),
        category="capacity",
        severity=result.severity,
        status="active",
        title=result.title,
        message=result.message,
        recommendation=result.recommendation,
        client_id=client_id,
        kpi_key="load_percent",
        current_value=float(load_percent),
        alert_metadata=result.metadata,
    )

    db.add(alert)
    db.commit()
    db.refresh(alert)

    return [AlertResponse.model_validate(alert)]


# ==================== Helper Functions ====================


def _check_efficiency_alerts(db: Session, client_id: Optional[str], thresholds: dict) -> List[Alert]:
    """Check efficiency KPI and generate alerts"""
    # This would query actual efficiency data from production entries
    # For now, return empty - will be connected to real data
    return []


def _check_otd_alerts(db: Session, client_id: Optional[str]) -> List[Alert]:
    """Check OTD risk on pending work orders"""
    from backend.schemas.work_order import WorkOrder, WorkOrderStatus

    alerts = []

    query = db.query(WorkOrder).filter(
        WorkOrder.status == WorkOrderStatus.ACTIVE,
        WorkOrder.planned_ship_date.isnot(None),
    )

    if client_id:
        query = query.filter(WorkOrder.client_id == client_id)

    work_orders = query.all()

    for wo in work_orders:
        if not wo.planned_ship_date:
            continue

        due_date = wo.planned_ship_date
        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date)

        if not due_date.tzinfo:
            due_date = due_date.replace(tzinfo=timezone.utc)
        days_remaining = (due_date - datetime.now(tz=timezone.utc)).days

        if days_remaining < 0 or days_remaining > 30:
            continue

        total_qty = wo.planned_quantity or 1
        completed_qty = wo.actual_quantity or 0
        current_completion = Decimal(str((completed_qty / total_qty) * 100))

        if wo.created_at:
            created_at = wo.created_at if wo.created_at.tzinfo else wo.created_at.replace(tzinfo=timezone.utc)
            total_days = (due_date - created_at).days
            elapsed_days = (datetime.now(tz=timezone.utc) - created_at).days
            planned_completion = Decimal(str(min(100, (elapsed_days / max(1, total_days)) * 100)))
        else:
            planned_completion = Decimal("50")

        result = generate_otd_risk_alert(
            work_order_id=wo.work_order_id,
            client_name=wo.client_id or "Unknown",
            due_date=due_date,
            current_completion_percent=current_completion,
            planned_completion_percent=planned_completion,
            days_remaining=days_remaining,
        )

        if result and result.should_alert:
            existing = (
                db.query(Alert)
                .filter(
                    Alert.work_order_id == wo.work_order_id,
                    Alert.category == "otd",
                    Alert.status == "active",
                )
                .first()
            )

            if not existing:
                alert = Alert(
                    alert_id=generate_alert_id(),
                    category="otd",
                    severity=result.severity,
                    status="active",
                    title=result.title,
                    message=result.message,
                    recommendation=result.recommendation,
                    client_id=wo.client_id,
                    kpi_key="otd",
                    work_order_id=wo.work_order_id,
                    current_value=float(current_completion),
                    threshold_value=float(planned_completion),
                    confidence=float(result.confidence) if result.confidence else None,
                    alert_metadata=result.metadata,
                )
                db.add(alert)
                alerts.append(alert)

    db.commit()
    return alerts


def _check_quality_alerts(db: Session, client_id: Optional[str], thresholds: dict) -> List[Alert]:
    """Check quality KPIs and generate alerts"""
    # This would query actual quality data
    # For now, return empty - will be connected to real data
    return []


def _check_hold_alerts(db: Session, client_id: Optional[str]) -> List[Alert]:
    """Check for pending hold approvals"""
    from backend.schemas.hold_entry import HoldEntry, HoldStatus

    query = db.query(HoldEntry).filter(
        HoldEntry.hold_status.in_([HoldStatus.PENDING_HOLD_APPROVAL, HoldStatus.PENDING_RESUME_APPROVAL])
    )

    if client_id:
        query = query.filter(HoldEntry.client_id == client_id)

    pending_holds = query.all()

    if not pending_holds:
        return []

    oldest_hold = min(pending_holds, key=lambda h: h.created_at)
    oldest_hours = (
        int(
            (
                datetime.now(tz=timezone.utc)
                - (
                    oldest_hold.created_at
                    if oldest_hold.created_at.tzinfo
                    else oldest_hold.created_at.replace(tzinfo=timezone.utc)
                )
            ).total_seconds()
            / 3600
        )
        if oldest_hold.created_at
        else None
    )

    total_units = len(pending_holds)

    result = generate_hold_alert(
        pending_holds_count=len(pending_holds),
        oldest_hold_hours=oldest_hours,
        total_units_on_hold=total_units,
    )

    if not result or not result.should_alert:
        return []

    existing = db.query(Alert).filter(Alert.category == "hold", Alert.status == "active").first()

    if existing:
        existing.severity = result.severity
        existing.title = result.title
        existing.message = result.message
        existing.alert_metadata = result.metadata
        db.commit()
        return [existing]

    alert = Alert(
        alert_id=generate_alert_id(),
        category="hold",
        severity=result.severity,
        status="active",
        title=result.title,
        message=result.message,
        recommendation=result.recommendation,
        client_id=client_id,
        kpi_key="hold_approval",
        alert_metadata=result.metadata,
    )

    db.add(alert)
    db.commit()
    db.refresh(alert)

    return [alert]
