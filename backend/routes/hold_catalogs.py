"""
Hold Catalogs API Routes
Manage client-configurable hold statuses and hold reasons.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.orm.user import User
from backend.utils.logging_utils import get_module_logger
from backend.schemas.hold_catalog import (
    HoldStatusCatalogCreate,
    HoldStatusCatalogUpdate,
    HoldStatusCatalogResponse,
    HoldReasonCatalogCreate,
    HoldReasonCatalogUpdate,
    HoldReasonCatalogResponse,
)
from backend.services.hold_catalog_service import (
    create_hold_status_record as create_hold_status,
    list_hold_status_records as list_hold_statuses,
    update_hold_status_record as update_hold_status,
    deactivate_hold_status_record as deactivate_hold_status,
    create_hold_reason_record as create_hold_reason,
    list_hold_reason_records as list_hold_reasons,
    update_hold_reason_record as update_hold_reason,
    deactivate_hold_reason_record as deactivate_hold_reason,
    seed_default_catalogs as seed_defaults,
)

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/hold-catalogs", tags=["Hold Catalogs"])


# =============================================================================
# Hold Status Endpoints
# =============================================================================


@router.get("/statuses", response_model=List[HoldStatusCatalogResponse])
def get_hold_statuses(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[HoldStatusCatalogResponse]:
    """
    List active hold statuses for a client.

    Returns all active status catalog entries ordered by sort_order.
    """
    logger.info("Listing hold statuses for client_id=%s by user=%s", client_id, current_user.user_id)
    return list_hold_statuses(db, client_id)


@router.post("/statuses", response_model=HoldStatusCatalogResponse, status_code=status.HTTP_201_CREATED)
def create_hold_status_endpoint(
    data: HoldStatusCatalogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> HoldStatusCatalogResponse:
    """
    Create a custom hold status for a client.

    Requires supervisor or admin role.
    """
    try:
        result = create_hold_status(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    logger.info("Created hold status '%s' for client '%s'", data.status_code, data.client_id)
    return result


@router.put("/statuses/{catalog_id}", response_model=HoldStatusCatalogResponse)
def update_hold_status_endpoint(
    catalog_id: int,
    data: HoldStatusCatalogUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> HoldStatusCatalogResponse:
    """
    Update a hold status catalog entry.

    Requires supervisor or admin role.
    """
    tenant_filter = current_user.client_id_assigned if current_user.client_id_assigned else None
    result = update_hold_status(db, catalog_id, data, client_id=tenant_filter)
    if not result:
        raise HTTPException(status_code=404, detail="Hold status catalog entry not found")
    return result


@router.delete("/statuses/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hold_status_endpoint(
    catalog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> None:
    """
    Deactivate a hold status (soft delete).

    Requires supervisor or admin role.
    """
    tenant_filter = current_user.client_id_assigned if current_user.client_id_assigned else None
    success = deactivate_hold_status(db, catalog_id, client_id=tenant_filter)
    if not success:
        raise HTTPException(status_code=404, detail="Hold status catalog entry not found")


# =============================================================================
# Hold Reason Endpoints
# =============================================================================


@router.get("/reasons", response_model=List[HoldReasonCatalogResponse])
def get_hold_reasons(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[HoldReasonCatalogResponse]:
    """
    List active hold reasons for a client.

    Returns all active reason catalog entries ordered by sort_order.
    """
    logger.info("Listing hold reasons for client_id=%s by user=%s", client_id, current_user.user_id)
    return list_hold_reasons(db, client_id)


@router.post("/reasons", response_model=HoldReasonCatalogResponse, status_code=status.HTTP_201_CREATED)
def create_hold_reason_endpoint(
    data: HoldReasonCatalogCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> HoldReasonCatalogResponse:
    """
    Create a custom hold reason for a client.

    Requires supervisor or admin role.
    """
    try:
        result = create_hold_reason(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    logger.info("Created hold reason '%s' for client '%s'", data.reason_code, data.client_id)
    return result


@router.put("/reasons/{catalog_id}", response_model=HoldReasonCatalogResponse)
def update_hold_reason_endpoint(
    catalog_id: int,
    data: HoldReasonCatalogUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> HoldReasonCatalogResponse:
    """
    Update a hold reason catalog entry.

    Requires supervisor or admin role.
    """
    tenant_filter = current_user.client_id_assigned if current_user.client_id_assigned else None
    result = update_hold_reason(db, catalog_id, data, client_id=tenant_filter)
    if not result:
        raise HTTPException(status_code=404, detail="Hold reason catalog entry not found")
    return result


@router.delete("/reasons/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hold_reason_endpoint(
    catalog_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> None:
    """
    Deactivate a hold reason (soft delete).

    Requires supervisor or admin role.
    """
    tenant_filter = current_user.client_id_assigned if current_user.client_id_assigned else None
    success = deactivate_hold_reason(db, catalog_id, client_id=tenant_filter)
    if not success:
        raise HTTPException(status_code=404, detail="Hold reason catalog entry not found")


# =============================================================================
# Seed Defaults
# =============================================================================


@router.post("/seed-defaults", status_code=status.HTTP_200_OK)
def seed_defaults_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> dict:
    """
    Seed default hold statuses and reasons for a client.

    Idempotent: skips entries that already exist.
    Requires supervisor or admin role.
    """
    result = seed_defaults(db, client_id)
    logger.info("Seeded hold catalog defaults for client_id=%s: %s", client_id, result)
    return result
