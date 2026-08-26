"""
Alerts - CRUD and Dashboard Endpoints

Covers: list, dashboard, summary, get, create, acknowledge, resolve, dismiss.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Query as OrmQuery, Session
from typing import Any, List, Optional
from datetime import datetime, timedelta, timezone
import uuid

from backend.database import get_db
from backend.orm.alert import Alert, AlertHistory
from backend.schemas.alert import (
    AlertCreate,
    AlertResponse,
    AlertAcknowledge,
    AlertResolve,
    AlertSummary,
    AlertDashboard,
    AlertCategory,
    AlertSeverity,
    AlertStatus,
)
from backend.calculations.alerts import generate_alert_id
from backend.auth.jwt import ClientScope, get_current_user, resolve_client_scope
from backend.middleware.client_auth import verify_client_access
from backend.orm.user import User
from backend.constants import (
    LOOKBACK_DAILY_HOURS,
    MEDIUM_PAGE_SIZE,
    MAX_ALERT_PAGE_SIZE,
    MIN_DAYS_LOOKBACK,
    MAX_DAYS_SHORT,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

crud_router = APIRouter()


def _build_alerts_query(
    db: Session,
    *,
    client_id: Optional[str] = None,
    category: Optional[AlertCategory] = None,
    severity: Optional[AlertSeverity] = None,
    status: Optional[AlertStatus] = None,
    kpi_key: Optional[str] = None,
    days: Optional[int] = None,
    client_ids: Optional[tuple[str, ...]] = None,
) -> "OrmQuery[Alert]":
    """Single source of truth for filtering the ALERT table.

    Both the list endpoint and the summary/dashboard endpoints build their
    queries here so they can never disagree about which alerts count as
    "active" (ISSUE-008). Previously `list_alerts` silently applied a
    7-day recency window by default while `get_alert_summary` applied none,
    so alerts older than a week were counted in the summary chips but never
    appeared in the unfiltered list (summary total_active=9, list=[]). The
    `days` window is now opt-in (None = no date filter) on every caller.
    """
    query = db.query(Alert)

    # SECURITY: confine to the caller's clients. ``client_ids`` is
    # ClientScope.client_ids — None means all clients, correct only for
    # admin/poweruser. Client-less alerts are system-wide and carry no tenant
    # data, so they stay visible. Without this every caller saw every tenant's
    # alerts whenever they omitted client_id.
    if client_ids is not None:
        query = query.filter(or_(Alert.client_id.in_(list(client_ids)), Alert.client_id.is_(None)))

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
    if days is not None:
        from_date = datetime.now(tz=timezone.utc) - timedelta(days=days)
        query = query.filter(Alert.created_at >= from_date)

    return query


@crud_router.get("/", response_model=List[AlertResponse])
async def list_alerts(
    client_id: Optional[str] = Query(None, description="Filter by client"),
    category: Optional[AlertCategory] = Query(None, description="Filter by category"),
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    status: Optional[AlertStatus] = Query(AlertStatus.ACTIVE, description="Filter by status"),
    kpi_key: Optional[str] = Query(None, description="Filter by KPI"),
    days: Optional[int] = Query(
        None,
        ge=MIN_DAYS_LOOKBACK,
        le=MAX_DAYS_SHORT,
        description="Optional recency window in days; omit to match every alert on the same basis as /summary",
    ),
    limit: int = Query(MEDIUM_PAGE_SIZE, ge=MIN_DAYS_LOOKBACK, le=MAX_ALERT_PAGE_SIZE, description="Maximum results"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> Any:
    """
    List alerts with optional filters

    Returns alerts matching the specified criteria, sorted by creation date descending.
    Without an explicit `days` value, this returns every alert matching the other
    filters (same basis /summary uses), so an unfiltered active-status list and the
    summary's total_active can never disagree.
    """
    query = _build_alerts_query(
        db,
        client_id=client_id,
        category=category,
        severity=severity,
        status=status,
        kpi_key=kpi_key,
        days=days,
        client_ids=scope.client_ids,
    )

    alerts = query.order_by(Alert.created_at.desc()).limit(limit).all()

    return [AlertResponse.model_validate(a) for a in alerts]


@crud_router.get("/dashboard", response_model=AlertDashboard)
async def get_alert_dashboard(
    client_id: Optional[str] = Query(None, description="Filter by client"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> Any:
    """
    Get comprehensive alert dashboard

    Returns summary statistics, urgent alerts, and recent activity.
    """
    all_active = _build_alerts_query(
        db, client_id=client_id, status=AlertStatus.ACTIVE, client_ids=scope.client_ids
    ).all()

    # Build summary
    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    urgent_alerts = []
    critical_alerts = []

    for alert in all_active:
        by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1
        by_category[alert.category] = by_category.get(alert.category, 0) + 1

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

    # Get recent alerts (last 24 hours, any status). Built through the shared
    # helper so the SECURITY scope filter cannot be forgotten on this branch.
    recent_query = _build_alerts_query(db, client_id=client_id, client_ids=scope.client_ids).filter(
        Alert.created_at >= datetime.now(tz=timezone.utc) - timedelta(hours=LOOKBACK_DAILY_HOURS)
    )

    recent = recent_query.order_by(Alert.created_at.desc()).limit(10).all()

    return AlertDashboard(
        summary=summary,
        urgent_alerts=urgent_alerts[:5],
        critical_alerts=critical_alerts[:10],
        recent_alerts=[AlertResponse.model_validate(a) for a in recent],
    )


@crud_router.get("/summary", response_model=AlertSummary)
async def get_alert_summary(
    client_id: Optional[str] = Query(None, description="Filter by client"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    scope: ClientScope = Depends(resolve_client_scope),
) -> Any:
    """
    Get quick summary of active alerts

    Lightweight endpoint for status bars and quick checks.
    """
    alerts = _build_alerts_query(db, client_id=client_id, status=AlertStatus.ACTIVE, client_ids=scope.client_ids).all()

    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}

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


@crud_router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get specific alert by ID"""
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    # SECURITY: alert_id alone carried no tenant check. Client-less alerts are
    # system-wide and stay readable.
    if alert.client_id is not None:
        verify_client_access(current_user, alert.client_id, db)
    return AlertResponse.model_validate(alert)


@crud_router.post("/", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    alert_data: AlertCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create new alert manually

    Typically alerts are generated automatically, but manual creation is supported.
    """
    if alert_data.client_id:
        verify_client_access(current_user, alert_data.client_id)

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


@crud_router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert(
    alert_id: str,
    ack_data: AlertAcknowledge,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Acknowledge an alert

    Marks alert as seen but not yet resolved.
    """
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # SECURITY: alert_id alone carried no tenant check, so a scoped caller
    # could mutate another client's alert. The AttributeError below used to
    # mask this as a 500 AFTER the state assignment — a crash is not a denial.
    # Client-less alerts are system-wide and stay actionable.
    if alert.client_id is not None:
        verify_client_access(current_user, alert.client_id, db)

    if alert.status != "active":
        raise HTTPException(status_code=400, detail="Only active alerts can be acknowledged")

    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.now(tz=timezone.utc)
    alert.acknowledged_by = current_user.user_id

    db.commit()
    db.refresh(alert)

    return AlertResponse.model_validate(alert)


@crud_router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert(
    alert_id: str,
    resolve_data: AlertResolve,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Resolve an alert

    Marks alert as resolved with resolution notes.
    """
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # SECURITY: alert_id alone carried no tenant check, so a scoped caller
    # could mutate another client's alert. The AttributeError below used to
    # mask this as a 500 AFTER the state assignment — a crash is not a denial.
    # Client-less alerts are system-wide and stay actionable.
    if alert.client_id is not None:
        verify_client_access(current_user, alert.client_id, db)

    if alert.status == "resolved":
        raise HTTPException(status_code=400, detail="Alert already resolved")

    alert.status = "resolved"
    alert.resolved_at = datetime.now(tz=timezone.utc)
    alert.resolved_by = current_user.user_id
    alert.resolution_notes = resolve_data.resolution_notes

    # Track prediction accuracy if this was a prediction-based alert
    if alert.predicted_value and alert.current_value:
        history = AlertHistory(
            history_id=f"AHT-{uuid.uuid4().hex[:8].upper()}",
            alert_id=alert_id,
            predicted_value=alert.predicted_value,
            actual_value=alert.current_value,
            prediction_date=alert.created_at,
            actual_date=datetime.now(tz=timezone.utc),
        )
        db.add(history)

    db.commit()
    db.refresh(alert)

    return AlertResponse.model_validate(alert)


@crud_router.post("/{alert_id}/dismiss", response_model=AlertResponse)
async def dismiss_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """
    Dismiss an alert

    Marks as false positive or no longer relevant.
    """
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    # SECURITY: alert_id alone carried no tenant check, so a scoped caller
    # could mutate another client's alert. The AttributeError below used to
    # mask this as a 500 AFTER the state assignment — a crash is not a denial.
    # Client-less alerts are system-wide and stay actionable.
    if alert.client_id is not None:
        verify_client_access(current_user, alert.client_id, db)

    alert.status = "dismissed"
    alert.resolved_at = datetime.now(tz=timezone.utc)
    alert.resolved_by = current_user.user_id

    db.commit()
    db.refresh(alert)

    return AlertResponse.model_validate(alert)
