"""
Tests for Shift CRUD operations.
Uses real database sessions -- no mocks for DB layer.
"""

import pytest
from datetime import time

from backend.tests.fixtures.factories import TestDataFactory
from backend.orm.shift import Shift
from backend.crud.shift import (
    create_shift,
    list_shifts,
    get_shift,
    update_shift,
    deactivate_shift,
)
from backend.schemas.shift import ShiftCreate, ShiftUpdate


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _seed_client(db, client_id="SHIFT-TEST-C1"):
    """Create the minimal client row needed for FK constraint."""
    client = TestDataFactory.create_client(db, client_id=client_id, client_name="Shift Test Client")
    db.commit()
    return client


# ============================================================================
# TestCreateShift
# ============================================================================
class TestCreateShift:
    """Tests for create_shift function."""

    def test_create_shift_basic(self, transactional_db):
        """Create a shift and verify all fields are set correctly."""
        db = transactional_db
        _seed_client(db, "SH-C1")

        data = ShiftCreate(
            client_id="SH-C1",
            shift_name="1st",
            start_time=time(6, 0),
            end_time=time(14, 0),
        )
        result = create_shift(db, data)

        assert result.shift_id is not None
        assert result.client_id == "SH-C1"
        assert result.shift_name == "1st"
        assert result.start_time == time(6, 0)
        assert result.end_time == time(14, 0)
        assert result.is_active is True
        assert result.created_at is not None

    def test_create_duplicate_shift_raises(self, transactional_db):
        """Creating a duplicate (client_id, shift_name) raises ValueError."""
        db = transactional_db
        _seed_client(db, "SH-C2")

        data = ShiftCreate(
            client_id="SH-C2",
            shift_name="Duplicate Shift",
            start_time=time(6, 0),
            end_time=time(14, 0),
        )
        create_shift(db, data)

        with pytest.raises(ValueError, match="already exists"):
            create_shift(db, data)

    def test_create_shift_overnight(self, transactional_db):
        """Create an overnight shift (start > end, e.g. 22:00-06:00)."""
        db = transactional_db
        _seed_client(db, "SH-C3")

        data = ShiftCreate(
            client_id="SH-C3",
            shift_name="3rd",
            start_time=time(22, 0),
            end_time=time(6, 0),
        )
        result = create_shift(db, data)

        assert result.start_time == time(22, 0)
        assert result.end_time == time(6, 0)

    def test_create_shift_same_name_different_client(self, transactional_db):
        """Same shift name is allowed for different clients."""
        db = transactional_db
        _seed_client(db, "SH-CA")
        _seed_client(db, "SH-CB")

        data_a = ShiftCreate(
            client_id="SH-CA",
            shift_name="1st",
            start_time=time(6, 0),
            end_time=time(14, 0),
        )
        data_b = ShiftCreate(
            client_id="SH-CB",
            shift_name="1st",
            start_time=time(6, 0),
            end_time=time(14, 0),
        )

        result_a = create_shift(db, data_a)
        result_b = create_shift(db, data_b)

        assert result_a.shift_id != result_b.shift_id
        assert result_a.client_id == "SH-CA"
        assert result_b.client_id == "SH-CB"


# ============================================================================
# TestListShifts
# ============================================================================
class TestListShifts:
    """Tests for list_shifts function."""

    def test_list_shifts_returns_active_only(self, transactional_db):
        """list_shifts excludes inactive shifts by default."""
        db = transactional_db
        _seed_client(db, "SH-L1")

        for name in ["1st", "2nd", "3rd"]:
            create_shift(db, ShiftCreate(
                client_id="SH-L1",
                shift_name=name,
                start_time=time(6, 0),
                end_time=time(14, 0),
            ))

        # Deactivate one
        shifts = list_shifts(db, "SH-L1")
        deactivate_shift(db, shifts[0].shift_id)

        active = list_shifts(db, "SH-L1")
        all_entries = list_shifts(db, "SH-L1", include_inactive=True)

        assert len(active) == 2
        assert len(all_entries) == 3

    def test_list_shifts_ordered_by_name(self, transactional_db):
        """list_shifts returns entries ordered by shift_name."""
        db = transactional_db
        _seed_client(db, "SH-L2")

        for name in ["3rd", "1st", "2nd"]:
            create_shift(db, ShiftCreate(
                client_id="SH-L2",
                shift_name=name,
                start_time=time(6, 0),
                end_time=time(14, 0),
            ))

        shifts = list_shifts(db, "SH-L2")
        names = [s.shift_name for s in shifts]
        assert names == sorted(names)

    def test_list_shifts_empty_client(self, transactional_db):
        """list_shifts returns empty list for client with no shifts."""
        db = transactional_db
        _seed_client(db, "SH-L3")

        shifts = list_shifts(db, "SH-L3")
        assert shifts == []


# ============================================================================
# TestGetShift
# ============================================================================
class TestGetShift:
    """Tests for get_shift function."""

    def test_get_shift_found(self, transactional_db):
        """get_shift returns the shift when found."""
        db = transactional_db
        _seed_client(db, "SH-G1")

        created = create_shift(db, ShiftCreate(
            client_id="SH-G1",
            shift_name="Morning",
            start_time=time(6, 0),
            end_time=time(14, 0),
        ))

        result = get_shift(db, created.shift_id)
        assert result is not None
        assert result.shift_id == created.shift_id
        assert result.shift_name == "Morning"

    def test_get_shift_not_found(self, transactional_db):
        """get_shift returns None when shift does not exist."""
        result = get_shift(transactional_db, 999999)
        assert result is None


# ============================================================================
# TestUpdateShift
# ============================================================================
class TestUpdateShift:
    """Tests for update_shift function."""

    def test_update_shift_name(self, transactional_db):
        """Update shift_name of an existing shift."""
        db = transactional_db
        _seed_client(db, "SH-U1")

        created = create_shift(db, ShiftCreate(
            client_id="SH-U1",
            shift_name="Before",
            start_time=time(6, 0),
            end_time=time(14, 0),
        ))

        updated = update_shift(db, created.shift_id, ShiftUpdate(shift_name="After"))
        assert updated is not None
        assert updated.shift_name == "After"

    def test_update_shift_times(self, transactional_db):
        """Update start_time and end_time."""
        db = transactional_db
        _seed_client(db, "SH-U2")

        created = create_shift(db, ShiftCreate(
            client_id="SH-U2",
            shift_name="Flexible",
            start_time=time(6, 0),
            end_time=time(14, 0),
        ))

        updated = update_shift(db, created.shift_id, ShiftUpdate(
            start_time=time(7, 0),
            end_time=time(15, 0),
        ))
        assert updated.start_time == time(7, 0)
        assert updated.end_time == time(15, 0)

    def test_update_shift_is_active(self, transactional_db):
        """Update is_active flag via update_shift."""
        db = transactional_db
        _seed_client(db, "SH-U3")

        created = create_shift(db, ShiftCreate(
            client_id="SH-U3",
            shift_name="Toggle",
            start_time=time(6, 0),
            end_time=time(14, 0),
        ))

        updated = update_shift(db, created.shift_id, ShiftUpdate(is_active=False))
        assert updated.is_active is False

    def test_update_nonexistent_returns_none(self, transactional_db):
        """Updating a nonexistent shift_id returns None."""
        result = update_shift(
            transactional_db,
            999999,
            ShiftUpdate(shift_name="Ghost"),
        )
        assert result is None


# ============================================================================
# TestDeactivateShift
# ============================================================================
class TestDeactivateShift:
    """Tests for deactivate_shift function."""

    def test_deactivate_shift(self, transactional_db):
        """Deactivate sets is_active=False."""
        db = transactional_db
        _seed_client(db, "SH-D1")

        created = create_shift(db, ShiftCreate(
            client_id="SH-D1",
            shift_name="ToDeactivate",
            start_time=time(6, 0),
            end_time=time(14, 0),
        ))

        assert deactivate_shift(db, created.shift_id) is True

        # Verify it's deactivated
        entry = get_shift(db, created.shift_id)
        assert entry.is_active is False

    def test_deactivate_nonexistent_returns_false(self, transactional_db):
        """Deactivating a nonexistent shift_id returns False."""
        assert deactivate_shift(transactional_db, 999999) is False


# ============================================================================
# TestMultiTenantIsolation
# ============================================================================
class TestMultiTenantIsolation:
    """Test that shifts are properly isolated between clients."""

    def test_shifts_isolated_by_client(self, transactional_db):
        """Shifts from client A are not visible when querying client B."""
        db = transactional_db
        _seed_client(db, "SH-ISO-A")
        _seed_client(db, "SH-ISO-B")

        create_shift(db, ShiftCreate(
            client_id="SH-ISO-A",
            shift_name="1st",
            start_time=time(6, 0),
            end_time=time(14, 0),
        ))
        create_shift(db, ShiftCreate(
            client_id="SH-ISO-A",
            shift_name="2nd",
            start_time=time(14, 0),
            end_time=time(22, 0),
        ))
        create_shift(db, ShiftCreate(
            client_id="SH-ISO-B",
            shift_name="Only B Shift",
            start_time=time(8, 0),
            end_time=time(16, 0),
        ))

        shifts_a = list_shifts(db, "SH-ISO-A")
        shifts_b = list_shifts(db, "SH-ISO-B")

        assert len(shifts_a) == 2
        assert len(shifts_b) == 1
        assert shifts_b[0].shift_name == "Only B Shift"

        # Ensure no cross-contamination
        names_a = {s.shift_name for s in shifts_a}
        assert "Only B Shift" not in names_a
