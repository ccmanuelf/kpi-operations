"""
CRUD operations for Production Lines.
Supports per-client line management with soft-delete, hierarchy, configurable limits,
and bridging to Capacity Planning production lines.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Dict, List, Optional, Tuple

from backend.orm.production_line import ProductionLine
from backend.orm.capacity.production_lines import CapacityProductionLine
from backend.schemas.production_line import ProductionLineCreate, ProductionLineUpdate
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

# Configurable soft limit for production lines per client.
# Admins can exceed this; non-admin writes receive a warning.
DEFAULT_MAX_LINES_PER_CLIENT = 10


def count_active_lines(db: Session, client_id: str) -> int:
    """Count active production lines for a client.

    Args:
        db: Database session.
        client_id: Client to count lines for.

    Returns:
        Number of active lines.
    """
    return (
        db.query(ProductionLine)
        .filter(
            ProductionLine.client_id == client_id,
            ProductionLine.is_active == True,  # noqa: E712
        )
        .count()
    )


def create_production_line(
    db: Session,
    data: ProductionLineCreate,
    max_lines: int = DEFAULT_MAX_LINES_PER_CLIENT,
) -> ProductionLine:
    """Create a new production line for a client.

    Args:
        db: Database session.
        data: Production line creation payload.
        max_lines: Configurable soft limit (default 10).

    Returns:
        Tuple-like: the newly created ProductionLine ORM object.
        The caller can check the ``_limit_warning`` attribute for a soft-limit message.

    Raises:
        ValueError: If a line with the same (client_id, line_code) already exists.
    """
    # Check duplicate (client_id, line_code)
    existing = (
        db.query(ProductionLine)
        .filter(
            ProductionLine.client_id == data.client_id,
            ProductionLine.line_code == data.line_code,
        )
        .first()
    )
    if existing:
        raise ValueError(f"Line code '{data.line_code}' already exists for client '{data.client_id}'")

    # Check soft limit
    current_count = count_active_lines(db, data.client_id)
    warning = None
    if current_count >= max_lines:
        warning = (
            f"Client '{data.client_id}' has {current_count} active lines "
            f"(soft limit: {max_lines}). Proceeding with creation."
        )
        logger.warning(warning)

    db_entry = ProductionLine(
        client_id=data.client_id,
        line_code=data.line_code,
        line_name=data.line_name,
        department=data.department,
        line_type=data.line_type,
        parent_line_id=data.parent_line_id,
        max_operators=data.max_operators,
        capacity_line_id=data.capacity_line_id,
        is_active=True,
    )
    try:
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
    except IntegrityError:
        db.rollback()
        raise ValueError(f"Line code '{data.line_code}' already exists for client '{data.client_id}'")

    # Attach warning as transient attribute so the route can surface it
    db_entry._limit_warning = warning

    logger.info(
        "Created production line '%s' (%s) for client '%s'",
        data.line_code,
        data.line_name,
        data.client_id,
    )
    return db_entry


def list_production_lines(
    db: Session,
    client_id: str,
    include_inactive: bool = False,
) -> List[ProductionLine]:
    """List production lines for a client, ordered by line_code.

    Args:
        db: Database session.
        client_id: Client to filter by.
        include_inactive: If True, include deactivated lines.

    Returns:
        List of ProductionLine ORM objects.
    """
    query = db.query(ProductionLine).filter(ProductionLine.client_id == client_id)
    if not include_inactive:
        query = query.filter(ProductionLine.is_active == True)  # noqa: E712
    return query.order_by(ProductionLine.line_code).all()


def get_production_line(db: Session, line_id: int) -> Optional[ProductionLine]:
    """Get a single production line by ID.

    Args:
        db: Database session.
        line_id: Primary key of the production line.

    Returns:
        ProductionLine ORM object or None if not found.
    """
    return db.query(ProductionLine).filter(ProductionLine.line_id == line_id).first()


def get_production_line_tree(db: Session, client_id: str) -> List[ProductionLine]:
    """Get top-level production lines (parent_line_id IS NULL) with children loaded.

    The SQLAlchemy ``children`` relationship is lazy='select' by default,
    so accessing ``.children`` on each top-level line triggers child loading.

    Args:
        db: Database session.
        client_id: Client to filter by.

    Returns:
        List of top-level ProductionLine ORM objects with children populated.
    """
    top_level = (
        db.query(ProductionLine)
        .filter(
            ProductionLine.client_id == client_id,
            ProductionLine.parent_line_id.is_(None),
            ProductionLine.is_active == True,  # noqa: E712
        )
        .order_by(ProductionLine.line_code)
        .all()
    )
    # Force-load children so they are available outside the session context
    for line in top_level:
        _ = line.children  # triggers lazy load
    return top_level


def update_production_line(
    db: Session,
    line_id: int,
    data: ProductionLineUpdate,
) -> Optional[ProductionLine]:
    """Update an existing production line.

    Args:
        db: Database session.
        line_id: Primary key of the production line to update.
        data: Fields to update (only non-None fields are applied).

    Returns:
        Updated ProductionLine ORM object, or None if not found.
    """
    db_entry = db.query(ProductionLine).filter(ProductionLine.line_id == line_id).first()
    if not db_entry:
        return None
    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(db_entry, field, value)
    db.commit()
    db.refresh(db_entry)
    logger.info("Updated production line line_id=%d", line_id)
    return db_entry


def deactivate_production_line(db: Session, line_id: int) -> bool:
    """Soft-delete a production line and cascade to its children.

    Args:
        db: Database session.
        line_id: Primary key of the production line to deactivate.

    Returns:
        True if line was found and deactivated, False if not found.
    """
    db_entry = db.query(ProductionLine).filter(ProductionLine.line_id == line_id).first()
    if not db_entry:
        return False

    db_entry.is_active = False

    # Cascade: deactivate all children
    children = db.query(ProductionLine).filter(ProductionLine.parent_line_id == line_id).all()
    deactivated_children = 0
    for child in children:
        if child.is_active:
            child.is_active = False
            deactivated_children += 1

    db.commit()
    logger.info(
        "Deactivated production line line_id=%d (and %d children)",
        line_id,
        deactivated_children,
    )
    return True


# ============================================================================
# Capacity Planning Bridge Functions
# ============================================================================


def link_to_capacity_line(db: Session, line_id: int, capacity_line_id: int) -> Optional[ProductionLine]:
    """Manually link an operational production line to a capacity planning line.

    Args:
        db: Database session.
        line_id: PK of the operational production line.
        capacity_line_id: PK of the CapacityProductionLine to link to.

    Returns:
        Updated ProductionLine or None if the operational line was not found.

    Raises:
        ValueError: If the capacity line does not exist.
    """
    db_entry = db.query(ProductionLine).filter(ProductionLine.line_id == line_id).first()
    if not db_entry:
        return None

    # Validate that the capacity line exists
    cap_line = db.query(CapacityProductionLine).filter(CapacityProductionLine.id == capacity_line_id).first()
    if not cap_line:
        raise ValueError(f"CapacityProductionLine with id={capacity_line_id} does not exist")

    db_entry.capacity_line_id = capacity_line_id
    db.commit()
    db.refresh(db_entry)
    logger.info(
        "Linked operational line_id=%d to capacity line id=%d",
        line_id,
        capacity_line_id,
    )
    return db_entry


def unlink_from_capacity_line(db: Session, line_id: int) -> Optional[ProductionLine]:
    """Remove the capacity planning link from an operational production line.

    Args:
        db: Database session.
        line_id: PK of the operational production line.

    Returns:
        Updated ProductionLine (with capacity_line_id=NULL), or None if not found.
    """
    db_entry = db.query(ProductionLine).filter(ProductionLine.line_id == line_id).first()
    if not db_entry:
        return None

    previous = db_entry.capacity_line_id
    db_entry.capacity_line_id = None
    db.commit()
    db.refresh(db_entry)
    logger.info(
        "Unlinked operational line_id=%d from capacity line id=%s",
        line_id,
        previous,
    )
    return db_entry


def auto_sync_lines(db: Session, client_id: str) -> Dict[str, list]:
    """Automatically link operational lines to capacity lines by matching line_code.

    Only matches within the same client_id. Already-linked lines are skipped.

    Args:
        db: Database session.
        client_id: Client scope for matching.

    Returns:
        Dict with keys:
            - ``matched``: list of dicts with ``line_id``, ``capacity_line_id``, ``line_code``
            - ``unmatched``: list of dicts with ``line_id``, ``line_code`` (no capacity match)
    """
    # Get all active, unlinked operational lines for this client
    ops_lines = (
        db.query(ProductionLine)
        .filter(
            ProductionLine.client_id == client_id,
            ProductionLine.is_active == True,  # noqa: E712
            ProductionLine.capacity_line_id.is_(None),
        )
        .all()
    )

    # Get all active capacity lines for this client, indexed by line_code
    cap_lines = (
        db.query(CapacityProductionLine)
        .filter(
            CapacityProductionLine.client_id == client_id,
            CapacityProductionLine.is_active == True,  # noqa: E712
        )
        .all()
    )
    cap_by_code: Dict[str, CapacityProductionLine] = {cl.line_code: cl for cl in cap_lines}

    matched = []
    unmatched = []

    for ops_line in ops_lines:
        cap_match = cap_by_code.get(ops_line.line_code)
        if cap_match:
            ops_line.capacity_line_id = cap_match.id
            matched.append(
                {
                    "line_id": ops_line.line_id,
                    "capacity_line_id": cap_match.id,
                    "line_code": ops_line.line_code,
                }
            )
        else:
            unmatched.append(
                {
                    "line_id": ops_line.line_id,
                    "line_code": ops_line.line_code,
                }
            )

    if matched:
        db.commit()

    logger.info(
        "Auto-sync for client '%s': %d matched, %d unmatched",
        client_id,
        len(matched),
        len(unmatched),
    )
    return {"matched": matched, "unmatched": unmatched}


def get_unlinked_lines(db: Session, client_id: str) -> List[ProductionLine]:
    """Return active operational lines that have no capacity line link.

    Args:
        db: Database session.
        client_id: Client to filter by.

    Returns:
        List of ProductionLine ORM objects with capacity_line_id IS NULL.
    """
    return (
        db.query(ProductionLine)
        .filter(
            ProductionLine.client_id == client_id,
            ProductionLine.is_active == True,  # noqa: E712
            ProductionLine.capacity_line_id.is_(None),
        )
        .order_by(ProductionLine.line_code)
        .all()
    )
