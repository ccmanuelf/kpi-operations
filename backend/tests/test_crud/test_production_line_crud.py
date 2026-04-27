"""
Tests for ProductionLine CRUD operations.
Uses real database sessions -- no mocks for DB layer.
"""

import pytest

from backend.tests.fixtures.factories import TestDataFactory
from backend.orm.production_line import ProductionLine
from backend.crud.production_line import (
    create_production_line,
    list_production_lines,
    get_production_line,
    get_production_line_tree,
    update_production_line,
    deactivate_production_line,
    count_active_lines,
)
from backend.schemas.production_line import ProductionLineCreate, ProductionLineUpdate


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _seed_client(db, client_id="PL-TEST-C1"):
    """Create the minimal client row needed for FK constraint."""
    client = TestDataFactory.create_client(db, client_id=client_id, client_name="PL Test Client")
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


# ============================================================================
# TestCreateProductionLine
# ============================================================================
class TestCreateProductionLine:
    """Tests for create_production_line function."""

    def test_create_basic(self, transactional_db):
        """Create a production line and verify all fields are set correctly."""
        db = transactional_db
        _seed_client(db, "PL-C1")

        data = _make_create("PL-C1", "SEW-01", "Sewing Line 1", department="SEWING")
        result = create_production_line(db, data)

        assert result.line_id is not None
        assert result.client_id == "PL-C1"
        assert result.line_code == "SEW-01"
        assert result.line_name == "Sewing Line 1"
        assert result.department == "SEWING"
        assert result.line_type == "DEDICATED"
        assert result.parent_line_id is None
        assert result.is_active is True
        assert result.created_at is not None

    def test_create_with_all_fields(self, transactional_db):
        """Create a production line with all optional fields."""
        db = transactional_db
        _seed_client(db, "PL-C2")

        data = _make_create(
            "PL-C2",
            "CUT-01",
            "Cutting Area",
            department="CUTTING",
            line_type="SECTION",
            max_operators=15,
        )
        result = create_production_line(db, data)

        assert result.line_type == "SECTION"
        assert result.max_operators == 15
        assert result.department == "CUTTING"

    def test_create_duplicate_raises(self, transactional_db):
        """Creating a duplicate (client_id, line_code) raises ValueError."""
        db = transactional_db
        _seed_client(db, "PL-C3")

        data = _make_create("PL-C3", "SEW-01", "Sewing Line 1")
        create_production_line(db, data)

        with pytest.raises(ValueError, match="already exists"):
            create_production_line(db, data)

    def test_create_same_code_different_client(self, transactional_db):
        """Same line_code is allowed for different clients."""
        db = transactional_db
        _seed_client(db, "PL-CA")
        _seed_client(db, "PL-CB")

        data_a = _make_create("PL-CA", "SEW-01", "Sewing Line 1")
        data_b = _make_create("PL-CB", "SEW-01", "Sewing Line 1")

        result_a = create_production_line(db, data_a)
        result_b = create_production_line(db, data_b)

        assert result_a.line_id != result_b.line_id
        assert result_a.client_id == "PL-CA"
        assert result_b.client_id == "PL-CB"

    def test_create_with_parent(self, transactional_db):
        """Create a child production line with parent_line_id set."""
        db = transactional_db
        _seed_client(db, "PL-C4")

        parent = create_production_line(db, _make_create("PL-C4", "SEW-AREA", "Sewing Area", line_type="SECTION"))
        child = create_production_line(
            db,
            _make_create(
                "PL-C4",
                "SEW-01",
                "Sewing Line 1",
                parent_line_id=parent.line_id,
            ),
        )

        assert child.parent_line_id == parent.line_id

    def test_soft_limit_warning_but_still_creates(self, transactional_db):
        """Creating line 11 succeeds but attaches a soft-limit warning."""
        db = transactional_db
        _seed_client(db, "PL-LIM")

        # Create 10 lines (at the limit)
        for i in range(10):
            create_production_line(db, _make_create("PL-LIM", f"LINE-{i:02d}", f"Line {i}"))

        assert count_active_lines(db, "PL-LIM") == 10

        # The 11th still succeeds with a warning
        result = create_production_line(db, _make_create("PL-LIM", "LINE-10", "Line 10"))
        assert result.line_id is not None
        assert result._limit_warning is not None
        assert "soft limit" in result._limit_warning

    def test_soft_limit_custom_max(self, transactional_db):
        """Custom max_lines parameter controls the soft limit threshold."""
        db = transactional_db
        _seed_client(db, "PL-LIM2")

        # Create 3 lines
        for i in range(3):
            create_production_line(db, _make_create("PL-LIM2", f"LINE-{i}", f"Line {i}"), max_lines=3)

        # 4th triggers warning with custom limit of 3
        result = create_production_line(db, _make_create("PL-LIM2", "LINE-3", "Line 3"), max_lines=3)
        assert result._limit_warning is not None


# ============================================================================
# TestListProductionLines
# ============================================================================
class TestListProductionLines:
    """Tests for list_production_lines function."""

    def test_list_returns_active_only(self, transactional_db):
        """list_production_lines excludes inactive lines by default."""
        db = transactional_db
        _seed_client(db, "PL-L1")

        for code in ["SEW-01", "SEW-02", "CUT-01"]:
            create_production_line(db, _make_create("PL-L1", code, f"Line {code}"))

        # Deactivate one
        lines = list_production_lines(db, "PL-L1")
        deactivate_production_line(db, lines[0].line_id)

        active = list_production_lines(db, "PL-L1")
        all_entries = list_production_lines(db, "PL-L1", include_inactive=True)

        assert len(active) == 2
        assert len(all_entries) == 3

    def test_list_ordered_by_code(self, transactional_db):
        """list_production_lines returns entries ordered by line_code."""
        db = transactional_db
        _seed_client(db, "PL-L2")

        for code in ["SEW-03", "CUT-01", "INS-01"]:
            create_production_line(db, _make_create("PL-L2", code, f"Line {code}"))

        lines = list_production_lines(db, "PL-L2")
        codes = [line.line_code for line in lines]
        assert codes == sorted(codes)

    def test_list_empty_client(self, transactional_db):
        """list_production_lines returns empty list for client with no lines."""
        db = transactional_db
        _seed_client(db, "PL-L3")

        lines = list_production_lines(db, "PL-L3")
        assert lines == []


# ============================================================================
# TestGetProductionLine
# ============================================================================
class TestGetProductionLine:
    """Tests for get_production_line function."""

    def test_get_found(self, transactional_db):
        """get_production_line returns the line when found."""
        db = transactional_db
        _seed_client(db, "PL-G1")

        created = create_production_line(db, _make_create("PL-G1", "SEW-01", "Sewing Line 1"))

        result = get_production_line(db, created.line_id)
        assert result is not None
        assert result.line_id == created.line_id
        assert result.line_code == "SEW-01"

    def test_get_not_found(self, transactional_db):
        """get_production_line returns None when line does not exist."""
        result = get_production_line(transactional_db, 999999)
        assert result is None


# ============================================================================
# TestGetProductionLineTree
# ============================================================================
class TestGetProductionLineTree:
    """Tests for get_production_line_tree function."""

    def test_tree_parent_with_children(self, transactional_db):
        """Tree returns top-level lines with nested children."""
        db = transactional_db
        _seed_client(db, "PL-T1")

        parent = create_production_line(
            db,
            _make_create("PL-T1", "SEW-AREA", "Sewing Area", line_type="SECTION"),
        )

        child_codes = ["SEW-01", "SEW-02", "SEW-03"]
        for code in child_codes:
            create_production_line(
                db,
                _make_create(
                    "PL-T1",
                    code,
                    f"Sewing {code}",
                    parent_line_id=parent.line_id,
                ),
            )

        tree = get_production_line_tree(db, "PL-T1")

        assert len(tree) == 1
        assert tree[0].line_code == "SEW-AREA"
        assert len(tree[0].children) == 3

        child_codes_result = sorted([c.line_code for c in tree[0].children])
        assert child_codes_result == sorted(child_codes)

    def test_tree_excludes_inactive(self, transactional_db):
        """Tree excludes inactive top-level lines."""
        db = transactional_db
        _seed_client(db, "PL-T2")

        active = create_production_line(db, _make_create("PL-T2", "ACT-01", "Active Line"))
        inactive = create_production_line(db, _make_create("PL-T2", "INACT-01", "Inactive Line"))
        deactivate_production_line(db, inactive.line_id)

        tree = get_production_line_tree(db, "PL-T2")
        assert len(tree) == 1
        assert tree[0].line_code == "ACT-01"

    def test_tree_multiple_roots(self, transactional_db):
        """Tree returns multiple top-level lines when no parent set."""
        db = transactional_db
        _seed_client(db, "PL-T3")

        create_production_line(db, _make_create("PL-T3", "CUT-01", "Cutting"))
        create_production_line(db, _make_create("PL-T3", "PKG-01", "Packaging"))
        create_production_line(db, _make_create("PL-T3", "SEW-01", "Sewing"))

        tree = get_production_line_tree(db, "PL-T3")
        assert len(tree) == 3
        codes = [t.line_code for t in tree]
        assert codes == sorted(codes)


# ============================================================================
# TestUpdateProductionLine
# ============================================================================
class TestUpdateProductionLine:
    """Tests for update_production_line function."""

    def test_update_name(self, transactional_db):
        """Update line_name of an existing production line."""
        db = transactional_db
        _seed_client(db, "PL-U1")

        created = create_production_line(db, _make_create("PL-U1", "SEW-01", "Before"))

        updated = update_production_line(db, created.line_id, ProductionLineUpdate(line_name="After"))
        assert updated is not None
        assert updated.line_name == "After"

    def test_update_multiple_fields(self, transactional_db):
        """Update department, line_type, and max_operators simultaneously."""
        db = transactional_db
        _seed_client(db, "PL-U2")

        created = create_production_line(db, _make_create("PL-U2", "GEN-01", "Generic Line"))

        updated = update_production_line(
            db,
            created.line_id,
            ProductionLineUpdate(
                department="FINISHING",
                line_type="SHARED",
                max_operators=20,
            ),
        )
        assert updated.department == "FINISHING"
        assert updated.line_type == "SHARED"
        assert updated.max_operators == 20

    def test_update_is_active(self, transactional_db):
        """Update is_active flag via update_production_line."""
        db = transactional_db
        _seed_client(db, "PL-U3")

        created = create_production_line(db, _make_create("PL-U3", "SEW-01", "Toggle"))

        updated = update_production_line(db, created.line_id, ProductionLineUpdate(is_active=False))
        assert updated.is_active is False

    def test_update_nonexistent_returns_none(self, transactional_db):
        """Updating a nonexistent line_id returns None."""
        result = update_production_line(
            transactional_db,
            999999,
            ProductionLineUpdate(line_name="Ghost"),
        )
        assert result is None


# ============================================================================
# TestDeactivateProductionLine
# ============================================================================
class TestDeactivateProductionLine:
    """Tests for deactivate_production_line function."""

    def test_deactivate_line(self, transactional_db):
        """Deactivate sets is_active=False."""
        db = transactional_db
        _seed_client(db, "PL-D1")

        created = create_production_line(db, _make_create("PL-D1", "SEW-01", "ToDeactivate"))

        assert deactivate_production_line(db, created.line_id) is True

        entry = get_production_line(db, created.line_id)
        assert entry.is_active is False

    def test_deactivate_nonexistent_returns_false(self, transactional_db):
        """Deactivating a nonexistent line_id returns False."""
        assert deactivate_production_line(transactional_db, 999999) is False

    def test_deactivate_cascades_to_children(self, transactional_db):
        """Deactivating a parent also deactivates its children."""
        db = transactional_db
        _seed_client(db, "PL-D2")

        parent = create_production_line(
            db,
            _make_create("PL-D2", "SEW-AREA", "Sewing Area", line_type="SECTION"),
        )
        child1 = create_production_line(
            db,
            _make_create("PL-D2", "SEW-01", "Sewing Line 1", parent_line_id=parent.line_id),
        )
        child2 = create_production_line(
            db,
            _make_create("PL-D2", "SEW-02", "Sewing Line 2", parent_line_id=parent.line_id),
        )
        child3 = create_production_line(
            db,
            _make_create("PL-D2", "SEW-03", "Sewing Line 3", parent_line_id=parent.line_id),
        )

        deactivate_production_line(db, parent.line_id)

        assert get_production_line(db, parent.line_id).is_active is False
        assert get_production_line(db, child1.line_id).is_active is False
        assert get_production_line(db, child2.line_id).is_active is False
        assert get_production_line(db, child3.line_id).is_active is False

    def test_deactivate_parent_children_no_longer_in_active_list(self, transactional_db):
        """After deactivating parent, children do not appear in active list."""
        db = transactional_db
        _seed_client(db, "PL-D3")

        parent = create_production_line(
            db,
            _make_create("PL-D3", "SEW-AREA", "Sewing Area", line_type="SECTION"),
        )
        create_production_line(
            db,
            _make_create("PL-D3", "SEW-01", "Sewing Line 1", parent_line_id=parent.line_id),
        )

        # Before deactivation: parent + child = 2 active
        assert len(list_production_lines(db, "PL-D3")) == 2

        deactivate_production_line(db, parent.line_id)

        # After deactivation: 0 active
        assert len(list_production_lines(db, "PL-D3")) == 0
        # But all still exist when including inactive
        assert len(list_production_lines(db, "PL-D3", include_inactive=True)) == 2


# ============================================================================
# TestCountActiveLines
# ============================================================================
class TestCountActiveLines:
    """Tests for count_active_lines function."""

    def test_count_zero(self, transactional_db):
        """Count returns 0 for client with no lines."""
        db = transactional_db
        _seed_client(db, "PL-CNT1")
        assert count_active_lines(db, "PL-CNT1") == 0

    def test_count_excludes_inactive(self, transactional_db):
        """Count excludes deactivated lines."""
        db = transactional_db
        _seed_client(db, "PL-CNT2")

        line1 = create_production_line(db, _make_create("PL-CNT2", "L1", "Line 1"))
        create_production_line(db, _make_create("PL-CNT2", "L2", "Line 2"))

        assert count_active_lines(db, "PL-CNT2") == 2

        deactivate_production_line(db, line1.line_id)
        assert count_active_lines(db, "PL-CNT2") == 1


# ============================================================================
# TestMultiTenantIsolation
# ============================================================================
class TestMultiTenantIsolation:
    """Test that production lines are properly isolated between clients."""

    def test_lines_isolated_by_client(self, transactional_db):
        """Lines from client A are not visible when querying client B."""
        db = transactional_db
        _seed_client(db, "PL-ISO-A")
        _seed_client(db, "PL-ISO-B")

        create_production_line(db, _make_create("PL-ISO-A", "SEW-01", "Sewing Line 1"))
        create_production_line(db, _make_create("PL-ISO-A", "SEW-02", "Sewing Line 2"))
        create_production_line(db, _make_create("PL-ISO-B", "CUT-01", "Cutting Only B"))

        lines_a = list_production_lines(db, "PL-ISO-A")
        lines_b = list_production_lines(db, "PL-ISO-B")

        assert len(lines_a) == 2
        assert len(lines_b) == 1
        assert lines_b[0].line_name == "Cutting Only B"

        # Ensure no cross-contamination
        codes_a = {line.line_code for line in lines_a}
        assert "CUT-01" not in codes_a

    def test_count_isolated_by_client(self, transactional_db):
        """count_active_lines only counts lines for the specified client."""
        db = transactional_db
        _seed_client(db, "PL-ISO-C")
        _seed_client(db, "PL-ISO-D")

        for i in range(5):
            create_production_line(db, _make_create("PL-ISO-C", f"C-{i}", f"Line C-{i}"))
        for i in range(3):
            create_production_line(db, _make_create("PL-ISO-D", f"D-{i}", f"Line D-{i}"))

        assert count_active_lines(db, "PL-ISO-C") == 5
        assert count_active_lines(db, "PL-ISO-D") == 3
