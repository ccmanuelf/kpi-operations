"""
CRUD operations for Capacity BOM (Bill of Materials)

Provides operations for managing BOM headers (parent items) and
details (components) for MRP explosion and component availability.

Multi-tenant: All operations enforce client_id isolation.
"""
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.schemas.capacity.bom import CapacityBOMHeader, CapacityBOMDetail
from backend.utils.tenant_guard import ensure_client_id


# ============================================================================
# BOM Header Operations
# ============================================================================

def create_bom_header(
    db: Session,
    client_id: str,
    parent_item_code: str,
    parent_item_description: Optional[str] = None,
    style_code: Optional[str] = None,
    revision: str = "1.0",
    is_active: bool = True,
    notes: Optional[str] = None
) -> CapacityBOMHeader:
    """
    Create a new BOM header.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        parent_item_code: Parent item code
        parent_item_description: Parent item description
        style_code: Linked style code
        revision: BOM revision number
        is_active: Whether BOM is active
        notes: Additional notes

    Returns:
        Created CapacityBOMHeader
    """
    ensure_client_id(client_id, "BOM header creation")

    header = CapacityBOMHeader(
        client_id=client_id,
        parent_item_code=parent_item_code,
        parent_item_description=parent_item_description,
        style_code=style_code,
        revision=revision,
        is_active=is_active,
        notes=notes
    )
    db.add(header)
    db.commit()
    db.refresh(header)
    return header


def get_bom_headers(
    db: Session,
    client_id: str,
    skip: int = 0,
    limit: int = 100,
    include_inactive: bool = False
) -> List[CapacityBOMHeader]:
    """
    Get all BOM headers for a client.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        skip: Number of records to skip (pagination)
        limit: Maximum records to return
        include_inactive: Whether to include inactive BOMs

    Returns:
        List of CapacityBOMHeader entries
    """
    ensure_client_id(client_id, "BOM headers query")

    query = db.query(CapacityBOMHeader).filter(
        CapacityBOMHeader.client_id == client_id
    )

    if not include_inactive:
        query = query.filter(CapacityBOMHeader.is_active == True)

    return query.order_by(CapacityBOMHeader.parent_item_code).offset(skip).limit(limit).all()


def get_bom_header(
    db: Session,
    client_id: str,
    header_id: int
) -> Optional[CapacityBOMHeader]:
    """
    Get a specific BOM header by ID.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        header_id: BOM header ID

    Returns:
        CapacityBOMHeader or None if not found
    """
    ensure_client_id(client_id, "BOM header query")
    return db.query(CapacityBOMHeader).filter(
        and_(
            CapacityBOMHeader.client_id == client_id,
            CapacityBOMHeader.id == header_id
        )
    ).first()


def get_bom_header_by_item(
    db: Session,
    client_id: str,
    parent_item_code: str,
    active_only: bool = True
) -> Optional[CapacityBOMHeader]:
    """
    Get BOM header by parent item code.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        parent_item_code: Parent item code
        active_only: Return only active BOM

    Returns:
        CapacityBOMHeader or None if not found
    """
    ensure_client_id(client_id, "BOM header query")

    filters = [
        CapacityBOMHeader.client_id == client_id,
        CapacityBOMHeader.parent_item_code == parent_item_code
    ]

    if active_only:
        filters.append(CapacityBOMHeader.is_active == True)

    return db.query(CapacityBOMHeader).filter(
        and_(*filters)
    ).first()


def update_bom_header(
    db: Session,
    client_id: str,
    header_id: int,
    **updates
) -> Optional[CapacityBOMHeader]:
    """
    Update a BOM header.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        header_id: BOM header ID to update
        **updates: Fields to update

    Returns:
        Updated CapacityBOMHeader or None if not found
    """
    header = get_bom_header(db, client_id, header_id)
    if not header:
        return None

    for key, value in updates.items():
        if hasattr(header, key) and value is not None:
            setattr(header, key, value)

    db.commit()
    db.refresh(header)
    return header


def delete_bom_header(
    db: Session,
    client_id: str,
    header_id: int,
    soft_delete: bool = True
) -> bool:
    """
    Delete a BOM header (and cascade delete details if hard delete).

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        header_id: BOM header ID to delete
        soft_delete: If True, set is_active=False; otherwise hard delete

    Returns:
        True if deleted/deactivated, False if not found
    """
    header = get_bom_header(db, client_id, header_id)
    if not header:
        return False

    if soft_delete:
        header.is_active = False
        db.commit()
    else:
        # Hard delete - cascade will handle details
        db.delete(header)
        db.commit()

    return True


def get_bom_for_style(
    db: Session,
    client_id: str,
    style_code: str
) -> Optional[CapacityBOMHeader]:
    """
    Get active BOM for a style.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        style_code: Style code

    Returns:
        CapacityBOMHeader or None if not found
    """
    ensure_client_id(client_id, "BOM for style query")
    return db.query(CapacityBOMHeader).filter(
        and_(
            CapacityBOMHeader.client_id == client_id,
            CapacityBOMHeader.style_code == style_code,
            CapacityBOMHeader.is_active == True
        )
    ).first()


# ============================================================================
# BOM Detail Operations
# ============================================================================

def create_bom_detail(
    db: Session,
    client_id: str,
    header_id: int,
    component_item_code: str,
    quantity_per: float = 1.0,
    component_description: Optional[str] = None,
    unit_of_measure: str = "EA",
    waste_percentage: float = 0,
    component_type: Optional[str] = None,
    notes: Optional[str] = None
) -> Optional[CapacityBOMDetail]:
    """
    Create a new BOM detail.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        header_id: Parent BOM header ID
        component_item_code: Component item code
        quantity_per: Quantity per parent unit
        component_description: Component description
        unit_of_measure: Unit of measure (default "EA")
        waste_percentage: Waste/scrap allowance percentage
        component_type: Component type (FABRIC, TRIM, etc.)
        notes: Additional notes

    Returns:
        Created CapacityBOMDetail or None if header not found
    """
    ensure_client_id(client_id, "BOM detail creation")

    # Verify header exists and belongs to client
    header = get_bom_header(db, client_id, header_id)
    if not header:
        return None

    detail = CapacityBOMDetail(
        header_id=header_id,
        client_id=client_id,
        component_item_code=component_item_code,
        component_description=component_description,
        quantity_per=Decimal(str(quantity_per)),
        unit_of_measure=unit_of_measure,
        waste_percentage=Decimal(str(waste_percentage)),
        component_type=component_type,
        notes=notes
    )
    db.add(detail)
    db.commit()
    db.refresh(detail)
    return detail


def get_bom_details(
    db: Session,
    client_id: str,
    header_id: int
) -> List[CapacityBOMDetail]:
    """
    Get all details for a BOM header.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        header_id: BOM header ID

    Returns:
        List of CapacityBOMDetail entries
    """
    ensure_client_id(client_id, "BOM details query")
    return db.query(CapacityBOMDetail).filter(
        and_(
            CapacityBOMDetail.client_id == client_id,
            CapacityBOMDetail.header_id == header_id
        )
    ).order_by(CapacityBOMDetail.component_item_code).all()


def get_bom_detail(
    db: Session,
    client_id: str,
    detail_id: int
) -> Optional[CapacityBOMDetail]:
    """
    Get a specific BOM detail by ID.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        detail_id: BOM detail ID

    Returns:
        CapacityBOMDetail or None if not found
    """
    ensure_client_id(client_id, "BOM detail query")
    return db.query(CapacityBOMDetail).filter(
        and_(
            CapacityBOMDetail.client_id == client_id,
            CapacityBOMDetail.id == detail_id
        )
    ).first()


def update_bom_detail(
    db: Session,
    client_id: str,
    detail_id: int,
    **updates
) -> Optional[CapacityBOMDetail]:
    """
    Update a BOM detail.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        detail_id: BOM detail ID to update
        **updates: Fields to update

    Returns:
        Updated CapacityBOMDetail or None if not found
    """
    detail = get_bom_detail(db, client_id, detail_id)
    if not detail:
        return None

    # Convert float fields to Decimal
    decimal_fields = ['quantity_per', 'waste_percentage']
    for key, value in updates.items():
        if hasattr(detail, key) and value is not None:
            if key in decimal_fields:
                value = Decimal(str(value))
            setattr(detail, key, value)

    db.commit()
    db.refresh(detail)
    return detail


def delete_bom_detail(
    db: Session,
    client_id: str,
    detail_id: int
) -> bool:
    """
    Delete a BOM detail.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        detail_id: BOM detail ID to delete

    Returns:
        True if deleted, False if not found
    """
    detail = get_bom_detail(db, client_id, detail_id)
    if not detail:
        return False

    db.delete(detail)
    db.commit()
    return True


def get_details_by_component(
    db: Session,
    client_id: str,
    component_item_code: str
) -> List[CapacityBOMDetail]:
    """
    Get all BOM details where a component is used.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        component_item_code: Component item code

    Returns:
        List of CapacityBOMDetail entries using the component
    """
    ensure_client_id(client_id, "BOM details by component query")
    return db.query(CapacityBOMDetail).filter(
        and_(
            CapacityBOMDetail.client_id == client_id,
            CapacityBOMDetail.component_item_code == component_item_code
        )
    ).all()


def get_details_by_type(
    db: Session,
    client_id: str,
    header_id: int,
    component_type: str
) -> List[CapacityBOMDetail]:
    """
    Get BOM details by component type.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        header_id: BOM header ID
        component_type: Component type to filter by

    Returns:
        List of CapacityBOMDetail entries of the specified type
    """
    ensure_client_id(client_id, "BOM details by type query")
    return db.query(CapacityBOMDetail).filter(
        and_(
            CapacityBOMDetail.client_id == client_id,
            CapacityBOMDetail.header_id == header_id,
            CapacityBOMDetail.component_type == component_type
        )
    ).all()


def calculate_required_components(
    db: Session,
    client_id: str,
    header_id: int,
    parent_quantity: int
) -> List[dict]:
    """
    Calculate required component quantities for a given parent quantity.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        header_id: BOM header ID
        parent_quantity: Number of parent units to produce

    Returns:
        List of dicts with component info and required quantities
    """
    details = get_bom_details(db, client_id, header_id)

    requirements = []
    for detail in details:
        requirements.append({
            'component_item_code': detail.component_item_code,
            'component_description': detail.component_description,
            'component_type': detail.component_type,
            'unit_of_measure': detail.unit_of_measure,
            'quantity_per': float(detail.quantity_per),
            'waste_percentage': float(detail.waste_percentage),
            'required_quantity': detail.required_quantity(parent_quantity)
        })

    return requirements


def bulk_create_bom_details(
    db: Session,
    client_id: str,
    header_id: int,
    details: List[dict]
) -> List[CapacityBOMDetail]:
    """
    Bulk create BOM details for a header.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        header_id: BOM header ID
        details: List of detail dictionaries

    Returns:
        List of created CapacityBOMDetail entries
    """
    ensure_client_id(client_id, "bulk BOM details create")

    # Verify header exists
    header = get_bom_header(db, client_id, header_id)
    if not header:
        return []

    created = []
    for detail_data in details:
        # Convert float fields to Decimal
        decimal_fields = ['quantity_per', 'waste_percentage']
        for field in decimal_fields:
            if field in detail_data and detail_data[field] is not None:
                detail_data[field] = Decimal(str(detail_data[field]))

        detail = CapacityBOMDetail(
            header_id=header_id,
            client_id=client_id,
            **detail_data
        )
        db.add(detail)
        created.append(detail)

    db.commit()
    for d in created:
        db.refresh(d)

    return created
