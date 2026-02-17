"""
Capacity Planning - BOM and Stock Endpoints

Bill of Materials (headers + details + explosion) and Stock Snapshot CRUD.
"""

from typing import List, Optional
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.middleware.client_auth import verify_client_access
from backend.constants import DEFAULT_PAGE_SIZE
from backend.crud.capacity import bom, stock

from ._models import (
    BOMHeaderCreate,
    BOMHeaderUpdate,
    BOMDetailCreate,
    BOMDetailUpdate,
    BOMHeaderResponse,
    BOMDetailResponse,
    BOMExplosionRequest,
    BOMExplosionResponse,
    StockSnapshotCreate,
    StockSnapshotUpdate,
    StockSnapshotResponse,
    AvailableStockResponse,
    MessageResponse,
)
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

bom_stock_router = APIRouter()


# =============================================================================
# BOM Endpoints
# =============================================================================


@bom_stock_router.get("/bom", response_model=List[BOMHeaderResponse])
def list_bom_headers(
    client_id: str = Query(..., description="Client ID"),
    include_inactive: bool = False,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get BOM headers for a client."""
    verify_client_access(current_user, client_id, db)
    return bom.get_bom_headers(db, client_id, skip, limit, include_inactive)


@bom_stock_router.post("/bom", response_model=BOMHeaderResponse, status_code=status.HTTP_201_CREATED)
def create_bom_header(
    header: BOMHeaderCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new BOM header."""
    verify_client_access(current_user, client_id, db)
    return bom.create_bom_header(
        db,
        client_id,
        header.parent_item_code,
        header.parent_item_description,
        header.style_code,
        header.revision,
        header.is_active,
        header.notes,
    )


@bom_stock_router.get("/bom/{header_id}", response_model=BOMHeaderResponse, responses={404: {"description": "BOM header not found"}})
def get_bom_header(
    header_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific BOM header."""
    verify_client_access(current_user, client_id, db)
    header = bom.get_bom_header(db, client_id, header_id)
    if not header:
        raise HTTPException(status_code=404, detail="BOM header not found")
    return header


@bom_stock_router.put("/bom/{header_id}", response_model=BOMHeaderResponse, responses={404: {"description": "BOM header not found"}})
def update_bom_header(
    header_id: int,
    update: BOMHeaderUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a BOM header."""
    verify_client_access(current_user, client_id, db)
    header = bom.update_bom_header(db, client_id, header_id, **update.model_dump(exclude_unset=True))
    if not header:
        raise HTTPException(status_code=404, detail="BOM header not found")
    return header


@bom_stock_router.delete("/bom/{header_id}", response_model=MessageResponse, responses={404: {"description": "BOM header not found"}})
def delete_bom_header(
    header_id: int,
    client_id: str = Query(..., description="Client ID"),
    cascade: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a BOM header (and optionally its details)."""
    verify_client_access(current_user, client_id, db)
    if not bom.delete_bom_header(db, client_id, header_id, cascade):
        raise HTTPException(status_code=404, detail="BOM header not found")
    return {"message": "BOM header deleted"}


@bom_stock_router.get("/bom/{header_id}/details", response_model=List[BOMDetailResponse])
def list_bom_details(
    header_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get details for a BOM header."""
    verify_client_access(current_user, client_id, db)
    return bom.get_bom_details(db, client_id, header_id)


@bom_stock_router.post("/bom/{header_id}/details", response_model=BOMDetailResponse, status_code=status.HTTP_201_CREATED)
def create_bom_detail(
    header_id: int,
    detail: BOMDetailCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a component to a BOM."""
    verify_client_access(current_user, client_id, db)
    return bom.create_bom_detail(
        db,
        client_id,
        header_id,
        detail.component_item_code,
        detail.quantity_per,
        detail.component_description,
        detail.unit_of_measure,
        detail.waste_percentage,
        detail.component_type,
        detail.notes,
    )


@bom_stock_router.put("/bom/details/{detail_id}", response_model=BOMDetailResponse, responses={404: {"description": "BOM detail not found"}})
def update_bom_detail(
    detail_id: int,
    update: BOMDetailUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a BOM detail."""
    verify_client_access(current_user, client_id, db)
    detail = bom.update_bom_detail(db, client_id, detail_id, **update.model_dump(exclude_unset=True))
    if not detail:
        raise HTTPException(status_code=404, detail="BOM detail not found")
    return detail


@bom_stock_router.delete("/bom/details/{detail_id}", response_model=MessageResponse, responses={404: {"description": "BOM detail not found"}})
def delete_bom_detail(
    detail_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a BOM detail."""
    verify_client_access(current_user, client_id, db)
    if not bom.delete_bom_detail(db, client_id, detail_id):
        raise HTTPException(status_code=404, detail="BOM detail not found")
    return {"message": "BOM detail deleted"}


@bom_stock_router.post("/bom/explode", response_model=BOMExplosionResponse, responses={400: {"description": "BOM explosion failed"}})
def explode_bom(
    request: BOMExplosionRequest,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run BOM explosion for a parent item."""
    verify_client_access(current_user, client_id, db)
    from backend.services.capacity.bom_service import BOMService

    service = BOMService(db)
    try:
        result = service.explode_bom(client_id, request.parent_item_code, Decimal(str(request.quantity)))
        return {
            "parent_item_code": result.parent_item_code,
            "quantity_requested": float(result.quantity_requested),
            "components": [
                {
                    "component_item_code": c.component_item_code,
                    "component_description": c.component_description,
                    "gross_required": float(c.gross_required),
                    "net_required": float(c.net_required),
                    "waste_percentage": float(c.waste_percentage),
                    "unit_of_measure": c.unit_of_measure,
                    "component_type": c.component_type,
                }
                for c in result.components
            ],
            "total_components": result.total_components,
        }
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.exception("Database error in BOM explosion for parent_item_code=%s", request.parent_item_code)
        raise HTTPException(status_code=503, detail="Database error during BOM explosion")
    except (ValueError, TypeError) as e:
        logger.exception("Validation error in BOM explosion for parent_item_code=%s", request.parent_item_code)
        raise HTTPException(status_code=400, detail="Invalid BOM explosion parameters")
    except Exception as e:
        db.rollback()
        logger.exception("BOM explosion failed for parent_item_code=%s", request.parent_item_code)
        raise HTTPException(status_code=400, detail="BOM explosion failed")


# =============================================================================
# Stock Endpoints
# =============================================================================


@bom_stock_router.get("/stock", response_model=List[StockSnapshotResponse])
def list_stock_snapshots(
    client_id: str = Query(..., description="Client ID"),
    snapshot_date: Optional[date] = None,
    skip: int = 0,
    limit: int = DEFAULT_PAGE_SIZE,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get stock snapshots for a client."""
    verify_client_access(current_user, client_id, db)
    return stock.get_stock_snapshots(db, client_id, skip, limit, snapshot_date)


@bom_stock_router.post("/stock", response_model=StockSnapshotResponse, status_code=status.HTTP_201_CREATED)
def create_stock_snapshot(
    snapshot: StockSnapshotCreate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new stock snapshot."""
    verify_client_access(current_user, client_id, db)
    return stock.create_stock_snapshot(
        db,
        client_id,
        snapshot.snapshot_date,
        snapshot.item_code,
        snapshot.on_hand_quantity,
        snapshot.allocated_quantity,
        snapshot.on_order_quantity,
        snapshot.item_description,
        snapshot.unit_of_measure,
        snapshot.location,
        snapshot.notes,
    )


@bom_stock_router.get("/stock/item/{item_code}/latest", response_model=StockSnapshotResponse, responses={404: {"description": "No stock snapshot found for this item"}})
def get_latest_stock_for_item(
    item_code: str,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the most recent stock snapshot for an item."""
    verify_client_access(current_user, client_id, db)
    snapshot = stock.get_latest_stock(db, client_id, item_code)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Stock snapshot not found")
    return snapshot


@bom_stock_router.get("/stock/item/{item_code}/available", response_model=AvailableStockResponse)
def get_available_stock_for_item(
    item_code: str,
    client_id: str = Query(..., description="Client ID"),
    as_of_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get available stock quantity for an item."""
    verify_client_access(current_user, client_id, db)
    available = stock.get_available_stock(db, client_id, item_code, as_of_date)
    return {"item_code": item_code, "available_quantity": available, "as_of_date": as_of_date}


@bom_stock_router.get("/stock/shortages", response_model=List[StockSnapshotResponse])
def get_shortage_items(
    client_id: str = Query(..., description="Client ID"),
    snapshot_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get items with shortage (zero or negative available quantity)."""
    verify_client_access(current_user, client_id, db)
    return stock.get_shortage_items(db, client_id, snapshot_date)


@bom_stock_router.get("/stock/{snapshot_id}", response_model=StockSnapshotResponse, responses={404: {"description": "Stock snapshot not found"}})
def get_stock_snapshot(
    snapshot_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific stock snapshot."""
    verify_client_access(current_user, client_id, db)
    snapshot = stock.get_stock_snapshot(db, client_id, snapshot_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Stock snapshot not found")
    return snapshot


@bom_stock_router.put("/stock/{snapshot_id}", response_model=StockSnapshotResponse, responses={404: {"description": "Stock snapshot not found"}})
def update_stock_snapshot(
    snapshot_id: int,
    update: StockSnapshotUpdate,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a stock snapshot."""
    verify_client_access(current_user, client_id, db)
    snapshot = stock.update_stock_snapshot(db, client_id, snapshot_id, **update.model_dump(exclude_unset=True))
    if not snapshot:
        raise HTTPException(status_code=404, detail="Stock snapshot not found")
    return snapshot


@bom_stock_router.delete("/stock/{snapshot_id}", response_model=MessageResponse, responses={404: {"description": "Stock snapshot not found"}})
def delete_stock_snapshot(
    snapshot_id: int,
    client_id: str = Query(..., description="Client ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a stock snapshot."""
    verify_client_access(current_user, client_id, db)
    if not stock.delete_stock_snapshot(db, client_id, snapshot_id):
        raise HTTPException(status_code=404, detail="Stock snapshot not found")
    return {"message": "Stock snapshot deleted"}
