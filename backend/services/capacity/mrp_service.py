"""
MRP / Component Check Service
Phase B.2: Backend Services for Capacity Planning

Provides Mini-MRP functionality for component availability checking.
Explodes BOMs, aggregates requirements, compares to stock, identifies shortages.
"""

import logging
from decimal import Decimal
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func

logger = logging.getLogger(__name__)

from backend.schemas.capacity.component_check import CapacityComponentCheck, ComponentStatus
from backend.schemas.capacity.stock import CapacityStockSnapshot
from backend.schemas.capacity.orders import CapacityOrder
from backend.services.capacity.bom_service import BOMService, BOMExplosionResult
from backend.events.bus import event_bus
from backend.events.domain_events import ComponentShortageDetected


@dataclass
class ComponentCheckResult:
    """Result of component check for a single component."""

    component_item_code: str
    component_description: Optional[str]
    required_quantity: Decimal
    available_quantity: Decimal
    shortage_quantity: Decimal
    status: ComponentStatus
    affected_orders: List[str]


@dataclass
class MRPRunResult:
    """Complete MRP run result."""

    run_date: date
    total_components_checked: int
    components_ok: int
    components_short: int
    components: List[ComponentCheckResult]
    orders_affected: int


class MRPService:
    """
    Service for MRP / Component Check operations.

    Implements Mini-MRP functionality:
    1. Get orders to check
    2. Explode BOMs for each order
    3. Aggregate component requirements
    4. Compare to stock
    5. Calculate shortages
    6. Store results
    7. Emit events for shortages

    Multi-tenant isolation via client_id on all operations.
    """

    def __init__(self, db: Session):
        """
        Initialize MRP service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.bom_service = BOMService(db)

    def run_component_check(self, client_id: str, order_ids: Optional[List[int]] = None) -> MRPRunResult:
        """
        Run component check (Mini-MRP) for orders.

        Steps:
        1. Get orders to check (all pending or specific IDs)
        2. Explode BOMs for each order
        3. Aggregate component requirements
        4. Compare to stock
        5. Calculate shortages
        6. Store results
        7. Emit events for shortages

        Args:
            client_id: Client ID for tenant isolation
            order_ids: Optional list of specific order IDs to check

        Returns:
            MRPRunResult with all component statuses
        """
        run_date = date.today()

        # Get orders to process
        query = self.db.query(CapacityOrder).filter(CapacityOrder.client_id == client_id)
        if order_ids:
            query = query.filter(CapacityOrder.id.in_(order_ids))

        orders = query.all()

        if not orders:
            return MRPRunResult(
                run_date=run_date,
                total_components_checked=0,
                components_ok=0,
                components_short=0,
                components=[],
                orders_affected=0,
            )

        # Explode BOMs for all orders
        explosion_results: List[BOMExplosionResult] = []
        order_by_style: Dict[str, List[str]] = {}  # Track which orders use which style

        for order in orders:
            try:
                result = self.bom_service.explode_bom(
                    client_id, order.style_code, Decimal(str(order.order_quantity)), emit_event=False
                )
                explosion_results.append(result)

                if order.style_code not in order_by_style:
                    order_by_style[order.style_code] = []
                order_by_style[order.style_code].append(order.order_number)
            except (SQLAlchemyError, ValueError, KeyError) as e:
                # Skip orders without valid BOMs
                logger.exception("BOM explosion failed for order %s", order.order_number)
                continue

        # Aggregate requirements
        aggregated = self.bom_service.aggregate_component_requirements(explosion_results)

        # Get current stock
        stock_by_item = self._get_latest_stock(client_id)

        # Check each component
        components_checked: List[ComponentCheckResult] = []
        orders_affected: set = set()

        for item_code, required_qty in aggregated.items():
            available_qty = stock_by_item.get(item_code, Decimal("0"))
            shortage_qty = max(Decimal("0"), required_qty - available_qty)

            if shortage_qty > 0:
                status = ComponentStatus.SHORTAGE
                # Find affected orders
                affected = self._find_affected_orders(item_code, explosion_results, order_by_style)
                orders_affected.update(affected)

                # Emit event for each affected order
                for order_num in affected:
                    event = ComponentShortageDetected(
                        aggregate_id=f"component_check_{client_id}_{run_date}",
                        client_id=client_id,
                        order_id=order_num,
                        component_item_code=item_code,
                        shortage_quantity=shortage_qty,
                        required_quantity=required_qty,
                        available_quantity=available_qty,
                        affected_orders_count=len(affected),
                    )
                    event_bus.collect(event)
            elif available_qty < required_qty * Decimal("1.1"):
                # Less than 10% buffer - mark as partial
                status = ComponentStatus.PARTIAL
                affected = []
            else:
                status = ComponentStatus.OK
                affected = []

            components_checked.append(
                ComponentCheckResult(
                    component_item_code=item_code,
                    component_description=None,
                    required_quantity=required_qty,
                    available_quantity=available_qty,
                    shortage_quantity=shortage_qty,
                    status=status,
                    affected_orders=affected,
                )
            )

            # Store result in database
            self._store_check_result(
                client_id, run_date, item_code, required_qty, available_qty, shortage_qty, status, orders
            )

        components_ok = sum(1 for c in components_checked if c.status == ComponentStatus.OK)
        components_short = sum(1 for c in components_checked if c.status == ComponentStatus.SHORTAGE)

        return MRPRunResult(
            run_date=run_date,
            total_components_checked=len(components_checked),
            components_ok=components_ok,
            components_short=components_short,
            components=components_checked,
            orders_affected=len(orders_affected),
        )

    def get_component_check_history(
        self,
        client_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        status_filter: Optional[ComponentStatus] = None,
    ) -> List[CapacityComponentCheck]:
        """
        Get historical component check results.

        Args:
            client_id: Client ID for tenant isolation
            start_date: Optional start date filter
            end_date: Optional end date filter
            status_filter: Optional status filter

        Returns:
            List of CapacityComponentCheck records
        """
        query = self.db.query(CapacityComponentCheck).filter(CapacityComponentCheck.client_id == client_id)

        if start_date:
            query = query.filter(CapacityComponentCheck.run_date >= start_date)
        if end_date:
            query = query.filter(CapacityComponentCheck.run_date <= end_date)
        if status_filter:
            query = query.filter(CapacityComponentCheck.status == status_filter)

        return query.order_by(CapacityComponentCheck.run_date.desc()).all()

    def get_shortages_by_order(self, client_id: str, order_number: str) -> List[ComponentCheckResult]:
        """
        Get component shortages for a specific order.

        Args:
            client_id: Client ID for tenant isolation
            order_number: Order number to check

        Returns:
            List of ComponentCheckResult for components with shortages
        """
        checks = (
            self.db.query(CapacityComponentCheck)
            .filter(
                CapacityComponentCheck.client_id == client_id,
                CapacityComponentCheck.order_number == order_number,
                CapacityComponentCheck.status == ComponentStatus.SHORTAGE,
            )
            .all()
        )

        return [
            ComponentCheckResult(
                component_item_code=c.component_item_code,
                component_description=c.component_description,
                required_quantity=Decimal(str(c.required_quantity)),
                available_quantity=Decimal(str(c.available_quantity)),
                shortage_quantity=Decimal(str(c.shortage_quantity)),
                status=c.status,
                affected_orders=[c.order_number],
            )
            for c in checks
        ]

    def _get_latest_stock(self, client_id: str) -> Dict[str, Decimal]:
        """
        Get latest stock quantities by item.

        Args:
            client_id: Client ID for tenant isolation

        Returns:
            Dict of item_code -> available_quantity
        """
        # Subquery to get max snapshot date per item
        subq = (
            self.db.query(
                CapacityStockSnapshot.item_code, func.max(CapacityStockSnapshot.snapshot_date).label("max_date")
            )
            .filter(CapacityStockSnapshot.client_id == client_id)
            .group_by(CapacityStockSnapshot.item_code)
            .subquery()
        )

        snapshots = (
            self.db.query(CapacityStockSnapshot)
            .join(
                subq,
                (CapacityStockSnapshot.item_code == subq.c.item_code)
                & (CapacityStockSnapshot.snapshot_date == subq.c.max_date),
            )
            .filter(CapacityStockSnapshot.client_id == client_id)
            .all()
        )

        return {s.item_code: Decimal(str(s.available_quantity or 0)) for s in snapshots}

    def _find_affected_orders(
        self, item_code: str, explosion_results: List[BOMExplosionResult], order_by_style: Dict[str, List[str]]
    ) -> List[str]:
        """
        Find orders affected by a component shortage.

        Args:
            item_code: Component item code
            explosion_results: List of BOM explosion results
            order_by_style: Dict of style_code -> order_numbers

        Returns:
            List of affected order numbers
        """
        affected = []
        for result in explosion_results:
            for comp in result.components:
                if comp.component_item_code == item_code:
                    affected.extend(order_by_style.get(result.parent_item_code, []))
        return list(set(affected))

    def _store_check_result(
        self,
        client_id: str,
        run_date: date,
        item_code: str,
        required: Decimal,
        available: Decimal,
        shortage: Decimal,
        status: ComponentStatus,
        orders: List[CapacityOrder],
    ) -> None:
        """
        Store component check result in database.

        Args:
            client_id: Client ID for tenant isolation
            run_date: Date of the check run
            item_code: Component item code
            required: Required quantity
            available: Available quantity
            shortage: Shortage quantity
            status: Component status
            orders: List of orders
        """
        for order in orders:
            check = CapacityComponentCheck(
                client_id=client_id,
                run_date=run_date,
                order_id=order.id,
                order_number=order.order_number,
                component_item_code=item_code,
                required_quantity=required,
                available_quantity=available,
                shortage_quantity=shortage,
                status=status,
            )
            self.db.add(check)

        self.db.commit()
