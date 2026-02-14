"""
Alert Routes - API endpoints for intelligent alerting system
Provides proactive alerts based on predictions, thresholds, and patterns
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from backend.database import get_db
from backend.models.alert import Alert, AlertConfig, AlertHistory
from backend.schemas.kpi_threshold import KPIThreshold
from backend.schemas.alert import (
    AlertCreate,
    AlertResponse,
    AlertUpdate,
    AlertAcknowledge,
    AlertResolve,
    AlertSummary,
    AlertFilter,
    AlertDashboard,
    AlertCategory,
    AlertSeverity,
    AlertStatus,
    AlertConfigCreate,
    AlertConfigResponse,
    OTDRiskAlert,
    QualityTrendAlert,
    CapacityAlert,
)
from backend.calculations.alerts import (
    generate_alert_id,
    generate_efficiency_alert,
    generate_otd_risk_alert,
    generate_quality_alert,
    generate_capacity_alert,
    generate_prediction_based_alert,
    generate_attendance_alert,
    generate_hold_alert,
)
from backend.auth.jwt import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])


# ==================== Alert CRUD Operations ====================


@router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    client_id: Optional[str] = Query(None, description="Filter by client"),
    category: Optional[AlertCategory] = Query(None, description="Filter by category"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    status: Optional[AlertStatus] = Query(AlertStatus.ACTIVE, description="Filter by status"),
    kpi_key: Optional[str] = Query(None, description="Filter by KPI"),
    days: int = Query(7, ge=1, le=90, description="Days to look back"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    db: Session = Depends(get_db),
):
    """
    List alerts with optional filters

    Returns alerts matching the specified criteria, sorted by creation date descending.
    """
    query = db.query(Alert)

    if client_id:
        query = query.filter(Alert.client_id == client_id)
    if category:
        query = query.filter(Alert.category == category.value)
    if severity:
        query = query.filter(Alert.severity == severity.value)
    if status:
        query = query.filter(Alert.status == status.value)
    if kpi_key:
        query = query.filter(Alert.kpi_key == kpi_key)

    # Date filter
    from_date = datetime.now() - timedelta(days=days)
    query = query.filter(Alert.created_at >= from_date)

    alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()

    return [AlertResponse.model_validate(a) for a in alerts]


@router.get("/dashboard", response_model=AlertDashboard)
async def get_alert_dashboard(
    client_id: Optional[str] = Query(None, description="Filter by client"), db: Session = Depends(get_db)
):
    """
    Get comprehensive alert dashboard

    Returns summary statistics, urgent alerts, and recent activity.
    """
    base_query = db.query(Alert).filter(Alert.status == "active")

    if client_id:
        base_query = base_query.filter(Alert.client_id == client_id)

    all_active = base_query.all()

    # Build summary
    by_severity = {}
    by_category = {}
    urgent_alerts = []
    critical_alerts = []

    for alert in all_active:
        # Count by severity
        by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1
        # Count by category
        by_category[alert.category] = by_category.get(alert.category, 0) + 1

        # Collect urgent and critical
        if alert.severity == "urgent":
            urgent_alerts.append(AlertResponse.model_validate(alert))
        elif alert.severity == "critical":
            critical_alerts.append(AlertResponse.model_validate(alert))

    summary = AlertSummary(
        total_active=len(all_active),
        by_severity=by_severity,
        by_category=by_category,
        critical_count=by_severity.get("critical", 0),
        urgent_count=by_severity.get("urgent", 0),
    )

    # Get recent alerts (last 24 hours, any status)
    recent_query = db.query(Alert).filter(Alert.created_at >= datetime.now() - timedelta(hours=24))
    if client_id:
        recent_query = recent_query.filter(Alert.client_id == client_id)

    recent = recent_query.order_by(Alert.created_at.desc()).limit(10).all()

    return AlertDashboard(
        summary=summary,
        urgent_alerts=urgent_alerts[:5],
        critical_alerts=critical_alerts[:10],
        recent_alerts=[AlertResponse.model_validate(a) for a in recent],
    )


@router.get("/summary", response_model=AlertSummary)
async def get_alert_summary(
    client_id: Optional[str] = Query(None, description="Filter by client"), db: Session = Depends(get_db)
):
    """
    Get quick summary of active alerts

    Lightweight endpoint for status bars and quick checks.
    """
    query = db.query(Alert).filter(Alert.status == "active")

    if client_id:
        query = query.filter(Alert.client_id == client_id)

    alerts = query.all()

    by_severity = {}
    by_category = {}

    for alert in alerts:
        by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1
        by_category[alert.category] = by_category.get(alert.category, 0) + 1

    return AlertSummary(
        total_active=len(alerts),
        by_severity=by_severity,
        by_category=by_category,
        critical_count=by_severity.get("critical", 0),
        urgent_count=by_severity.get("urgent", 0),
    )


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str, db: Session = Depends(get_db)):
    """Get specific alert by ID"""
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return AlertResponse.model_validate(alert)


@router.post("/", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(alert_data: AlertCreate, db: Session = Depends(get_db)):
    """
    Create new alert manually

    Typically alerts are generated automatically, but manual creation is supported.
    """
    alert = Alert(
        alert_id=generate_alert_id(),
        category=alert_data.category.value,
        severity=alert_data.severity.value,
        status="active",
        title=alert_data.title,
        message=alert_data.message,
        recommendation=alert_data.recommendation,
        client_id=alert_data.client_id,
        kpi_key=alert_data.kpi_key,
        work_order_id=alert_data.work_order_id,
        current_value=float(alert_data.current_value) if alert_data.current_value else None,
        threshold_value=float(alert_data.threshold_value) if alert_data.threshold_value else None,
        predicted_value=float(alert_data.predicted_value) if alert_data.predicted_value else None,
        confidence=float(alert_data.confidence) if alert_data.confidence else None,
        alert_metadata=alert_data.metadata,
    )

    db.add(alert)
    db.commit()
    db.refresh(alert)

    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: str,
    ack_data: AlertAcknowledge,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Acknowledge an alert

    Marks alert as seen but not yet resolved.
    """
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status != "active":
        raise HTTPException(status_code=400, detail="Only active alerts can be acknowledged")

    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.now()
    alert.acknowledged_by = current_user.get("user_id")

    db.commit()
    db.refresh(alert)

    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: str,
    resolve_data: AlertResolve,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Resolve an alert

    Marks alert as resolved with resolution notes.
    """
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if alert.status == "resolved":
        raise HTTPException(status_code=400, detail="Alert already resolved")

    alert.status = "resolved"
    alert.resolved_at = datetime.now()
    alert.resolved_by = current_user.get("user_id")
    alert.resolution_notes = resolve_data.resolution_notes

    # Track prediction accuracy if this was a prediction-based alert
    if alert.predicted_value and alert.current_value:
        history = AlertHistory(
            history_id=f"AHT-{uuid.uuid4().hex[:8].upper()}",
            alert_id=alert_id,
            predicted_value=alert.predicted_value,
            actual_value=alert.current_value,
            prediction_date=alert.created_at,
            actual_date=datetime.now(),
        )
        db.add(history)

    db.commit()
    db.refresh(alert)

    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/dismiss", response_model=AlertResponse)
async def dismiss_alert(alert_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Dismiss an alert

    Marks as false positive or no longer relevant.
    """
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = "dismissed"
    alert.resolved_at = datetime.now()
    alert.resolved_by = current_user.get("user_id")

    db.commit()
    db.refresh(alert)

    return AlertResponse.model_validate(alert)


# ==================== Alert Generation Endpoints ====================


@router.post("/generate/check-all")
async def generate_all_alerts(
    client_id: Optional[str] = Query(None, description="Check for specific client"), db: Session = Depends(get_db)
):
    """
    Run all alert checks and generate new alerts

    This endpoint should be called periodically (e.g., every hour) to check
    for new alert conditions across all KPIs.
    """
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
    except Exception as e:
        errors.append(f"Efficiency check failed: {str(e)}")

    # Check OTD
    try:
        otd_result = _check_otd_alerts(db, client_id)
        generated_alerts.extend(otd_result)
    except Exception as e:
        errors.append(f"OTD check failed: {str(e)}")

    # Check quality
    try:
        quality_result = _check_quality_alerts(db, client_id, thresholds)
        generated_alerts.extend(quality_result)
    except Exception as e:
        errors.append(f"Quality check failed: {str(e)}")

    # Check holds
    try:
        hold_result = _check_hold_alerts(db, client_id)
        generated_alerts.extend(hold_result)
    except Exception as e:
        errors.append(f"Hold check failed: {str(e)}")

    return {
        "status": "completed",
        "alerts_generated": len(generated_alerts),
        "alerts": [AlertResponse.model_validate(a) for a in generated_alerts],
        "errors": errors if errors else None,
    }


@router.post("/generate/otd-risk", response_model=List[AlertResponse])
async def check_otd_risk_alerts(client_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Check for OTD risk alerts on pending work orders"""
    alerts = _check_otd_alerts(db, client_id)
    return [AlertResponse.model_validate(a) for a in alerts]


@router.post("/generate/quality", response_model=List[AlertResponse])
async def check_quality_alerts(client_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Check for quality KPI alerts"""
    thresholds = {t.kpi_key: t for t in db.query(KPIThreshold).all()}
    alerts = _check_quality_alerts(db, client_id, thresholds)
    return [AlertResponse.model_validate(a) for a in alerts]


@router.post("/generate/capacity", response_model=List[AlertResponse])
async def check_capacity_alerts(
    load_percent: Decimal = Query(..., description="Current capacity load %"),
    predicted_idle_days: Optional[int] = Query(None),
    overtime_hours_needed: Optional[Decimal] = Query(None),
    bottleneck_station: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Check for capacity planning alerts

    This is typically called from capacity planning simulation results.
    """
    result = generate_capacity_alert(
        load_percent=load_percent,
        predicted_idle_days=predicted_idle_days,
        overtime_hours_needed=overtime_hours_needed,
        bottleneck_station=bottleneck_station,
    )

    if not result:
        return []

    # Create the alert
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


# ==================== Alert Configuration ====================


@router.get("/config/", response_model=List[AlertConfigResponse])
async def list_alert_configs(client_id: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """List alert configurations"""
    query = db.query(AlertConfig)
    if client_id:
        query = query.filter((AlertConfig.client_id == client_id) | (AlertConfig.client_id.is_(None)))
    configs = query.all()
    return [AlertConfigResponse.model_validate(c) for c in configs]


@router.post("/config/", response_model=AlertConfigResponse)
async def create_alert_config(config_data: AlertConfigCreate, db: Session = Depends(get_db)):
    """Create alert configuration"""
    config = AlertConfig(
        config_id=f"ACF-{uuid.uuid4().hex[:8].upper()}",
        client_id=config_data.client_id,
        alert_type=config_data.alert_type.value,
        enabled=config_data.enabled,
        warning_threshold=float(config_data.warning_threshold) if config_data.warning_threshold else None,
        critical_threshold=float(config_data.critical_threshold) if config_data.critical_threshold else None,
        notification_email=config_data.notification_email,
        notification_sms=config_data.notification_sms,
        check_frequency_minutes=config_data.check_frequency_minutes,
    )

    db.add(config)
    db.commit()
    db.refresh(config)

    return AlertConfigResponse.model_validate(config)


# ==================== Alert History & Accuracy ====================


@router.get("/history/accuracy")
async def get_prediction_accuracy(
    days: int = Query(30, ge=7, le=365), category: Optional[AlertCategory] = Query(None), db: Session = Depends(get_db)
):
    """
    Get historical accuracy of prediction-based alerts

    Returns metrics showing how accurate our predictions have been.
    """
    from_date = datetime.now() - timedelta(days=days)

    query = db.query(AlertHistory).filter(AlertHistory.created_at >= from_date, AlertHistory.actual_value.isnot(None))

    if category:
        query = query.join(Alert).filter(Alert.category == category.value)

    history = query.all()

    if not history:
        return {
            "period_days": days,
            "total_predictions": 0,
            "accuracy_metrics": None,
            "message": "No prediction history available for this period",
        }

    # Calculate accuracy metrics
    accurate_count = sum(1 for h in history if h.was_accurate)
    total = len(history)
    errors = [abs(h.error_percent) for h in history if h.error_percent]

    avg_error = sum(errors) / len(errors) if errors else 0
    accuracy_rate = (accurate_count / total * 100) if total > 0 else 0

    return {
        "period_days": days,
        "total_predictions": total,
        "accurate_predictions": accurate_count,
        "accuracy_rate_percent": round(accuracy_rate, 2),
        "average_error_percent": round(avg_error, 2),
        "category": category.value if category else "all",
    }


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

    # Query pending work orders (ACTIVE status)
    query = db.query(WorkOrder).filter(
        WorkOrder.status == WorkOrderStatus.ACTIVE, WorkOrder.planned_ship_date.isnot(None)
    )

    if client_id:
        query = query.filter(WorkOrder.client_id == client_id)

    work_orders = query.all()

    for wo in work_orders:
        if not wo.planned_ship_date:
            continue

        # Calculate progress vs plan
        due_date = wo.planned_ship_date
        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date)

        days_remaining = (due_date - datetime.now()).days

        # Skip if already past due or far in future
        if days_remaining < 0 or days_remaining > 30:
            continue

        # Calculate expected completion (linear progress assumption)
        total_qty = wo.planned_quantity or 1
        completed_qty = wo.actual_quantity or 0
        current_completion = Decimal(str((completed_qty / total_qty) * 100))

        # Expected progress based on time elapsed (simplified)
        # Assume order started when created
        if wo.created_at:
            total_days = (due_date - wo.created_at).days
            elapsed_days = (datetime.now() - wo.created_at).days
            planned_completion = Decimal(str(min(100, (elapsed_days / max(1, total_days)) * 100)))
        else:
            planned_completion = Decimal("50")  # Default assumption

        # Check for alert
        result = generate_otd_risk_alert(
            work_order_id=wo.work_order_id,
            client_name=wo.client_id or "Unknown",
            due_date=due_date,
            current_completion_percent=current_completion,
            planned_completion_percent=planned_completion,
            days_remaining=days_remaining,
        )

        if result and result.should_alert:
            # Check for existing active alert for this work order
            existing = (
                db.query(Alert)
                .filter(Alert.work_order_id == wo.work_order_id, Alert.category == "otd", Alert.status == "active")
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

    # Query pending holds (holds awaiting approval)
    query = db.query(HoldEntry).filter(
        HoldEntry.hold_status.in_([HoldStatus.PENDING_HOLD_APPROVAL, HoldStatus.PENDING_RESUME_APPROVAL])
    )

    if client_id:
        query = query.filter(Hold.client_id == client_id)

    pending_holds = query.all()

    if not pending_holds:
        return []

    # Find oldest pending hold
    oldest_hold = min(pending_holds, key=lambda h: h.created_at)
    oldest_hours = (
        int((datetime.now() - oldest_hold.created_at).total_seconds() / 3600) if oldest_hold.created_at else None
    )

    # Count total holds (HoldEntry doesn't have quantity field, count records)
    total_units = len(pending_holds)

    result = generate_hold_alert(
        pending_holds_count=len(pending_holds), oldest_hold_hours=oldest_hours, total_units_on_hold=total_units
    )

    if not result or not result.should_alert:
        return []

    # Check for existing active hold alert
    existing = db.query(Alert).filter(Alert.category == "hold", Alert.status == "active").first()

    if existing:
        # Update existing alert instead of creating new
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
