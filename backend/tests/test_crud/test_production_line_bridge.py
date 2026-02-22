"""
Tests for ProductionLine <-> CapacityProductionLine bridge CRUD operations.
Uses real database sessions -- no mocks for DB layer.
"""

import pytest

from backend.tests.fixtures.factories import TestDataFactory
from backend.schemas.production_line import ProductionLine
from backend.schemas.capacity.production_lines import CapacityProductionLine
from backend.schemas.work_order import WorkOrder
from backend.crud.production_line import (
    create_production_line,
    link_to_capacity_line,
    unlink_from_capacity_line,
    auto_sync_lines,
    get_unlinked_lines,
)
from backend.models.production_line import ProductionLineCreate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _seed_client(db, client_id="BRIDGE-C1"):
    """Create the minimal client row needed for FK constraint."""
    client = TestDataFactory.create_client(
        db, client_id=client_id, client_name="Bridge Test Client"
    )
    db.commit()
    return client


def _make_create(client_id, line_code, line_name, **kwargs):
    """Shorthand for building a ProductionLineCreate."""
    return ProductionLineCreate(
        client_id=client_id,
        line_code=line_code,
        line_name=line_name,
        **kwargs,
    )


def _create_capacity_line(db, client_id, line_code, line_name="Cap Line", **kwargs):
    """Create a CapacityProductionLine directly in the DB."""
    cap_line = CapacityProductionLine(
        client_id=client_id,
        line_code=line_code,
        line_name=line_name,
        department=kwargs.get("department"),
        is_active=kwargs.get("is_active", True),
    )
    db.add(cap_line)
    db.commit()
    db.refresh(cap_line)
    return cap_line


# ============================================================================
# TestLinkToCapacityLine
# ============================================================================
class TestLinkToCapacityLine:
    """Tests for link_to_capacity_line function."""

    def test_link_success(self, transactional_db):
        """Link an operational line to a capacity line."""
        db = transactional_db
        _seed_client(db, "BRG-L1")

        ops = create_production_line(
            db, _make_create("BRG-L1", "SEW-01", "Sewing Line 1")
        )
        cap = _create_capacity_line(db, "BRG-L1", "SEW-01", "Cap Sewing 1")

        result = link_to_capacity_line(db, ops.line_id, cap.id)
        assert result is not None
        assert result.capacity_line_id == cap.id

    def test_link_nonexistent_ops_line(self, transactional_db):
        """Linking a nonexistent operational line returns None."""
        db = transactional_db
        _seed_client(db, "BRG-L2")
        cap = _create_capacity_line(db, "BRG-L2", "SEW-01")

        result = link_to_capacity_line(db, 999999, cap.id)
        assert result is None

    def test_link_nonexistent_capacity_line(self, transactional_db):
        """Linking to a nonexistent capacity line raises ValueError."""
        db = transactional_db
        _seed_client(db, "BRG-L3")
        ops = create_production_line(
            db, _make_create("BRG-L3", "SEW-01", "Sewing Line 1")
        )

        with pytest.raises(ValueError, match="does not exist"):
            link_to_capacity_line(db, ops.line_id, 999999)

    def test_link_replaces_previous(self, transactional_db):
        """Linking overwrites a previous capacity link."""
        db = transactional_db
        _seed_client(db, "BRG-L4")

        ops = create_production_line(
            db, _make_create("BRG-L4", "SEW-01", "Sewing 1")
        )
        cap_a = _create_capacity_line(db, "BRG-L4", "CAP-A", "Cap A")
        cap_b = _create_capacity_line(db, "BRG-L4", "CAP-B", "Cap B")

        link_to_capacity_line(db, ops.line_id, cap_a.id)
        assert ops.capacity_line_id == cap_a.id

        result = link_to_capacity_line(db, ops.line_id, cap_b.id)
        assert result.capacity_line_id == cap_b.id


# ============================================================================
# TestUnlinkFromCapacityLine
# ============================================================================
class TestUnlinkFromCapacityLine:
    """Tests for unlink_from_capacity_line function."""

    def test_unlink_success(self, transactional_db):
        """Unlink removes the capacity_line_id."""
        db = transactional_db
        _seed_client(db, "BRG-U1")

        ops = create_production_line(
            db, _make_create("BRG-U1", "SEW-01", "Sewing Line 1")
        )
        cap = _create_capacity_line(db, "BRG-U1", "SEW-01")

        link_to_capacity_line(db, ops.line_id, cap.id)
        assert ops.capacity_line_id == cap.id

        result = unlink_from_capacity_line(db, ops.line_id)
        assert result is not None
        assert result.capacity_line_id is None

    def test_unlink_already_unlinked(self, transactional_db):
        """Unlinking an already-unlinked line still succeeds (idempotent)."""
        db = transactional_db
        _seed_client(db, "BRG-U2")

        ops = create_production_line(
            db, _make_create("BRG-U2", "SEW-01", "Sewing Line 1")
        )
        assert ops.capacity_line_id is None

        result = unlink_from_capacity_line(db, ops.line_id)
        assert result is not None
        assert result.capacity_line_id is None

    def test_unlink_nonexistent_returns_none(self, transactional_db):
        """Unlinking a nonexistent line returns None."""
        result = unlink_from_capacity_line(transactional_db, 999999)
        assert result is None


# ============================================================================
# TestAutoSyncLines
# ============================================================================
class TestAutoSyncLines:
    """Tests for auto_sync_lines function."""

    def test_sync_matches_by_line_code(self, transactional_db):
        """Auto-sync matches 3 operational lines to 3 capacity lines by code."""
        db = transactional_db
        _seed_client(db, "BRG-S1")

        codes = ["SEW-01", "CUT-01", "INS-01"]
        for code in codes:
            create_production_line(
                db, _make_create("BRG-S1", code, f"Ops {code}")
            )
            _create_capacity_line(db, "BRG-S1", code, f"Cap {code}")

        result = auto_sync_lines(db, "BRG-S1")
        assert len(result["matched"]) == 3
        assert len(result["unmatched"]) == 0

        # Verify all matched pairs
        matched_codes = {m["line_code"] for m in result["matched"]}
        assert matched_codes == set(codes)

    def test_sync_unmatched_stays_unlinked(self, transactional_db):
        """Operational line with no matching capacity code stays unmatched."""
        db = transactional_db
        _seed_client(db, "BRG-S2")

        # 2 matching + 1 unmatched operational line
        for code in ["SEW-01", "CUT-01"]:
            create_production_line(
                db, _make_create("BRG-S2", code, f"Ops {code}")
            )
            _create_capacity_line(db, "BRG-S2", code, f"Cap {code}")

        create_production_line(
            db, _make_create("BRG-S2", "PKG-01", "Packaging (no cap match)")
        )

        result = auto_sync_lines(db, "BRG-S2")
        assert len(result["matched"]) == 2
        assert len(result["unmatched"]) == 1
        assert result["unmatched"][0]["line_code"] == "PKG-01"

    def test_sync_skips_already_linked(self, transactional_db):
        """Already-linked lines are not re-synced."""
        db = transactional_db
        _seed_client(db, "BRG-S3")

        ops = create_production_line(
            db, _make_create("BRG-S3", "SEW-01", "Sewing 1")
        )
        cap = _create_capacity_line(db, "BRG-S3", "SEW-01", "Cap Sewing 1")

        # Manually link first
        link_to_capacity_line(db, ops.line_id, cap.id)

        # Now sync should find nothing to match (already linked)
        result = auto_sync_lines(db, "BRG-S3")
        assert len(result["matched"]) == 0
        assert len(result["unmatched"]) == 0

    def test_sync_empty_client(self, transactional_db):
        """Auto-sync on empty client returns empty result."""
        db = transactional_db
        _seed_client(db, "BRG-S4")

        result = auto_sync_lines(db, "BRG-S4")
        assert result["matched"] == []
        assert result["unmatched"] == []

    def test_sync_multi_tenant_isolation(self, transactional_db):
        """Auto-sync only matches within the same client_id."""
        db = transactional_db
        _seed_client(db, "BRG-MT-A")
        _seed_client(db, "BRG-MT-B")

        # Client A has operational line SEW-01
        create_production_line(
            db, _make_create("BRG-MT-A", "SEW-01", "Ops Sewing A")
        )
        # Client B has the capacity line SEW-01
        _create_capacity_line(db, "BRG-MT-B", "SEW-01", "Cap Sewing B")

        # Sync for client A should NOT match (capacity line is in client B)
        result = auto_sync_lines(db, "BRG-MT-A")
        assert len(result["matched"]) == 0
        assert len(result["unmatched"]) == 1

    def test_sync_skips_inactive_ops_lines(self, transactional_db):
        """Inactive operational lines are not included in sync."""
        db = transactional_db
        _seed_client(db, "BRG-S5")

        ops = create_production_line(
            db, _make_create("BRG-S5", "SEW-01", "Sewing 1")
        )
        _create_capacity_line(db, "BRG-S5", "SEW-01", "Cap Sewing 1")

        # Deactivate the operational line
        ops.is_active = False
        db.commit()

        result = auto_sync_lines(db, "BRG-S5")
        assert len(result["matched"]) == 0
        assert len(result["unmatched"]) == 0

    def test_sync_skips_inactive_capacity_lines(self, transactional_db):
        """Inactive capacity lines are not matched."""
        db = transactional_db
        _seed_client(db, "BRG-S6")

        create_production_line(
            db, _make_create("BRG-S6", "SEW-01", "Sewing 1")
        )
        cap = _create_capacity_line(
            db, "BRG-S6", "SEW-01", "Cap Sewing 1", is_active=False
        )

        result = auto_sync_lines(db, "BRG-S6")
        assert len(result["matched"]) == 0
        assert len(result["unmatched"]) == 1


# ============================================================================
# TestGetUnlinkedLines
# ============================================================================
class TestGetUnlinkedLines:
    """Tests for get_unlinked_lines function."""

    def test_all_unlinked(self, transactional_db):
        """All lines without capacity link are returned."""
        db = transactional_db
        _seed_client(db, "BRG-UL1")

        for code in ["SEW-01", "CUT-01", "INS-01"]:
            create_production_line(
                db, _make_create("BRG-UL1", code, f"Line {code}")
            )

        unlinked = get_unlinked_lines(db, "BRG-UL1")
        assert len(unlinked) == 3

    def test_linked_excluded(self, transactional_db):
        """Linked lines are excluded from unlinked query."""
        db = transactional_db
        _seed_client(db, "BRG-UL2")

        ops1 = create_production_line(
            db, _make_create("BRG-UL2", "SEW-01", "Sewing 1")
        )
        create_production_line(
            db, _make_create("BRG-UL2", "CUT-01", "Cutting 1")
        )
        cap = _create_capacity_line(db, "BRG-UL2", "SEW-01")

        link_to_capacity_line(db, ops1.line_id, cap.id)

        unlinked = get_unlinked_lines(db, "BRG-UL2")
        assert len(unlinked) == 1
        assert unlinked[0].line_code == "CUT-01"

    def test_unlinked_ordered_by_code(self, transactional_db):
        """Unlinked lines are returned ordered by line_code."""
        db = transactional_db
        _seed_client(db, "BRG-UL3")

        for code in ["ZZZ-01", "AAA-01", "MID-01"]:
            create_production_line(
                db, _make_create("BRG-UL3", code, f"Line {code}")
            )

        unlinked = get_unlinked_lines(db, "BRG-UL3")
        codes = [line.line_code for line in unlinked]
        assert codes == sorted(codes)

    def test_unlinked_excludes_inactive(self, transactional_db):
        """Inactive lines are excluded from unlinked query."""
        db = transactional_db
        _seed_client(db, "BRG-UL4")

        ops = create_production_line(
            db, _make_create("BRG-UL4", "SEW-01", "Sewing 1")
        )
        ops.is_active = False
        db.commit()

        unlinked = get_unlinked_lines(db, "BRG-UL4")
        assert len(unlinked) == 0

    def test_unlinked_empty_client(self, transactional_db):
        """Empty client returns empty unlinked list."""
        db = transactional_db
        _seed_client(db, "BRG-UL5")

        unlinked = get_unlinked_lines(db, "BRG-UL5")
        assert unlinked == []


# ============================================================================
# TestWorkOrderCapacityBridge
# ============================================================================
class TestWorkOrderCapacityBridge:
    """Test WorkOrder.capacity_order_id and origin fields."""

    def test_work_order_default_origin(self, transactional_db):
        """Work order origin defaults to AD_HOC."""
        db = transactional_db
        _seed_client(db, "WO-BRG-1")

        wo = WorkOrder(
            work_order_id="WO-ADHOC-001",
            client_id="WO-BRG-1",
            style_model="STYLE-001",
            planned_quantity=500,
            status="RECEIVED",
        )
        db.add(wo)
        db.commit()
        db.refresh(wo)

        assert wo.origin == "AD_HOC"
        assert wo.capacity_order_id is None

    def test_work_order_with_capacity_order_id(self, transactional_db):
        """Work order can be created with capacity_order_id (planned)."""
        db = transactional_db
        from datetime import date as date_type
        from backend.schemas.capacity.orders import CapacityOrder

        _seed_client(db, "WO-BRG-2")

        # Create a capacity order
        cap_order = CapacityOrder(
            client_id="WO-BRG-2",
            order_number="CO-001",
            style_model="STYLE-001",
            order_quantity=1000,
            required_date=date_type(2026, 6, 1),
        )
        db.add(cap_order)
        db.commit()
        db.refresh(cap_order)

        # Create work order linked to capacity order
        wo = WorkOrder(
            work_order_id="WO-PLANNED-001",
            client_id="WO-BRG-2",
            style_model="STYLE-001",
            planned_quantity=1000,
            status="RECEIVED",
            capacity_order_id=cap_order.id,
            origin="PLANNED",
        )
        db.add(wo)
        db.commit()
        db.refresh(wo)

        assert wo.capacity_order_id == cap_order.id
        assert wo.origin == "PLANNED"

    def test_work_order_ad_hoc_no_capacity_order(self, transactional_db):
        """Ad-hoc work order has NULL capacity_order_id."""
        db = transactional_db
        _seed_client(db, "WO-BRG-3")

        wo = WorkOrder(
            work_order_id="WO-TEST-RUN-001",
            client_id="WO-BRG-3",
            style_model="PROVE-IN-STYLE",
            planned_quantity=50,
            status="RECEIVED",
            origin="AD_HOC",
        )
        db.add(wo)
        db.commit()
        db.refresh(wo)

        assert wo.capacity_order_id is None
        assert wo.origin == "AD_HOC"
