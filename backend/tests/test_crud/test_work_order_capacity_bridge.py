"""
Tests for Work Order <-> Capacity Order cross-reference CRUD operations (Task 3.1).
Uses real database sessions -- no mocks for DB layer.
"""

import pytest
from datetime import date, datetime, timezone

from backend.tests.fixtures.factories import TestDataFactory
from backend.orm.work_order import WorkOrder
from backend.orm.capacity.orders import CapacityOrder, OrderStatus, OrderPriority
from backend.orm.user import User, UserRole
from backend.crud.work_order import (
    get_work_orders_by_capacity_order,
    get_capacity_order_for_work_order,
    link_work_order_to_capacity,
    unlink_work_order_from_capacity,
)
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
CLIENT_ID = "WO-CAP-C1"


def _seed_client(db, client_id=CLIENT_ID):
    """Create the minimal client row needed for FK constraint."""
    client = TestDataFactory.create_client(
        db, client_id=client_id, client_name="WO-Cap Bridge Test Client"
    )
    db.commit()
    return client


def _create_admin_user():
    """Create an in-memory admin user (not persisted, used for auth bypass)."""
    return User(
        user_id="admin-bridge-test",
        username="admin_bridge",
        email="admin_bridge@test.com",
        role=UserRole.ADMIN,
        client_id_assigned=None,
        is_active=True,
    )


def _create_capacity_order(db, client_id=CLIENT_ID, order_number="CO-001", **kwargs):
    """Create a CapacityOrder directly in the DB."""
    cap_order = CapacityOrder(
        client_id=client_id,
        order_number=order_number,
        style_model=kwargs.get("style_model", "STYLE-001"),
        order_quantity=kwargs.get("order_quantity", 1000),
        required_date=kwargs.get("required_date", date(2026, 6, 1)),
        priority=kwargs.get("priority", OrderPriority.NORMAL),
        status=kwargs.get("status", OrderStatus.CONFIRMED),
    )
    db.add(cap_order)
    db.commit()
    db.refresh(cap_order)
    return cap_order


def _create_work_order(db, client_id=CLIENT_ID, work_order_id="WO-TEST-001", **kwargs):
    """Create a WorkOrder directly in the DB."""
    wo = WorkOrder(
        work_order_id=work_order_id,
        client_id=client_id,
        style_model=kwargs.get("style_model", "STYLE-001"),
        planned_quantity=kwargs.get("planned_quantity", 500),
        actual_quantity=kwargs.get("actual_quantity", 0),
        status=kwargs.get("status", "RECEIVED"),
        capacity_order_id=kwargs.get("capacity_order_id"),
        origin=kwargs.get("origin", "AD_HOC"),
    )
    db.add(wo)
    db.commit()
    db.refresh(wo)
    return wo


# ============================================================================
# TestGetWorkOrdersByCapacityOrder
# ============================================================================
class TestGetWorkOrdersByCapacityOrder:
    """Tests for get_work_orders_by_capacity_order function."""

    def test_returns_linked_work_orders(self, transactional_db):
        """Returns work orders that are linked to a given capacity order."""
        db = transactional_db
        _seed_client(db)
        admin = _create_admin_user()

        cap_order = _create_capacity_order(db, order_number="CO-LINK-001")
        _create_work_order(
            db, work_order_id="WO-LINKED-001",
            capacity_order_id=cap_order.id, origin="PLANNED",
        )
        _create_work_order(
            db, work_order_id="WO-LINKED-002",
            capacity_order_id=cap_order.id, origin="PLANNED",
        )
        # Unlinked work order - should NOT be returned
        _create_work_order(db, work_order_id="WO-UNLINKED-001")

        results = get_work_orders_by_capacity_order(db, cap_order.id, admin)
        assert len(results) == 2
        wo_ids = {wo.work_order_id for wo in results}
        assert wo_ids == {"WO-LINKED-001", "WO-LINKED-002"}

    def test_returns_empty_for_no_linked_work_orders(self, transactional_db):
        """Returns empty list when no work orders are linked."""
        db = transactional_db
        _seed_client(db)
        admin = _create_admin_user()

        cap_order = _create_capacity_order(db, order_number="CO-EMPTY-001")
        _create_work_order(db, work_order_id="WO-ADHOC-001")

        results = get_work_orders_by_capacity_order(db, cap_order.id, admin)
        assert results == []


# ============================================================================
# TestGetCapacityOrderForWorkOrder
# ============================================================================
class TestGetCapacityOrderForWorkOrder:
    """Tests for get_capacity_order_for_work_order function."""

    def test_returns_capacity_order_when_linked(self, transactional_db):
        """Returns the capacity order for a linked work order."""
        db = transactional_db
        _seed_client(db)
        admin = _create_admin_user()

        cap_order = _create_capacity_order(db, order_number="CO-GET-001")
        _create_work_order(
            db, work_order_id="WO-GET-001",
            capacity_order_id=cap_order.id, origin="PLANNED",
        )

        result = get_capacity_order_for_work_order(db, "WO-GET-001", admin)
        assert result is not None
        assert result.id == cap_order.id
        assert result.order_number == "CO-GET-001"

    def test_returns_none_when_not_linked(self, transactional_db):
        """Returns None for an ad-hoc work order with no capacity link."""
        db = transactional_db
        _seed_client(db)
        admin = _create_admin_user()

        _create_work_order(db, work_order_id="WO-ADHOC-002")

        result = get_capacity_order_for_work_order(db, "WO-ADHOC-002", admin)
        assert result is None


# ============================================================================
# TestLinkWorkOrderToCapacity
# ============================================================================
class TestLinkWorkOrderToCapacity:
    """Tests for link_work_order_to_capacity function."""

    def test_link_success(self, transactional_db):
        """Successfully link a work order to a capacity order."""
        db = transactional_db
        _seed_client(db)
        admin = _create_admin_user()

        cap_order = _create_capacity_order(db, order_number="CO-LNK-001")
        _create_work_order(db, work_order_id="WO-LNK-001")

        result = link_work_order_to_capacity(db, "WO-LNK-001", cap_order.id, admin)
        assert result.capacity_order_id == cap_order.id
        assert result.origin == "PLANNED"

    def test_link_nonexistent_capacity_order_returns_404(self, transactional_db):
        """Linking to a nonexistent capacity order raises HTTPException 404."""
        db = transactional_db
        _seed_client(db)
        admin = _create_admin_user()

        _create_work_order(db, work_order_id="WO-LNK-002")

        with pytest.raises(HTTPException) as exc_info:
            link_work_order_to_capacity(db, "WO-LNK-002", 999999, admin)
        assert exc_info.value.status_code == 404
        assert "Capacity order not found" in exc_info.value.detail

    def test_link_nonexistent_work_order_returns_404(self, transactional_db):
        """Linking a nonexistent work order raises HTTPException 404."""
        db = transactional_db
        _seed_client(db)
        admin = _create_admin_user()

        cap_order = _create_capacity_order(db, order_number="CO-LNK-003")

        with pytest.raises(HTTPException) as exc_info:
            link_work_order_to_capacity(db, "WO-NONEXISTENT", cap_order.id, admin)
        assert exc_info.value.status_code == 404


# ============================================================================
# TestUnlinkWorkOrderFromCapacity
# ============================================================================
class TestUnlinkWorkOrderFromCapacity:
    """Tests for unlink_work_order_from_capacity function."""

    def test_unlink_success(self, transactional_db):
        """Successfully unlink a work order from its capacity order."""
        db = transactional_db
        _seed_client(db)
        admin = _create_admin_user()

        cap_order = _create_capacity_order(db, order_number="CO-UNL-001")
        _create_work_order(
            db, work_order_id="WO-UNL-001",
            capacity_order_id=cap_order.id, origin="PLANNED",
        )

        result = unlink_work_order_from_capacity(db, "WO-UNL-001", admin)
        assert result.capacity_order_id is None
        assert result.origin == "AD_HOC"

    def test_unlink_nonexistent_work_order_returns_404(self, transactional_db):
        """Unlinking a nonexistent work order raises HTTPException 404."""
        db = transactional_db
        _seed_client(db)
        admin = _create_admin_user()

        with pytest.raises(HTTPException) as exc_info:
            unlink_work_order_from_capacity(db, "WO-NONEXISTENT", admin)
        assert exc_info.value.status_code == 404
