"""
KPI Thresholds Routes

CRUD endpoints for KPI threshold configuration (global and per-client).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone
import uuid

from backend.utils.logging_utils import get_module_logger
from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User

logger = get_module_logger(__name__)

thresholds_router = APIRouter(prefix="/api/kpi-thresholds", tags=["KPI Thresholds"])


@thresholds_router.get("")
def get_kpi_thresholds(
    client_id: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Get KPI thresholds for a specific client or global defaults.
    If client_id is provided, returns client-specific thresholds merged with global defaults.
    If client_id is NULL/not provided, returns only global defaults.
    """
    from backend.schemas.kpi_threshold import KPIThreshold
    from backend.schemas.client import Client

    # Get global defaults
    global_thresholds = db.query(KPIThreshold).filter(KPIThreshold.client_id.is_(None)).all()

    # Build response with global defaults
    result = {"client_id": client_id, "client_name": None, "thresholds": {}}

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
            "is_global": True,
        }

    # If client_id provided, override with client-specific values
    if client_id:
        client = db.query(Client).filter(Client.client_id == client_id).first()
        if client:
            result["client_name"] = client.client_name

        client_thresholds = db.query(KPIThreshold).filter(KPIThreshold.client_id == client_id).all()

        for t in client_thresholds:
            result["thresholds"][t.kpi_key] = {
                "threshold_id": t.threshold_id,
                "kpi_key": t.kpi_key,
                "target_value": t.target_value,
                "warning_threshold": t.warning_threshold,
                "critical_threshold": t.critical_threshold,
                "unit": t.unit,
                "higher_is_better": t.higher_is_better,
                "is_global": False,
            }

    return result


@thresholds_router.put("")
def update_kpi_thresholds(
    thresholds_data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Update KPI thresholds for a client or global.
    Expects: { "client_id": "xxx" or null, "thresholds": { "efficiency": { "target_value": 85 }, ... } }
    """
    if current_user.role not in ["admin", "poweruser"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin or supervisor access required")

    from backend.schemas.kpi_threshold import KPIThreshold

    client_id = thresholds_data.get("client_id")
    thresholds = thresholds_data.get("thresholds", {})

    updated = []
    for kpi_key, values in thresholds.items():
        # Check if threshold exists
        existing = (
            db.query(KPIThreshold)
            .filter(
                KPIThreshold.client_id == client_id if client_id else KPIThreshold.client_id.is_(None),
                KPIThreshold.kpi_key == kpi_key,
            )
            .first()
        )

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
            existing.updated_at = datetime.now(tz=timezone.utc)
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
                created_at=datetime.now(tz=timezone.utc),
                updated_at=datetime.now(tz=timezone.utc),
            )
            db.add(new_threshold)
            updated.append(kpi_key)

    db.commit()

    return {"message": f"Updated {len(updated)} thresholds", "client_id": client_id, "updated_kpis": updated}


@thresholds_router.delete("/{client_id}/{kpi_key}")
def delete_client_threshold(
    client_id: str, kpi_key: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Delete a client-specific threshold (reverts to global default).
    Cannot delete global thresholds.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    from backend.schemas.kpi_threshold import KPIThreshold

    threshold = (
        db.query(KPIThreshold).filter(KPIThreshold.client_id == client_id, KPIThreshold.kpi_key == kpi_key).first()
    )

    if not threshold:
        raise HTTPException(status_code=404, detail="Client threshold not found")

    db.delete(threshold)
    db.commit()

    return {"message": f"Threshold {kpi_key} deleted for client {client_id}, reverted to global default"}
