"""
Tests for Equipment CRUD operations.
Uses real database sessions -- no mocks for DB layer.

NOTE: The PRODUCTION_LINE table is created by a parallel agent (Task 2.1).
All tests here use line_id=None (shared equipment) to avoid FK dependency
on the PRODUCTION_LINE table. Once Task 2.1 is integrated, tests with
line_id should be added to verify FK-backed line assignment.
"""

import pytest
from datetime import date

from backend.tests.fixtures.factories import TestDataFactory
from backend.schemas.equipment import Equipment
from backend.schemas.production_line import ProductionLine  # noqa: F401 — register table for Base.metadata
from backend.crud.equipment import (
    create_equipment,
    list_equipment,
    list_shared_equipment,
    get_equipment,
    update_equipment,
    deactivate_equipment,
    get_equipment_by_code,
)
from backend.models.equipment import EquipmentCreate, EquipmentUpdate


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _seed_client(db, client_id="EQUIP-TEST-C1"):
    """Create the minimal client row needed for FK constraint."""
    client = TestDataFactory.create_client(db, client_id=client_id, client_name="Equipment Test Client")
    db.commit()
    return client


def _make_equipment(
    client_id="EQUIP-TEST-C1",
    equipment_code="MCH-001",
    equipment_name="Test Machine",
    equipment_type="Sewing Machine",
    is_shared=False,
    status="ACTIVE",
    line_id=None,
    **kwargs,
):
    """Build an EquipmentCreate payload with sensible defaults."""
    return EquipmentCreate(
        client_id=client_id,
        line_id=line_id,
        equipment_code=equipment_code,
        equipment_name=equipment_name,
        equipment_type=equipment_type,
        is_shared=is_shared,
        status=status,
        **kwargs,
    )


# ============================================================================
# TestCreateEquipment
# ============================================================================
class TestCreateEquipment:
    """Tests for create_equipment function."""

    def test_create_equipment_basic(self, transactional_db):
        """Create equipment and verify all fields are set correctly."""
        db = transactional_db
        _seed_client(db, "EQ-C1")

        data = _make_equipment(
            client_id="EQ-C1",
            equipment_code="MCH-001",
            equipment_name="Brother Sewing Machine",
            equipment_type="Sewing Machine",
            notes="Floor 2, Station A",
        )
        result = create_equipment(db, data)

        assert result.equipment_id is not None
        assert result.client_id == "EQ-C1"
        assert result.equipment_code == "MCH-001"
        assert result.equipment_name == "Brother Sewing Machine"
        assert result.equipment_type == "Sewing Machine"
        assert result.is_shared is False
        assert result.status == "ACTIVE"
        assert result.line_id is None
        assert result.notes == "Floor 2, Station A"
        assert result.is_active is True
        assert result.created_at is not None

    def test_create_shared_equipment(self, transactional_db):
        """Create shared equipment — must have line_id=None."""
        db = transactional_db
        _seed_client(db, "EQ-C2")

        data = _make_equipment(
            client_id="EQ-C2",
            equipment_code="CMN-001",
            equipment_name="Shared Forklift",
            is_shared=True,
            line_id=None,
        )
        result = create_equipment(db, data)

        assert result.is_shared is True
        assert result.line_id is None

    def test_create_shared_equipment_with_line_raises(self, transactional_db):
        """Shared equipment with a line_id set raises ValueError."""
        db = transactional_db
        _seed_client(db, "EQ-C3")

        data = _make_equipment(
            client_id="EQ-C3",
            equipment_code="BAD-001",
            equipment_name="Invalid Shared",
            is_shared=True,
            line_id=99,  # Not allowed for shared
        )
        with pytest.raises(ValueError, match="Shared equipment"):
            create_equipment(db, data)

    def test_create_duplicate_equipment_code_raises(self, transactional_db):
        """Creating a duplicate (client_id, equipment_code) raises ValueError."""
        db = transactional_db
        _seed_client(db, "EQ-C4")

        data = _make_equipment(client_id="EQ-C4", equipment_code="DUP-001")
        create_equipment(db, data)

        with pytest.raises(ValueError, match="already exists"):
            create_equipment(db, data)

    def test_create_same_code_different_client(self, transactional_db):
        """Same equipment_code is allowed for different clients."""
        db = transactional_db
        _seed_client(db, "EQ-CA")
        _seed_client(db, "EQ-CB")

        result_a = create_equipment(db, _make_equipment(client_id="EQ-CA", equipment_code="MCH-X01"))
        result_b = create_equipment(db, _make_equipment(client_id="EQ-CB", equipment_code="MCH-X01"))

        assert result_a.equipment_id != result_b.equipment_id
        assert result_a.client_id == "EQ-CA"
        assert result_b.client_id == "EQ-CB"

    def test_create_equipment_with_maintenance_dates(self, transactional_db):
        """Create equipment with maintenance date fields set."""
        db = transactional_db
        _seed_client(db, "EQ-C5")

        data = _make_equipment(
            client_id="EQ-C5",
            equipment_code="MCH-MAINT",
            last_maintenance_date=date(2026, 1, 15),
            next_maintenance_date=date(2026, 4, 15),
        )
        result = create_equipment(db, data)

        assert result.last_maintenance_date == date(2026, 1, 15)
        assert result.next_maintenance_date == date(2026, 4, 15)

    def test_create_equipment_with_status_maintenance(self, transactional_db):
        """Create equipment with MAINTENANCE status."""
        db = transactional_db
        _seed_client(db, "EQ-C6")

        data = _make_equipment(
            client_id="EQ-C6",
            equipment_code="MCH-DOWN",
            status="MAINTENANCE",
        )
        result = create_equipment(db, data)
        assert result.status == "MAINTENANCE"

    def test_create_equipment_with_status_retired(self, transactional_db):
        """Create equipment with RETIRED status."""
        db = transactional_db
        _seed_client(db, "EQ-C7")

        data = _make_equipment(
            client_id="EQ-C7",
            equipment_code="MCH-OLD",
            status="RETIRED",
        )
        result = create_equipment(db, data)
        assert result.status == "RETIRED"


# ============================================================================
# TestListEquipment
# ============================================================================
class TestListEquipment:
    """Tests for list_equipment function."""

    def test_list_equipment_returns_active_only(self, transactional_db):
        """list_equipment excludes inactive equipment by default."""
        db = transactional_db
        _seed_client(db, "EQ-L1")

        for code in ["MCH-001", "MCH-002", "MCH-003"]:
            create_equipment(db, _make_equipment(client_id="EQ-L1", equipment_code=code))

        # Deactivate one
        items = list_equipment(db, "EQ-L1")
        deactivate_equipment(db, items[0].equipment_id)

        active = list_equipment(db, "EQ-L1")
        all_entries = list_equipment(db, "EQ-L1", include_inactive=True)

        assert len(active) == 2
        assert len(all_entries) == 3

    def test_list_equipment_ordered_by_code(self, transactional_db):
        """list_equipment returns entries ordered by equipment_code."""
        db = transactional_db
        _seed_client(db, "EQ-L2")

        for code in ["MCH-003", "MCH-001", "MCH-002"]:
            create_equipment(db, _make_equipment(client_id="EQ-L2", equipment_code=code))

        items = list_equipment(db, "EQ-L2")
        codes = [e.equipment_code for e in items]
        assert codes == sorted(codes)

    def test_list_equipment_empty_client(self, transactional_db):
        """list_equipment returns empty list for client with no equipment."""
        db = transactional_db
        _seed_client(db, "EQ-L3")

        items = list_equipment(db, "EQ-L3")
        assert items == []

    def test_list_equipment_includes_shared_when_line_filter(self, transactional_db):
        """When filtering by line_id, shared equipment is also included."""
        db = transactional_db
        _seed_client(db, "EQ-L4")

        # Create line-specific equipment (line_id=None because PRODUCTION_LINE table may not exist,
        # but we simulate line assignment using a non-FK integer)
        # For this test, we directly insert equipment with line_id values
        # Since PRODUCTION_LINE table may not exist, we skip FK validation in SQLite
        line_equip = Equipment(
            client_id="EQ-L4",
            line_id=1,
            equipment_code="LINE-MCH-01",
            equipment_name="Line 1 Machine",
            is_shared=False,
            status="ACTIVE",
            is_active=True,
        )
        shared_equip = Equipment(
            client_id="EQ-L4",
            line_id=None,
            equipment_code="SHARED-01",
            equipment_name="Shared Compressor",
            is_shared=True,
            status="ACTIVE",
            is_active=True,
        )
        other_line_equip = Equipment(
            client_id="EQ-L4",
            line_id=2,
            equipment_code="LINE2-MCH-01",
            equipment_name="Line 2 Machine",
            is_shared=False,
            status="ACTIVE",
            is_active=True,
        )
        db.add_all([line_equip, shared_equip, other_line_equip])
        db.commit()

        # Filter by line_id=1 should return line 1 equipment + shared
        results = list_equipment(db, "EQ-L4", line_id=1)
        codes = {e.equipment_code for e in results}
        assert "LINE-MCH-01" in codes
        assert "SHARED-01" in codes
        assert "LINE2-MCH-01" not in codes

    def test_list_equipment_without_line_filter_returns_all(self, transactional_db):
        """Without line_id filter, all active equipment is returned."""
        db = transactional_db
        _seed_client(db, "EQ-L5")

        line_equip = Equipment(
            client_id="EQ-L5",
            line_id=1,
            equipment_code="LINE-MCH-01",
            equipment_name="Line 1 Machine",
            is_shared=False,
            status="ACTIVE",
            is_active=True,
        )
        shared_equip = Equipment(
            client_id="EQ-L5",
            line_id=None,
            equipment_code="SHARED-01",
            equipment_name="Shared Compressor",
            is_shared=True,
            status="ACTIVE",
            is_active=True,
        )
        db.add_all([line_equip, shared_equip])
        db.commit()

        results = list_equipment(db, "EQ-L5")
        assert len(results) == 2


# ============================================================================
# TestListSharedEquipment
# ============================================================================
class TestListSharedEquipment:
    """Tests for list_shared_equipment function."""

    def test_list_shared_equipment_only(self, transactional_db):
        """list_shared_equipment returns only shared equipment."""
        db = transactional_db
        _seed_client(db, "EQ-S1")

        create_equipment(db, _make_equipment(
            client_id="EQ-S1", equipment_code="NORM-01", is_shared=False,
        ))
        create_equipment(db, _make_equipment(
            client_id="EQ-S1", equipment_code="SHR-01",
            equipment_name="Shared Forklift", is_shared=True,
        ))
        create_equipment(db, _make_equipment(
            client_id="EQ-S1", equipment_code="SHR-02",
            equipment_name="Shared Compressor", is_shared=True,
        ))

        shared = list_shared_equipment(db, "EQ-S1")
        assert len(shared) == 2
        codes = {e.equipment_code for e in shared}
        assert codes == {"SHR-01", "SHR-02"}

    def test_list_shared_equipment_excludes_inactive(self, transactional_db):
        """list_shared_equipment excludes deactivated shared equipment."""
        db = transactional_db
        _seed_client(db, "EQ-S2")

        equip = create_equipment(db, _make_equipment(
            client_id="EQ-S2", equipment_code="SHR-GONE", is_shared=True,
        ))
        deactivate_equipment(db, equip.equipment_id)

        shared = list_shared_equipment(db, "EQ-S2")
        assert len(shared) == 0


# ============================================================================
# TestGetEquipment
# ============================================================================
class TestGetEquipment:
    """Tests for get_equipment function."""

    def test_get_equipment_found(self, transactional_db):
        """get_equipment returns the equipment when found."""
        db = transactional_db
        _seed_client(db, "EQ-G1")

        created = create_equipment(db, _make_equipment(
            client_id="EQ-G1", equipment_code="MCH-GET",
            equipment_name="Getter Machine",
        ))
        result = get_equipment(db, created.equipment_id)

        assert result is not None
        assert result.equipment_id == created.equipment_id
        assert result.equipment_name == "Getter Machine"

    def test_get_equipment_not_found(self, transactional_db):
        """get_equipment returns None when equipment does not exist."""
        result = get_equipment(transactional_db, 999999)
        assert result is None


# ============================================================================
# TestGetEquipmentByCode
# ============================================================================
class TestGetEquipmentByCode:
    """Tests for get_equipment_by_code function."""

    def test_get_by_code_found(self, transactional_db):
        """get_equipment_by_code finds equipment by client_id+equipment_code."""
        db = transactional_db
        _seed_client(db, "EQ-BC1")

        created = create_equipment(db, _make_equipment(
            client_id="EQ-BC1", equipment_code="MCH-FIND",
        ))
        result = get_equipment_by_code(db, "EQ-BC1", "MCH-FIND")

        assert result is not None
        assert result.equipment_id == created.equipment_id

    def test_get_by_code_not_found(self, transactional_db):
        """get_equipment_by_code returns None for non-existent code."""
        db = transactional_db
        _seed_client(db, "EQ-BC2")

        result = get_equipment_by_code(db, "EQ-BC2", "GHOST-001")
        assert result is None

    def test_get_by_code_wrong_client(self, transactional_db):
        """get_equipment_by_code does not cross clients."""
        db = transactional_db
        _seed_client(db, "EQ-BC3A")
        _seed_client(db, "EQ-BC3B")

        create_equipment(db, _make_equipment(
            client_id="EQ-BC3A", equipment_code="MCH-CROSS",
        ))

        result = get_equipment_by_code(db, "EQ-BC3B", "MCH-CROSS")
        assert result is None


# ============================================================================
# TestUpdateEquipment
# ============================================================================
class TestUpdateEquipment:
    """Tests for update_equipment function."""

    def test_update_equipment_name(self, transactional_db):
        """Update equipment_name of an existing entry."""
        db = transactional_db
        _seed_client(db, "EQ-U1")

        created = create_equipment(db, _make_equipment(
            client_id="EQ-U1", equipment_code="MCH-UPD",
            equipment_name="Before",
        ))
        updated = update_equipment(db, created.equipment_id, EquipmentUpdate(equipment_name="After"))

        assert updated is not None
        assert updated.equipment_name == "After"

    def test_update_equipment_status(self, transactional_db):
        """Update equipment status to MAINTENANCE."""
        db = transactional_db
        _seed_client(db, "EQ-U2")

        created = create_equipment(db, _make_equipment(client_id="EQ-U2", equipment_code="MCH-STAT"))
        updated = update_equipment(db, created.equipment_id, EquipmentUpdate(status="MAINTENANCE"))

        assert updated.status == "MAINTENANCE"

    def test_update_equipment_notes(self, transactional_db):
        """Update notes field."""
        db = transactional_db
        _seed_client(db, "EQ-U3")

        created = create_equipment(db, _make_equipment(client_id="EQ-U3", equipment_code="MCH-NOTE"))
        updated = update_equipment(
            db, created.equipment_id,
            EquipmentUpdate(notes="Needs calibration"),
        )
        assert updated.notes == "Needs calibration"

    def test_update_equipment_is_active(self, transactional_db):
        """Update is_active flag via update_equipment."""
        db = transactional_db
        _seed_client(db, "EQ-U4")

        created = create_equipment(db, _make_equipment(client_id="EQ-U4", equipment_code="MCH-ACT"))
        updated = update_equipment(db, created.equipment_id, EquipmentUpdate(is_active=False))
        assert updated.is_active is False

    def test_update_nonexistent_returns_none(self, transactional_db):
        """Updating a nonexistent equipment_id returns None."""
        result = update_equipment(
            transactional_db,
            999999,
            EquipmentUpdate(equipment_name="Ghost"),
        )
        assert result is None

    def test_update_maintenance_dates(self, transactional_db):
        """Update maintenance date fields."""
        db = transactional_db
        _seed_client(db, "EQ-U5")

        created = create_equipment(db, _make_equipment(client_id="EQ-U5", equipment_code="MCH-DATE"))
        updated = update_equipment(
            db, created.equipment_id,
            EquipmentUpdate(
                last_maintenance_date=date(2026, 2, 1),
                next_maintenance_date=date(2026, 5, 1),
            ),
        )
        assert updated.last_maintenance_date == date(2026, 2, 1)
        assert updated.next_maintenance_date == date(2026, 5, 1)


# ============================================================================
# TestDeactivateEquipment
# ============================================================================
class TestDeactivateEquipment:
    """Tests for deactivate_equipment function."""

    def test_deactivate_equipment(self, transactional_db):
        """Deactivate sets is_active=False."""
        db = transactional_db
        _seed_client(db, "EQ-D1")

        created = create_equipment(db, _make_equipment(
            client_id="EQ-D1", equipment_code="MCH-DEL",
        ))
        assert deactivate_equipment(db, created.equipment_id) is True

        entry = get_equipment(db, created.equipment_id)
        assert entry.is_active is False

    def test_deactivate_nonexistent_returns_false(self, transactional_db):
        """Deactivating a nonexistent equipment_id returns False."""
        assert deactivate_equipment(transactional_db, 999999) is False


# ============================================================================
# TestMultiTenantIsolation
# ============================================================================
class TestMultiTenantIsolation:
    """Test that equipment is properly isolated between clients."""

    def test_equipment_isolated_by_client(self, transactional_db):
        """Equipment from client A is not visible when querying client B."""
        db = transactional_db
        _seed_client(db, "EQ-ISO-A")
        _seed_client(db, "EQ-ISO-B")

        create_equipment(db, _make_equipment(
            client_id="EQ-ISO-A", equipment_code="MCH-A01",
            equipment_name="Machine A1",
        ))
        create_equipment(db, _make_equipment(
            client_id="EQ-ISO-A", equipment_code="MCH-A02",
            equipment_name="Machine A2",
        ))
        create_equipment(db, _make_equipment(
            client_id="EQ-ISO-B", equipment_code="MCH-B01",
            equipment_name="Only B Machine",
        ))

        equip_a = list_equipment(db, "EQ-ISO-A")
        equip_b = list_equipment(db, "EQ-ISO-B")

        assert len(equip_a) == 2
        assert len(equip_b) == 1
        assert equip_b[0].equipment_name == "Only B Machine"

        # Ensure no cross-contamination
        names_a = {e.equipment_name for e in equip_a}
        assert "Only B Machine" not in names_a

    def test_shared_equipment_isolated_by_client(self, transactional_db):
        """Shared equipment is also isolated by client."""
        db = transactional_db
        _seed_client(db, "EQ-ISO-SA")
        _seed_client(db, "EQ-ISO-SB")

        create_equipment(db, _make_equipment(
            client_id="EQ-ISO-SA", equipment_code="SHR-A01",
            equipment_name="Shared A", is_shared=True,
        ))
        create_equipment(db, _make_equipment(
            client_id="EQ-ISO-SB", equipment_code="SHR-B01",
            equipment_name="Shared B", is_shared=True,
        ))

        shared_a = list_shared_equipment(db, "EQ-ISO-SA")
        shared_b = list_shared_equipment(db, "EQ-ISO-SB")

        assert len(shared_a) == 1
        assert shared_a[0].equipment_name == "Shared A"
        assert len(shared_b) == 1
        assert shared_b[0].equipment_name == "Shared B"
