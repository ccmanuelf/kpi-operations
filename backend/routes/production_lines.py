"""
Production Lines API Routes
Manage operational production lines (create, read, update, soft-delete, tree view).
Includes Capacity Planning bridge endpoints for linking operational lines.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Dict, List, Optional

from backend.database import get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.orm.user import User
from backend.utils.logging_utils import get_module_logger
from backend.schemas.production_line import (
    ProductionLineCreate,
    ProductionLineUpdate,
    ProductionLineResponse,
    ProductionLineTreeResponse,
)
from backend.services.production_line_service import (
    create_line as create_production_line,
    list_lines as list_production_lines,
    get_line as get_production_line,
    get_line_tree as get_production_line_tree,
    update_line as update_production_line,
    deactivate_line as deactivate_production_line,
    link_line_to_capacity as link_to_capacity_line,
    unlink_line_from_capacity as unlink_from_capacity_line,
    auto_sync_capacity_lines as auto_sync_lines,
    list_unlinked_lines as get_unlinked_lines,
)

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/production-lines", tags=["Production Lines"])


@router.get("/", response_model=List[ProductionLineResponse])
def list_production_lines_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProductionLineResponse]:
    """
    List active production lines for a client.

    Returns all active lines ordered by line_code.
    """
    logger.info(
        "Listing production lines for client_id=%s by user=%s",
        client_id,
        current_user.user_id,
    )
    return list_production_lines(db, client_id)


@router.get("/tree", response_model=List[ProductionLineTreeResponse])
def get_production_line_tree_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProductionLineTreeResponse]:
    """
    Get hierarchical tree view of production lines for a client.

    Returns top-level lines with nested children.
    """
    logger.info(
        "Fetching production line tree for client_id=%s by user=%s",
        client_id,
        current_user.user_id,
    )
    return get_production_line_tree(db, client_id)


@router.post("/", response_model=ProductionLineResponse, status_code=status.HTTP_201_CREATED)
def create_production_line_endpoint(
    data: ProductionLineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> ProductionLineResponse:
    """
    Create a new production line for a client.

    Requires supervisor or admin role.
    Returns 409 on duplicate (client_id, line_code).
    Warns (but does not block) if the client exceeds the soft line limit.
    """
    try:
        result = create_production_line(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    # Surface soft-limit warning in response headers if present
    warning = getattr(result, "_limit_warning", None)
    if warning:
        logger.warning("Soft limit warning: %s", warning)

    logger.info(
        "Created production line '%s' for client '%s' by user=%s",
        data.line_code,
        data.client_id,
        current_user.user_id,
    )
    return result


# ============================================================================
# Capacity Planning Bridge Endpoints
# ============================================================================


class LinkCapacityRequest(BaseModel):
    """Request body for linking an operational line to a capacity line."""

    capacity_line_id: int = Field(..., description="PK of CapacityProductionLine")


class SyncCapacityResponse(BaseModel):
    """Response for auto-sync operation."""

    matched: List[Dict] = Field(default_factory=list)
    unmatched: List[Dict] = Field(default_factory=list)


@router.post("/sync-capacity", response_model=SyncCapacityResponse)
def sync_capacity_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> SyncCapacityResponse:
    """
    Auto-sync operational lines to capacity lines by matching line_code.

    Matches are made within the same client_id. Already-linked lines are skipped.
    Requires supervisor or admin role.
    """
    logger.info(
        "Auto-syncing capacity lines for client_id=%s by user=%s",
        client_id,
        current_user.user_id,
    )
    result = auto_sync_lines(db, client_id)
    return SyncCapacityResponse(**result)


@router.get("/unlinked", response_model=List[ProductionLineResponse])
def get_unlinked_lines_endpoint(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProductionLineResponse]:
    """
    Return active operational lines that have no capacity planning link.
    """
    logger.info(
        "Fetching unlinked lines for client_id=%s by user=%s",
        client_id,
        current_user.user_id,
    )
    return get_unlinked_lines(db, client_id)


@router.post("/{line_id}/link-capacity", response_model=ProductionLineResponse)
def link_capacity_endpoint(
    line_id: int,
    body: LinkCapacityRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> ProductionLineResponse:
    """
    Manually link an operational production line to a capacity planning line.

    Requires supervisor or admin role.
    """
    try:
        result = link_to_capacity_line(db, line_id, body.capacity_line_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if not result:
        raise HTTPException(status_code=404, detail="Production line not found")
    logger.info(
        "Linked line_id=%d to capacity_line_id=%d by user=%s",
        line_id,
        body.capacity_line_id,
        current_user.user_id,
    )
    return result


@router.delete("/{line_id}/link-capacity", response_model=ProductionLineResponse)
def unlink_capacity_endpoint(
    line_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> ProductionLineResponse:
    """
    Remove the capacity planning link from an operational production line.

    Requires supervisor or admin role.
    """
    result = unlink_from_capacity_line(db, line_id)
    if not result:
        raise HTTPException(status_code=404, detail="Production line not found")
    logger.info(
        "Unlinked line_id=%d from capacity line by user=%s",
        line_id,
        current_user.user_id,
    )
    return result


@router.get("/{line_id}", response_model=ProductionLineResponse)
def get_production_line_endpoint(
    line_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProductionLineResponse:
    """
    Get a single production line by ID.
    """
    result = get_production_line(db, line_id)
    if not result:
        raise HTTPException(status_code=404, detail="Production line not found")
    return result


@router.put("/{line_id}", response_model=ProductionLineResponse)
def update_production_line_endpoint(
    line_id: int,
    data: ProductionLineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> ProductionLineResponse:
    """
    Update a production line entry.

    Requires supervisor or admin role.
    """
    result = update_production_line(db, line_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Production line not found")
    return result


@router.delete("/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_production_line_endpoint(
    line_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> None:
    """
    Deactivate a production line (soft delete) with cascade to children.

    Requires supervisor or admin role.
    """
    success = deactivate_production_line(db, line_id)
    if not success:
        raise HTTPException(status_code=404, detail="Production line not found")
