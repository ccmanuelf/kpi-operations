"""
CRUD operations for Capacity Stock Snapshots

Provides operations for managing point-in-time inventory positions
for MRP calculations and component availability checking.

Multi-tenant: All operations enforce client_id isolation.
"""

from typing import List, Optional
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from backend.schemas.capacity.stock import CapacityStockSnapshot
from backend.utils.tenant_guard import ensure_client_id


def create_stock_snapshot(
    db: Session,
    client_id: str,
    snapshot_date: date,
    item_code: str,
    on_hand_quantity: float = 0,
    allocated_quantity: float = 0,
    on_order_quantity: float = 0,
    item_description: Optional[str] = None,
    unit_of_measure: str = "EA",
    location: Optional[str] = None,
    notes: Optional[str] = None,
) -> CapacityStockSnapshot:
    """
    Create a new stock snapshot.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        snapshot_date: Date of the snapshot
        item_code: Item code
        on_hand_quantity: Physical inventory quantity
        allocated_quantity: Quantity reserved for orders
        on_order_quantity: Quantity on order (expected receipts)
        item_description: Item description
        unit_of_measure: Unit of measure (default "EA")
        location: Storage location
        notes: Additional notes

    Returns:
        Created CapacityStockSnapshot
    """
    ensure_client_id(client_id, "stock snapshot creation")

    # Calculate available quantity
    available = on_hand_quantity - allocated_quantity + on_order_quantity

    snapshot = CapacityStockSnapshot(
        client_id=client_id,
        snapshot_date=snapshot_date,
        item_code=item_code,
        item_description=item_description,
        on_hand_quantity=Decimal(str(on_hand_quantity)),
        allocated_quantity=Decimal(str(allocated_quantity)),
        on_order_quantity=Decimal(str(on_order_quantity)),
        available_quantity=Decimal(str(available)),
        unit_of_measure=unit_of_measure,
        location=location,
        notes=notes,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def get_stock_snapshots(
    db: Session, client_id: str, skip: int = 0, limit: int = 100, snapshot_date: Optional[date] = None
) -> List[CapacityStockSnapshot]:
    """
    Get all stock snapshots for a client.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        skip: Number of records to skip (pagination)
        limit: Maximum records to return
        snapshot_date: Optional date to filter by

    Returns:
        List of CapacityStockSnapshot entries
    """
    ensure_client_id(client_id, "stock snapshots query")
    query = db.query(CapacityStockSnapshot).filter(CapacityStockSnapshot.client_id == client_id)
    if snapshot_date:
        query = query.filter(CapacityStockSnapshot.snapshot_date == snapshot_date)
    return (
        query.order_by(desc(CapacityStockSnapshot.snapshot_date), CapacityStockSnapshot.item_code)
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_stock_snapshot(db: Session, client_id: str, snapshot_id: int) -> Optional[CapacityStockSnapshot]:
    """
    Get a specific stock snapshot by ID.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        snapshot_id: Snapshot ID

    Returns:
        CapacityStockSnapshot or None if not found
    """
    ensure_client_id(client_id, "stock snapshot query")
    return (
        db.query(CapacityStockSnapshot)
        .filter(and_(CapacityStockSnapshot.client_id == client_id, CapacityStockSnapshot.id == snapshot_id))
        .first()
    )


def update_stock_snapshot(db: Session, client_id: str, snapshot_id: int, **updates) -> Optional[CapacityStockSnapshot]:
    """
    Update a stock snapshot.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        snapshot_id: Snapshot ID to update
        **updates: Fields to update

    Returns:
        Updated CapacityStockSnapshot or None if not found
    """
    snapshot = get_stock_snapshot(db, client_id, snapshot_id)
    if not snapshot:
        return None

    # Convert float fields to Decimal
    decimal_fields = ["on_hand_quantity", "allocated_quantity", "on_order_quantity", "available_quantity"]
    for key, value in updates.items():
        if hasattr(snapshot, key) and value is not None:
            if key in decimal_fields:
                value = Decimal(str(value))
            setattr(snapshot, key, value)

    # Recalculate available if quantities changed
    if any(field in updates for field in ["on_hand_quantity", "allocated_quantity", "on_order_quantity"]):
        snapshot.available_quantity = Decimal(str(snapshot.calculate_available()))

    db.commit()
    db.refresh(snapshot)
    return snapshot


def delete_stock_snapshot(db: Session, client_id: str, snapshot_id: int) -> bool:
    """
    Delete a stock snapshot.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        snapshot_id: Snapshot ID to delete

    Returns:
        True if deleted, False if not found
    """
    snapshot = get_stock_snapshot(db, client_id, snapshot_id)
    if not snapshot:
        return False

    db.delete(snapshot)
    db.commit()
    return True


def get_latest_stock(db: Session, client_id: str, item_code: str) -> Optional[CapacityStockSnapshot]:
    """
    Get the most recent stock snapshot for an item.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        item_code: Item code

    Returns:
        Most recent CapacityStockSnapshot or None if not found
    """
    ensure_client_id(client_id, "latest stock query")
    return (
        db.query(CapacityStockSnapshot)
        .filter(and_(CapacityStockSnapshot.client_id == client_id, CapacityStockSnapshot.item_code == item_code))
        .order_by(desc(CapacityStockSnapshot.snapshot_date))
        .first()
    )


def get_available_stock(db: Session, client_id: str, item_code: str, as_of_date: Optional[date] = None) -> float:
    """
    Get current available stock for an item.

    Calculates: on_hand - allocated + on_order

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        item_code: Item code
        as_of_date: Optional date filter (uses latest if None)

    Returns:
        Available quantity or 0 if no snapshot exists
    """
    if as_of_date:
        ensure_client_id(client_id, "available stock query")
        snapshot = (
            db.query(CapacityStockSnapshot)
            .filter(
                and_(
                    CapacityStockSnapshot.client_id == client_id,
                    CapacityStockSnapshot.item_code == item_code,
                    CapacityStockSnapshot.snapshot_date <= as_of_date,
                )
            )
            .order_by(desc(CapacityStockSnapshot.snapshot_date))
            .first()
        )
    else:
        snapshot = get_latest_stock(db, client_id, item_code)
    if not snapshot:
        return 0.0
    return snapshot.calculate_available()


def get_shortage_items(
    db: Session, client_id: str, snapshot_date: Optional[date] = None
) -> List[CapacityStockSnapshot]:
    """
    Get items with zero or negative available quantity (shortages).

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        snapshot_date: Optional date filter

    Returns:
        List of CapacityStockSnapshot entries with shortages
    """
    ensure_client_id(client_id, "shortage items query")

    filters = [CapacityStockSnapshot.client_id == client_id, CapacityStockSnapshot.available_quantity <= Decimal("0")]

    if snapshot_date:
        filters.append(CapacityStockSnapshot.snapshot_date == snapshot_date)

    return (
        db.query(CapacityStockSnapshot).filter(and_(*filters)).order_by(CapacityStockSnapshot.available_quantity).all()
    )


def get_stock_by_date(db: Session, client_id: str, snapshot_date: date) -> List[CapacityStockSnapshot]:
    """
    Get all stock snapshots for a specific date.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        snapshot_date: Date to query

    Returns:
        List of CapacityStockSnapshot entries for the date
    """
    ensure_client_id(client_id, "stock by date query")
    return (
        db.query(CapacityStockSnapshot)
        .filter(
            and_(CapacityStockSnapshot.client_id == client_id, CapacityStockSnapshot.snapshot_date == snapshot_date)
        )
        .order_by(CapacityStockSnapshot.item_code)
        .all()
    )


def get_stock_by_location(
    db: Session, client_id: str, location: str, snapshot_date: Optional[date] = None
) -> List[CapacityStockSnapshot]:
    """
    Get stock snapshots by location.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        location: Location to filter by
        snapshot_date: Optional date filter

    Returns:
        List of CapacityStockSnapshot entries for the location
    """
    ensure_client_id(client_id, "stock by location query")

    filters = [CapacityStockSnapshot.client_id == client_id, CapacityStockSnapshot.location == location]

    if snapshot_date:
        filters.append(CapacityStockSnapshot.snapshot_date == snapshot_date)

    return (
        db.query(CapacityStockSnapshot)
        .filter(and_(*filters))
        .order_by(desc(CapacityStockSnapshot.snapshot_date), CapacityStockSnapshot.item_code)
        .all()
    )


def check_stock_availability(db: Session, client_id: str, item_code: str, required_quantity: float) -> dict:
    """
    Check if required quantity is available.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        item_code: Item code
        required_quantity: Quantity needed

    Returns:
        Dict with availability status, available quantity, and shortage
    """
    snapshot = get_latest_stock(db, client_id, item_code)

    if not snapshot:
        return {
            "item_code": item_code,
            "is_available": False,
            "available_quantity": 0,
            "required_quantity": required_quantity,
            "shortage_quantity": required_quantity,
            "has_snapshot": False,
        }

    available = snapshot.calculate_available()
    is_short = snapshot.is_short(required_quantity)
    shortage = snapshot.shortage_quantity(required_quantity)

    return {
        "item_code": item_code,
        "is_available": not is_short,
        "available_quantity": available,
        "required_quantity": required_quantity,
        "shortage_quantity": shortage,
        "has_snapshot": True,
        "snapshot_date": snapshot.snapshot_date,
        "location": snapshot.location,
    }


def check_multiple_items_availability(db: Session, client_id: str, requirements: List[dict]) -> List[dict]:
    """
    Check availability for multiple items.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        requirements: List of dicts with 'item_code' and 'required_quantity'

    Returns:
        List of availability check results
    """
    results = []
    for req in requirements:
        result = check_stock_availability(db, client_id, req["item_code"], req["required_quantity"])
        results.append(result)

    return results


def get_low_stock_items(db: Session, client_id: str, threshold_quantity: float = 0) -> List[CapacityStockSnapshot]:
    """
    Get items with low or zero available stock.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        threshold_quantity: Minimum available quantity threshold

    Returns:
        List of CapacityStockSnapshot entries below threshold
    """
    ensure_client_id(client_id, "low stock query")

    # Get latest snapshots with subquery
    from sqlalchemy import func

    # Subquery to get max date per item
    subquery = (
        db.query(CapacityStockSnapshot.item_code, func.max(CapacityStockSnapshot.snapshot_date).label("max_date"))
        .filter(CapacityStockSnapshot.client_id == client_id)
        .group_by(CapacityStockSnapshot.item_code)
        .subquery()
    )

    # Join to get full records
    return (
        db.query(CapacityStockSnapshot)
        .filter(
            and_(
                CapacityStockSnapshot.client_id == client_id,
                CapacityStockSnapshot.available_quantity <= Decimal(str(threshold_quantity)),
            )
        )
        .join(
            subquery,
            and_(
                CapacityStockSnapshot.item_code == subquery.c.item_code,
                CapacityStockSnapshot.snapshot_date == subquery.c.max_date,
            ),
        )
        .order_by(CapacityStockSnapshot.available_quantity)
        .all()
    )


def bulk_create_stock_snapshots(db: Session, client_id: str, snapshots: List[dict]) -> List[CapacityStockSnapshot]:
    """
    Bulk create stock snapshots.

    Args:
        db: Database session
        client_id: Client identifier for multi-tenant isolation
        snapshots: List of snapshot dictionaries

    Returns:
        List of created CapacityStockSnapshot entries
    """
    ensure_client_id(client_id, "bulk stock snapshots create")

    created = []
    for snap_data in snapshots:
        # Convert float fields to Decimal
        decimal_fields = ["on_hand_quantity", "allocated_quantity", "on_order_quantity"]
        for field in decimal_fields:
            if field in snap_data and snap_data[field] is not None:
                snap_data[field] = Decimal(str(snap_data[field]))

        # Calculate available if not provided
        if "available_quantity" not in snap_data:
            on_hand = float(snap_data.get("on_hand_quantity", 0))
            allocated = float(snap_data.get("allocated_quantity", 0))
            on_order = float(snap_data.get("on_order_quantity", 0))
            snap_data["available_quantity"] = Decimal(str(on_hand - allocated + on_order))
        else:
            snap_data["available_quantity"] = Decimal(str(snap_data["available_quantity"]))

        snapshot = CapacityStockSnapshot(client_id=client_id, **snap_data)
        db.add(snapshot)
        created.append(snapshot)

    db.commit()
    for snap in created:
        db.refresh(snap)

    return created
