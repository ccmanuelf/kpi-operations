"""
Alerts - Configuration and History Endpoints

Covers: alert config list/create, prediction accuracy history.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta, timezone
import uuid

from backend.database import get_db
from backend.models.alert import AlertConfig, AlertHistory
from backend.schemas.alert import (
    AlertConfigCreate,
    AlertConfigResponse,
    AlertCategory,
)
from backend.auth.jwt import get_current_user
from backend.middleware.client_auth import verify_client_access
from backend.constants import (
    LOOKBACK_WEEKLY_DAYS,
    LOOKBACK_MONTHLY_DAYS,
    MAX_DAYS_LONG,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

config_history_router = APIRouter()


# ==================== Alert Configuration ====================


@config_history_router.get("/config/", response_model=List[AlertConfigResponse])
async def list_alert_configs(
    client_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List alert configurations"""
    if client_id:
        verify_client_access(current_user, client_id)
    query = db.query(AlertConfig)
    if client_id:
        query = query.filter((AlertConfig.client_id == client_id) | (AlertConfig.client_id.is_(None)))
    configs = query.all()
    return [AlertConfigResponse.model_validate(c) for c in configs]


@config_history_router.post("/config/", response_model=AlertConfigResponse)
async def create_alert_config(
    config_data: AlertConfigCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create alert configuration"""
    if config_data.client_id:
        verify_client_access(current_user, config_data.client_id)
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


@config_history_router.get("/history/accuracy")
async def get_prediction_accuracy(
    days: int = Query(LOOKBACK_MONTHLY_DAYS, ge=LOOKBACK_WEEKLY_DAYS, le=MAX_DAYS_LONG),
    category: Optional[AlertCategory] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Get historical accuracy of prediction-based alerts

    Returns metrics showing how accurate our predictions have been.
    """
    from backend.models.alert import Alert

    from_date = datetime.now(tz=timezone.utc) - timedelta(days=days)

    query = db.query(AlertHistory).filter(
        AlertHistory.created_at >= from_date,
        AlertHistory.actual_value.isnot(None),
    )

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
