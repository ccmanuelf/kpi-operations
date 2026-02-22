"""
CRUD operations for Equipment.
Supports per-client equipment management with soft-delete.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_
from typing import List, Optional

from backend.schemas.equipment import Equipment
from backend.models.equipment import EquipmentCreate, EquipmentUpdate
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)


def create_equipment(db: Session, data: EquipmentCreate) -> Equipment:
    """Create a new equipment entry for a client.

    Args:
        db: Database session.
        data: Equipment creation payload.

    Returns:
        The newly created Equipment ORM object.

    Raises:
        ValueError: If equipment_code already exists for the client,
                    or if is_shared=True but line_id is set.
    """
    # Business rule: shared equipment must not be assigned to a line
    if data.is_shared and data.line_id is not None:
        raise ValueError(
            "Shared equipment (is_shared=True) must not be assigned to a production line (line_id must be None)"
        )

    db_entry = Equipment(
        client_id=data.client_id,
        line_id=data.line_id,
        equipment_code=data.equipment_code,
        equipment_name=data.equipment_name,
        equipment_type=data.equipment_type,
        is_shared=data.is_shared,
        status=data.status,
        last_maintenance_date=data.last_maintenance_date,
        next_maintenance_date=data.next_maintenance_date,
        notes=data.notes,
        is_active=True,
    )
    try:
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
    except IntegrityError:
        db.rollback()
        raise ValueError(
            f"Equipment code '{data.equipment_code}' already exists for client '{data.client_id}'"
        )
    logger.info(
        "Created equipment '%s' (%s) for client '%s'",
        data.equipment_name,
        data.equipment_code,
        data.client_id,
    )
    return db_entry


def list_equipment(
    db: Session,
    client_id: str,
    line_id: Optional[int] = None,
    include_inactive: bool = False,
) -> List[Equipment]:
    """List equipment for a client, optionally filtered by production line.

    When line_id is provided, shared equipment (line_id IS NULL, is_shared=True)
    is included alongside equipment assigned to that line.

    Args:
        db: Database session.
        client_id: Client to filter by.
        line_id: Optional production line filter.
        include_inactive: If True, include deactivated equipment.

    Returns:
        List of Equipment ORM objects ordered by equipment_code.
    """
    query = db.query(Equipment).filter(Equipment.client_id == client_id)

    if not include_inactive:
        query = query.filter(Equipment.is_active == True)  # noqa: E712

    if line_id is not None:
        # Include equipment assigned to the line AND shared equipment
        query = query.filter(
            or_(
                Equipment.line_id == line_id,
                Equipment.is_shared == True,  # noqa: E712
            )
        )

    return query.order_by(Equipment.equipment_code).all()


def list_shared_equipment(
    db: Session,
    client_id: str,
) -> List[Equipment]:
    """List only shared equipment for a client.

    Args:
        db: Database session.
        client_id: Client to filter by.

    Returns:
        List of shared Equipment ORM objects ordered by equipment_code.
    """
    return (
        db.query(Equipment)
        .filter(
            Equipment.client_id == client_id,
            Equipment.is_shared == True,  # noqa: E712
            Equipment.is_active == True,  # noqa: E712
        )
        .order_by(Equipment.equipment_code)
        .all()
    )


def get_equipment(db: Session, equipment_id: int) -> Optional[Equipment]:
    """Get a single equipment entry by ID.

    Args:
        db: Database session.
        equipment_id: Primary key of the equipment.

    Returns:
        Equipment ORM object or None if not found.
    """
    return db.query(Equipment).filter(Equipment.equipment_id == equipment_id).first()


def update_equipment(
    db: Session,
    equipment_id: int,
    data: EquipmentUpdate,
) -> Optional[Equipment]:
    """Update an existing equipment entry.

    Args:
        db: Database session.
        equipment_id: Primary key of the equipment to update.
        data: Fields to update (only non-None fields are applied).

    Returns:
        Updated Equipment ORM object, or None if not found.
    """
    db_entry = db.query(Equipment).filter(Equipment.equipment_id == equipment_id).first()
    if not db_entry:
        return None

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(db_entry, field, value)
    db.commit()
    db.refresh(db_entry)
    logger.info("Updated equipment equipment_id=%d", equipment_id)
    return db_entry


def deactivate_equipment(db: Session, equipment_id: int) -> bool:
    """Soft-delete an equipment entry (set is_active = False).

    Args:
        db: Database session.
        equipment_id: Primary key of the equipment to deactivate.

    Returns:
        True if equipment was found and deactivated, False if not found.
    """
    db_entry = db.query(Equipment).filter(Equipment.equipment_id == equipment_id).first()
    if not db_entry:
        return False
    db_entry.is_active = False
    db.commit()
    logger.info("Deactivated equipment equipment_id=%d", equipment_id)
    return True


def get_equipment_by_code(
    db: Session,
    client_id: str,
    equipment_code: str,
) -> Optional[Equipment]:
    """Lookup equipment by client_id + equipment_code.

    Args:
        db: Database session.
        client_id: Client to filter by.
        equipment_code: Equipment code to look up.

    Returns:
        Equipment ORM object or None if not found.
    """
    return (
        db.query(Equipment)
        .filter(
            Equipment.client_id == client_id,
            Equipment.equipment_code == equipment_code,
        )
        .first()
    )
