"""
BOM Explosion Service
Phase B.2: Backend Services for Capacity Planning

Provides BOM (Bill of Materials) explosion operations for capacity planning.
Single-level explosion per specification (no subassemblies).
"""

from decimal import Decimal
from typing import List, Dict, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session

from backend.schemas.capacity.bom import CapacityBOMHeader, CapacityBOMDetail
from backend.exceptions.domain_exceptions import BOMExplosionError
from backend.events.bus import event_bus
from backend.events.domain_events import BOMExploded


@dataclass
class BOMComponent:
    """Result of BOM explosion for a single component."""

    component_item_code: str
    component_description: Optional[str]
    gross_required: Decimal
    net_required: Decimal  # After waste
    waste_percentage: Decimal
    unit_of_measure: str
    component_type: Optional[str]


@dataclass
class BOMExplosionResult:
    """Complete BOM explosion result."""

    parent_item_code: str
    quantity_requested: Decimal
    components: List[BOMComponent]
    total_components: int
    explosion_depth: int = 1  # Single-level per spec


class BOMService:
    """
    Service for BOM explosion operations.

    Provides single-level BOM explosion for capacity planning.
    Multi-tenant isolation via client_id on all operations.
    """

    def __init__(self, db: Session):
        """
        Initialize BOM service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def explode_bom(
        self, client_id: str, parent_item_code: str, quantity: Decimal, emit_event: bool = True
    ) -> BOMExplosionResult:
        """
        Explode a BOM to get required components.

        Single-level explosion (spec requirement: no subassemblies).
        Applies waste percentage: net_required = qty * (1 + waste_pct/100)

        Args:
            client_id: Client ID for tenant isolation
            parent_item_code: Parent item to explode
            quantity: Quantity of parent being produced
            emit_event: Whether to emit BOMExploded event

        Returns:
            BOMExplosionResult with all components

        Raises:
            BOMExplosionError: If BOM not found or explosion fails
        """
        # Get BOM header
        header = (
            self.db.query(CapacityBOMHeader)
            .filter(
                CapacityBOMHeader.client_id == client_id,
                CapacityBOMHeader.parent_item_code == parent_item_code,
                CapacityBOMHeader.is_active == True,
            )
            .first()
        )

        if not header:
            raise BOMExplosionError(
                message=f"No active BOM found for item '{parent_item_code}'", parent_item=parent_item_code
            )

        # Get all components
        details = (
            self.db.query(CapacityBOMDetail)
            .filter(CapacityBOMDetail.header_id == header.id, CapacityBOMDetail.client_id == client_id)
            .all()
        )

        if not details:
            raise BOMExplosionError(
                message=f"BOM for '{parent_item_code}' has no components", parent_item=parent_item_code
            )

        # Calculate requirements for each component
        components = []
        for detail in details:
            gross_required = quantity * Decimal(str(detail.quantity_per))
            waste_pct = Decimal(str(detail.waste_percentage or 0))
            net_required = gross_required * (1 + waste_pct / 100)

            components.append(
                BOMComponent(
                    component_item_code=detail.component_item_code,
                    component_description=detail.component_description,
                    gross_required=gross_required,
                    net_required=net_required,
                    waste_percentage=waste_pct,
                    unit_of_measure=detail.unit_of_measure,
                    component_type=detail.component_type,
                )
            )

        result = BOMExplosionResult(
            parent_item_code=parent_item_code,
            quantity_requested=quantity,
            components=components,
            total_components=len(components),
            explosion_depth=1,
        )

        # Emit event
        if emit_event:
            event = BOMExploded(
                aggregate_id=f"bom_{header.id}",
                client_id=client_id,
                parent_item_code=parent_item_code,
                quantity_requested=quantity,
                components_count=len(components),
                explosion_depth=1,
            )
            event_bus.collect(event)

        return result

    def explode_multiple_orders(
        self, client_id: str, orders: List[Dict]  # [{"style_code": "X", "quantity": 100}, ...]
    ) -> Dict[str, BOMExplosionResult]:
        """
        Explode BOMs for multiple orders.

        Args:
            client_id: Client ID for tenant isolation
            orders: List of orders with style_code and quantity

        Returns:
            Dict of style_code -> BOMExplosionResult
        """
        results = {}
        for order in orders:
            style_code = order.get("style_code")
            quantity = Decimal(str(order.get("quantity", 0)))

            try:
                result = self.explode_bom(client_id, style_code, quantity, emit_event=False)
                results[style_code] = result
            except BOMExplosionError:
                # Skip orders without BOMs
                continue

        return results

    def aggregate_component_requirements(self, explosion_results: List[BOMExplosionResult]) -> Dict[str, Decimal]:
        """
        Aggregate component requirements across multiple explosions.

        Args:
            explosion_results: List of BOM explosion results

        Returns:
            Dict of component_item_code -> total_net_required
        """
        aggregated: Dict[str, Decimal] = {}
        for result in explosion_results:
            for comp in result.components:
                if comp.component_item_code in aggregated:
                    aggregated[comp.component_item_code] += comp.net_required
                else:
                    aggregated[comp.component_item_code] = comp.net_required

        return aggregated

    def get_bom_structure(self, client_id: str, parent_item_code: str) -> Optional[Dict]:
        """
        Get BOM structure without explosion.

        Args:
            client_id: Client ID for tenant isolation
            parent_item_code: Parent item code

        Returns:
            Dict with BOM structure or None if not found
        """
        header = (
            self.db.query(CapacityBOMHeader)
            .filter(
                CapacityBOMHeader.client_id == client_id,
                CapacityBOMHeader.parent_item_code == parent_item_code,
                CapacityBOMHeader.is_active == True,
            )
            .first()
        )

        if not header:
            return None

        details = (
            self.db.query(CapacityBOMDetail)
            .filter(CapacityBOMDetail.header_id == header.id, CapacityBOMDetail.client_id == client_id)
            .all()
        )

        return {
            "id": header.id,
            "parent_item_code": header.parent_item_code,
            "parent_item_description": header.parent_item_description,
            "style_code": header.style_code,
            "revision": header.revision,
            "is_active": header.is_active,
            "components": [
                {
                    "component_item_code": d.component_item_code,
                    "component_description": d.component_description,
                    "quantity_per": float(d.quantity_per),
                    "waste_percentage": float(d.waste_percentage or 0),
                    "unit_of_measure": d.unit_of_measure,
                    "component_type": d.component_type,
                }
                for d in details
            ],
        }
