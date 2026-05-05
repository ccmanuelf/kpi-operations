"""
CRUD operations for Hold Status and Hold Reason Catalogs.
Supports per-client catalog management and default seeding.
"""

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_
from typing import List, Optional

from backend.orm.hold_status_catalog import HoldStatusCatalog
from backend.orm.hold_reason_catalog import HoldReasonCatalog
from backend.schemas.hold_catalog import (
    HoldStatusCatalogCreate,
    HoldStatusCatalogUpdate,
    HoldReasonCatalogCreate,
    HoldReasonCatalogUpdate,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

# ---- Default seed data ----

DEFAULT_HOLD_STATUSES = [
    ("PENDING_HOLD_APPROVAL", "Pending Hold Approval", 10),
    ("ON_HOLD", "On Hold", 20),
    ("PENDING_RESUME_APPROVAL", "Pending Resume Approval", 30),
    ("RESUMED", "Resumed", 40),
    ("CANCELLED", "Cancelled", 50),
    ("RELEASED", "Released", 60),
    ("SCRAPPED", "Scrapped", 70),
]

DEFAULT_HOLD_REASONS = [
    ("MATERIAL_INSPECTION", "Material Inspection", 10),
    ("QUALITY_ISSUE", "Quality Issue", 20),
    ("ENGINEERING_REVIEW", "Engineering Review", 30),
    ("CUSTOMER_REQUEST", "Customer Request", 40),
    ("MISSING_SPECIFICATION", "Missing Specification", 50),
    ("EQUIPMENT_UNAVAILABLE", "Equipment Unavailable", 60),
    ("CAPACITY_CONSTRAINT", "Capacity Constraint", 70),
    ("MATERIAL_SHORTAGE", "Material Shortage", 80),
    ("ENGINEERING_CHANGE", "Engineering Change", 90),
    ("PENDING_APPROVAL", "Pending Approval", 100),
    ("OTHER", "Other", 110),
]


# =============================================================================
# Hold Status Catalog CRUD
# =============================================================================


def create_hold_status(db: Session, data: HoldStatusCatalogCreate) -> HoldStatusCatalog:
    """Create a new hold status catalog entry for a client."""
    db_entry = HoldStatusCatalog(
        client_id=data.client_id,
        status_code=data.status_code.upper(),
        display_name=data.display_name,
        is_default=data.is_default,
        is_active=True,
        sort_order=data.sort_order,
    )
    try:
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
    except IntegrityError:
        db.rollback()
        raise ValueError(f"Status code '{data.status_code}' already exists for client '{data.client_id}'")
    logger.info("Created hold status '%s' for client '%s'", data.status_code, data.client_id)
    return db_entry


def list_hold_statuses(
    db: Session,
    client_id: str,
    include_inactive: bool = False,
) -> List[HoldStatusCatalog]:
    """List hold statuses for a client, ordered by sort_order."""
    query = db.query(HoldStatusCatalog).filter(HoldStatusCatalog.client_id == client_id)
    if not include_inactive:
        query = query.filter(HoldStatusCatalog.is_active == True)  # noqa: E712
    return query.order_by(HoldStatusCatalog.sort_order, HoldStatusCatalog.status_code).all()


def update_hold_status(
    db: Session,
    catalog_id: int,
    data: HoldStatusCatalogUpdate,
    client_id: Optional[str] = None,
) -> Optional[HoldStatusCatalog]:
    """Update display_name, is_active, or sort_order of a hold status."""
    query = db.query(HoldStatusCatalog).filter(HoldStatusCatalog.catalog_id == catalog_id)
    if client_id is not None:
        query = query.filter(HoldStatusCatalog.client_id == client_id)
    db_entry = query.first()
    if not db_entry:
        return None
    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(db_entry, field, value)
    db.commit()
    db.refresh(db_entry)
    logger.info("Updated hold status catalog_id=%d", catalog_id)
    return db_entry


def deactivate_hold_status(db: Session, catalog_id: int, client_id: Optional[str] = None) -> bool:
    """Soft-delete a hold status (set is_active = False)."""
    query = db.query(HoldStatusCatalog).filter(HoldStatusCatalog.catalog_id == catalog_id)
    if client_id is not None:
        query = query.filter(HoldStatusCatalog.client_id == client_id)
    db_entry = query.first()
    if not db_entry:
        return False
    db_entry.is_active = False
    db.commit()
    logger.info("Deactivated hold status catalog_id=%d", catalog_id)
    return True


def validate_hold_status_for_client(db: Session, client_id: str, status_code: str) -> bool:
    """Check whether a status_code is active in the client's catalog."""
    exists = (
        db.query(HoldStatusCatalog)
        .filter(
            and_(
                HoldStatusCatalog.client_id == client_id,
                HoldStatusCatalog.status_code == status_code,
                HoldStatusCatalog.is_active == True,  # noqa: E712
            )
        )
        .first()
    )
    return exists is not None


# =============================================================================
# Hold Reason Catalog CRUD
# =============================================================================


def create_hold_reason(db: Session, data: HoldReasonCatalogCreate) -> HoldReasonCatalog:
    """Create a new hold reason catalog entry for a client."""
    db_entry = HoldReasonCatalog(
        client_id=data.client_id,
        reason_code=data.reason_code.upper(),
        display_name=data.display_name,
        is_default=data.is_default,
        is_active=True,
        sort_order=data.sort_order,
    )
    try:
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
    except IntegrityError:
        db.rollback()
        raise ValueError(f"Reason code '{data.reason_code}' already exists for client '{data.client_id}'")
    logger.info("Created hold reason '%s' for client '%s'", data.reason_code, data.client_id)
    return db_entry


def list_hold_reasons(
    db: Session,
    client_id: str,
    include_inactive: bool = False,
) -> List[HoldReasonCatalog]:
    """List hold reasons for a client, ordered by sort_order."""
    query = db.query(HoldReasonCatalog).filter(HoldReasonCatalog.client_id == client_id)
    if not include_inactive:
        query = query.filter(HoldReasonCatalog.is_active == True)  # noqa: E712
    return query.order_by(HoldReasonCatalog.sort_order, HoldReasonCatalog.reason_code).all()


def update_hold_reason(
    db: Session,
    catalog_id: int,
    data: HoldReasonCatalogUpdate,
    client_id: Optional[str] = None,
) -> Optional[HoldReasonCatalog]:
    """Update display_name, is_active, or sort_order of a hold reason."""
    query = db.query(HoldReasonCatalog).filter(HoldReasonCatalog.catalog_id == catalog_id)
    if client_id is not None:
        query = query.filter(HoldReasonCatalog.client_id == client_id)
    db_entry = query.first()
    if not db_entry:
        return None
    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(db_entry, field, value)
    db.commit()
    db.refresh(db_entry)
    logger.info("Updated hold reason catalog_id=%d", catalog_id)
    return db_entry


def deactivate_hold_reason(db: Session, catalog_id: int, client_id: Optional[str] = None) -> bool:
    """Soft-delete a hold reason (set is_active = False)."""
    query = db.query(HoldReasonCatalog).filter(HoldReasonCatalog.catalog_id == catalog_id)
    if client_id is not None:
        query = query.filter(HoldReasonCatalog.client_id == client_id)
    db_entry = query.first()
    if not db_entry:
        return False
    db_entry.is_active = False
    db.commit()
    logger.info("Deactivated hold reason catalog_id=%d", catalog_id)
    return True


def validate_hold_reason_for_client(db: Session, client_id: str, reason_code: str) -> bool:
    """Check whether a reason_code is active in the client's catalog."""
    exists = (
        db.query(HoldReasonCatalog)
        .filter(
            and_(
                HoldReasonCatalog.client_id == client_id,
                HoldReasonCatalog.reason_code == reason_code,
                HoldReasonCatalog.is_active == True,  # noqa: E712
            )
        )
        .first()
    )
    return exists is not None


# =============================================================================
# Seed Defaults
# =============================================================================


def seed_defaults(db: Session, client_id: str) -> dict:
    """
    Seed the default 7 statuses and 11 reasons for a client.
    Skips entries that already exist (idempotent).
    Returns summary: {"statuses_created": N, "reasons_created": N, "skipped": N}
    """
    statuses_created = 0
    reasons_created = 0
    skipped = 0

    # Seed statuses
    for code, display, order in DEFAULT_HOLD_STATUSES:
        existing = (
            db.query(HoldStatusCatalog)
            .filter(
                and_(
                    HoldStatusCatalog.client_id == client_id,
                    HoldStatusCatalog.status_code == code,
                )
            )
            .first()
        )
        if existing:
            skipped += 1
            continue
        db.add(
            HoldStatusCatalog(
                client_id=client_id,
                status_code=code,
                display_name=display,
                is_default=True,
                is_active=True,
                sort_order=order,
            )
        )
        statuses_created += 1

    # Seed reasons
    for code, display, order in DEFAULT_HOLD_REASONS:
        existing = (
            db.query(HoldReasonCatalog)
            .filter(
                and_(
                    HoldReasonCatalog.client_id == client_id,
                    HoldReasonCatalog.reason_code == code,
                )
            )
            .first()
        )
        if existing:
            skipped += 1
            continue
        db.add(
            HoldReasonCatalog(
                client_id=client_id,
                reason_code=code,
                display_name=display,
                is_default=True,
                is_active=True,
                sort_order=order,
            )
        )
        reasons_created += 1

    db.commit()
    logger.info(
        "Seeded defaults for client '%s': %d statuses, %d reasons, %d skipped",
        client_id,
        statuses_created,
        reasons_created,
        skipped,
    )
    return {
        "statuses_created": statuses_created,
        "reasons_created": reasons_created,
        "skipped": skipped,
    }
