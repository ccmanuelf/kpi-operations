"""
Equipment API Routes
Manage client equipment/machine registry (create, read, update, soft-delete).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.schemas.user import User
from backend.utils.logging_utils import get_module_logger
from backend.models.equipment import EquipmentCreate, EquipmentUpdate, EquipmentResponse
from backend.crud.equipment import (
    create_equipment,
    list_equipment,
    list_shared_equipment,
    get_equipment,
    update_equipment,
    deactivate_equipment,
)

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/equipment", tags=["Equipment"])


@router.get("/", response_model=List[EquipmentResponse])
def list_equipment_endpoint(
    client_id: str = Query(..., description="Client ID to filter equipment"),
    line_id: Optional[int] = Query(None, description="Optional production line filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EquipmentResponse]:
    """
    List equipment for a client, optionally filtered by production line.

    When line_id is provided, shared equipment is also included.
    """
    logger.info(
        "Listing equipment for client_id=%s line_id=%s by user=%s",
        client_id,
        line_id,
        current_user.user_id,
    )
    return list_equipment(db, client_id, line_id=line_id)


@router.get("/shared", response_model=List[EquipmentResponse])
def list_shared_equipment_endpoint(
    client_id: str = Query(..., description="Client ID to filter shared equipment"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EquipmentResponse]:
    """
    List only shared equipment (common resources) for a client.
    """
    logger.info(
        "Listing shared equipment for client_id=%s by user=%s",
        client_id,
        current_user.user_id,
    )
    return list_shared_equipment(db, client_id)


@router.post("/", response_model=EquipmentResponse, status_code=status.HTTP_201_CREATED)
def create_equipment_endpoint(
    data: EquipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> EquipmentResponse:
    """
    Create a new equipment entry for a client.

    Requires supervisor or admin role.
    Returns 409 on duplicate equipment_code for the same client.
    """
    try:
        result = create_equipment(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    logger.info(
        "Created equipment '%s' (%s) for client '%s'",
        data.equipment_name,
        data.equipment_code,
        data.client_id,
    )
    return result


@router.get("/{equipment_id}", response_model=EquipmentResponse)
def get_equipment_endpoint(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EquipmentResponse:
    """
    Get a single equipment entry by ID.
    """
    result = get_equipment(db, equipment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return result


@router.put("/{equipment_id}", response_model=EquipmentResponse)
def update_equipment_endpoint(
    equipment_id: int,
    data: EquipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> EquipmentResponse:
    """
    Update an equipment entry.

    Requires supervisor or admin role.
    """
    result = update_equipment(db, equipment_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Equipment not found")
    return result


@router.delete("/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_equipment_endpoint(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_supervisor),
) -> None:
    """
    Deactivate an equipment entry (soft delete).

    Requires supervisor or admin role.
    """
    success = deactivate_equipment(db, equipment_id)
    if not success:
        raise HTTPException(status_code=404, detail="Equipment not found")
