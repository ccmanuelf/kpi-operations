"""
CRUD Tests — Break Time Module
Uses real database (transactional_db) — no mocks.
"""

import pytest
from fastapi import HTTPException

from backend.schemas.break_time import BreakTime
from backend.tests.fixtures.factories import TestDataFactory
from backend.crud.break_time import (
    create_break_time,
    list_break_times,
    list_break_times_for_client,
    get_total_break_minutes,
    update_break_time,
    deactivate_break_time,
)
from backend.models.break_time import BreakTimeCreate, BreakTimeUpdate


class TestBreakTimeCRUD:
    """CRUD operations for break times with real DB."""

    # ------------------------------------------------------------------
    # create_break_time
    # ------------------------------------------------------------------

    def test_create_break_time(self, transactional_db):
        """Create a break time linked to a valid shift."""
        client = TestDataFactory.create_client(transactional_db, client_id="BRK-CL")
        shift = TestDataFactory.create_shift(transactional_db, client_id="BRK-CL")
        transactional_db.commit()

        data = BreakTimeCreate(
            shift_id=shift.shift_id,
            client_id="BRK-CL",
            break_name="Morning Break",
            start_offset_minutes=120,
            duration_minutes=15,
            applies_to="ALL",
        )
        result = create_break_time(transactional_db, data)

        assert result.break_id is not None
        assert result.break_name == "Morning Break"
        assert result.duration_minutes == 15
        assert result.shift_id == shift.shift_id
        assert result.client_id == "BRK-CL"
        assert result.is_active is True

    def test_create_break_time_invalid_shift(self, transactional_db):
        """Creating a break for a non-existent shift raises 404."""
        TestDataFactory.create_client(transactional_db, client_id="BRK-CL2")
        transactional_db.commit()

        data = BreakTimeCreate(
            shift_id=99999,
            client_id="BRK-CL2",
            break_name="Ghost Break",
            start_offset_minutes=0,
            duration_minutes=10,
        )
        with pytest.raises(HTTPException) as exc_info:
            create_break_time(transactional_db, data)
        assert exc_info.value.status_code == 404

    # ------------------------------------------------------------------
    # list_break_times
    # ------------------------------------------------------------------

    def test_list_break_times_empty(self, transactional_db):
        """List returns empty when no breaks exist for the shift."""
        client = TestDataFactory.create_client(transactional_db, client_id="BRK-LE")
        shift = TestDataFactory.create_shift(transactional_db, client_id="BRK-LE")
        transactional_db.commit()

        result = list_break_times(transactional_db, shift.shift_id, "BRK-LE")
        assert result == []

    def test_list_break_times_ordered(self, transactional_db):
        """Breaks are returned ordered by start_offset_minutes."""
        client = TestDataFactory.create_client(transactional_db, client_id="BRK-ORD")
        shift = TestDataFactory.create_shift(transactional_db, client_id="BRK-ORD")
        transactional_db.flush()

        # Insert in reverse order
        for offset, name in [(240, "Lunch"), (120, "Morning"), (360, "Afternoon")]:
            transactional_db.add(
                BreakTime(
                    shift_id=shift.shift_id,
                    client_id="BRK-ORD",
                    break_name=name,
                    start_offset_minutes=offset,
                    duration_minutes=15,
                    applies_to="ALL",
                    is_active=True,
                )
            )
        transactional_db.commit()

        result = list_break_times(transactional_db, shift.shift_id, "BRK-ORD")
        assert len(result) == 3
        assert [b.break_name for b in result] == ["Morning", "Lunch", "Afternoon"]

    def test_list_break_times_excludes_inactive(self, transactional_db):
        """Inactive breaks are excluded from the listing."""
        client = TestDataFactory.create_client(transactional_db, client_id="BRK-INACT")
        shift = TestDataFactory.create_shift(transactional_db, client_id="BRK-INACT")
        transactional_db.flush()

        transactional_db.add(
            BreakTime(
                shift_id=shift.shift_id,
                client_id="BRK-INACT",
                break_name="Active Break",
                start_offset_minutes=60,
                duration_minutes=10,
                applies_to="ALL",
                is_active=True,
            )
        )
        transactional_db.add(
            BreakTime(
                shift_id=shift.shift_id,
                client_id="BRK-INACT",
                break_name="Deactivated Break",
                start_offset_minutes=120,
                duration_minutes=10,
                applies_to="ALL",
                is_active=False,
            )
        )
        transactional_db.commit()

        result = list_break_times(transactional_db, shift.shift_id, "BRK-INACT")
        assert len(result) == 1
        assert result[0].break_name == "Active Break"

    # ------------------------------------------------------------------
    # list_break_times_for_client
    # ------------------------------------------------------------------

    def test_list_break_times_for_client(self, transactional_db):
        """List all active breaks across shifts for a client."""
        client = TestDataFactory.create_client(transactional_db, client_id="BRK-ALL")
        shift_a = TestDataFactory.create_shift(
            transactional_db, client_id="BRK-ALL", shift_name="Day"
        )
        shift_b = TestDataFactory.create_shift(
            transactional_db, client_id="BRK-ALL", shift_name="Night"
        )
        transactional_db.flush()

        for sid in [shift_a.shift_id, shift_b.shift_id]:
            transactional_db.add(
                BreakTime(
                    shift_id=sid,
                    client_id="BRK-ALL",
                    break_name=f"Break S{sid}",
                    start_offset_minutes=120,
                    duration_minutes=15,
                    applies_to="ALL",
                    is_active=True,
                )
            )
        transactional_db.commit()

        result = list_break_times_for_client(transactional_db, "BRK-ALL")
        assert len(result) == 2

    # ------------------------------------------------------------------
    # get_total_break_minutes (KEY for KPI integration)
    # ------------------------------------------------------------------

    def test_get_total_break_minutes_single(self, transactional_db):
        """Total break minutes for a shift with one break."""
        client = TestDataFactory.create_client(transactional_db, client_id="BRK-SUM1")
        shift = TestDataFactory.create_shift(transactional_db, client_id="BRK-SUM1")
        transactional_db.flush()

        transactional_db.add(
            BreakTime(
                shift_id=shift.shift_id,
                client_id="BRK-SUM1",
                break_name="Lunch",
                start_offset_minutes=240,
                duration_minutes=30,
                applies_to="ALL",
                is_active=True,
            )
        )
        transactional_db.commit()

        total = get_total_break_minutes(transactional_db, shift.shift_id, "BRK-SUM1")
        assert total == 30

    def test_get_total_break_minutes_multiple(self, transactional_db):
        """Total break minutes sums all active breaks."""
        client = TestDataFactory.create_client(transactional_db, client_id="BRK-SUM2")
        shift = TestDataFactory.create_shift(transactional_db, client_id="BRK-SUM2")
        transactional_db.flush()

        for name, offset, dur in [
            ("Morning", 120, 15),
            ("Lunch", 240, 30),
            ("Afternoon", 360, 15),
        ]:
            transactional_db.add(
                BreakTime(
                    shift_id=shift.shift_id,
                    client_id="BRK-SUM2",
                    break_name=name,
                    start_offset_minutes=offset,
                    duration_minutes=dur,
                    applies_to="ALL",
                    is_active=True,
                )
            )
        transactional_db.commit()

        total = get_total_break_minutes(transactional_db, shift.shift_id, "BRK-SUM2")
        assert total == 60  # 15 + 30 + 15

    def test_get_total_break_minutes_excludes_inactive(self, transactional_db):
        """Inactive breaks are not counted in the sum."""
        client = TestDataFactory.create_client(transactional_db, client_id="BRK-SUM3")
        shift = TestDataFactory.create_shift(transactional_db, client_id="BRK-SUM3")
        transactional_db.flush()

        transactional_db.add(
            BreakTime(
                shift_id=shift.shift_id,
                client_id="BRK-SUM3",
                break_name="Active",
                start_offset_minutes=120,
                duration_minutes=20,
                applies_to="ALL",
                is_active=True,
            )
        )
        transactional_db.add(
            BreakTime(
                shift_id=shift.shift_id,
                client_id="BRK-SUM3",
                break_name="Inactive",
                start_offset_minutes=240,
                duration_minutes=30,
                applies_to="ALL",
                is_active=False,
            )
        )
        transactional_db.commit()

        total = get_total_break_minutes(transactional_db, shift.shift_id, "BRK-SUM3")
        assert total == 20  # only active counted

    def test_get_total_break_minutes_no_breaks(self, transactional_db):
        """Returns 0 when no breaks exist for the shift."""
        client = TestDataFactory.create_client(transactional_db, client_id="BRK-SUM4")
        shift = TestDataFactory.create_shift(transactional_db, client_id="BRK-SUM4")
        transactional_db.commit()

        total = get_total_break_minutes(transactional_db, shift.shift_id, "BRK-SUM4")
        assert total == 0

    # ------------------------------------------------------------------
    # Multi-tenant isolation
    # ------------------------------------------------------------------

    def test_multi_tenant_isolation(self, transactional_db):
        """Breaks for one client are invisible to another."""
        client_a = TestDataFactory.create_client(transactional_db, client_id="BRK-A")
        client_b = TestDataFactory.create_client(transactional_db, client_id="BRK-B")
        shift_a = TestDataFactory.create_shift(transactional_db, client_id="BRK-A")
        shift_b = TestDataFactory.create_shift(transactional_db, client_id="BRK-B")
        transactional_db.flush()

        transactional_db.add(
            BreakTime(
                shift_id=shift_a.shift_id,
                client_id="BRK-A",
                break_name="Break A",
                start_offset_minutes=120,
                duration_minutes=15,
                applies_to="ALL",
                is_active=True,
            )
        )
        transactional_db.add(
            BreakTime(
                shift_id=shift_b.shift_id,
                client_id="BRK-B",
                break_name="Break B",
                start_offset_minutes=120,
                duration_minutes=30,
                applies_to="ALL",
                is_active=True,
            )
        )
        transactional_db.commit()

        breaks_a = list_break_times(transactional_db, shift_a.shift_id, "BRK-A")
        breaks_b = list_break_times(transactional_db, shift_b.shift_id, "BRK-B")
        assert len(breaks_a) == 1
        assert len(breaks_b) == 1
        assert breaks_a[0].break_name == "Break A"
        assert breaks_b[0].break_name == "Break B"

        # Cross-check: client A's shift has no breaks under client B
        cross = list_break_times(transactional_db, shift_a.shift_id, "BRK-B")
        assert len(cross) == 0

        # Total minutes are tenant-scoped
        total_a = get_total_break_minutes(transactional_db, shift_a.shift_id, "BRK-A")
        total_b = get_total_break_minutes(transactional_db, shift_b.shift_id, "BRK-B")
        assert total_a == 15
        assert total_b == 30

    # ------------------------------------------------------------------
    # update_break_time
    # ------------------------------------------------------------------

    def test_update_break_time(self, transactional_db):
        """Partial update of break time fields."""
        client = TestDataFactory.create_client(transactional_db, client_id="BRK-UPD")
        shift = TestDataFactory.create_shift(transactional_db, client_id="BRK-UPD")
        transactional_db.flush()

        brk = BreakTime(
            shift_id=shift.shift_id,
            client_id="BRK-UPD",
            break_name="Old Name",
            start_offset_minutes=60,
            duration_minutes=10,
            applies_to="ALL",
            is_active=True,
        )
        transactional_db.add(brk)
        transactional_db.commit()

        update_data = BreakTimeUpdate(break_name="New Name", duration_minutes=20)
        updated = update_break_time(transactional_db, brk.break_id, update_data)

        assert updated is not None
        assert updated.break_name == "New Name"
        assert updated.duration_minutes == 20
        # Unchanged fields remain
        assert updated.start_offset_minutes == 60
        assert updated.applies_to == "ALL"

    def test_update_break_time_not_found(self, transactional_db):
        """Updating a non-existent break raises 404."""
        update_data = BreakTimeUpdate(break_name="No Such Break")
        with pytest.raises(HTTPException) as exc_info:
            update_break_time(transactional_db, 99999, update_data)
        assert exc_info.value.status_code == 404

    # ------------------------------------------------------------------
    # deactivate_break_time (soft delete)
    # ------------------------------------------------------------------

    def test_deactivate_break_time(self, transactional_db):
        """Soft-delete sets is_active to False."""
        client = TestDataFactory.create_client(transactional_db, client_id="BRK-DEL")
        shift = TestDataFactory.create_shift(transactional_db, client_id="BRK-DEL")
        transactional_db.flush()

        brk = BreakTime(
            shift_id=shift.shift_id,
            client_id="BRK-DEL",
            break_name="To Delete",
            start_offset_minutes=60,
            duration_minutes=10,
            applies_to="ALL",
            is_active=True,
        )
        transactional_db.add(brk)
        transactional_db.commit()

        success = deactivate_break_time(transactional_db, brk.break_id)
        assert success is True

        # Verify it is no longer listed
        result = list_break_times(transactional_db, shift.shift_id, "BRK-DEL")
        assert len(result) == 0

        # Verify total break minutes excludes it
        total = get_total_break_minutes(transactional_db, shift.shift_id, "BRK-DEL")
        assert total == 0

    def test_deactivate_break_time_not_found(self, transactional_db):
        """Deactivating a non-existent break raises 404."""
        with pytest.raises(HTTPException) as exc_info:
            deactivate_break_time(transactional_db, 99999)
        assert exc_info.value.status_code == 404

    # ------------------------------------------------------------------
    # Break associated with correct shift
    # ------------------------------------------------------------------

    def test_break_associated_with_correct_shift(self, transactional_db):
        """Breaks are scoped to their parent shift."""
        client = TestDataFactory.create_client(transactional_db, client_id="BRK-ASSOC")
        shift_day = TestDataFactory.create_shift(
            transactional_db, client_id="BRK-ASSOC", shift_name="Day"
        )
        shift_night = TestDataFactory.create_shift(
            transactional_db, client_id="BRK-ASSOC", shift_name="Night"
        )
        transactional_db.flush()

        transactional_db.add(
            BreakTime(
                shift_id=shift_day.shift_id,
                client_id="BRK-ASSOC",
                break_name="Day Lunch",
                start_offset_minutes=240,
                duration_minutes=30,
                applies_to="ALL",
                is_active=True,
            )
        )
        transactional_db.add(
            BreakTime(
                shift_id=shift_night.shift_id,
                client_id="BRK-ASSOC",
                break_name="Night Snack",
                start_offset_minutes=180,
                duration_minutes=15,
                applies_to="ALL",
                is_active=True,
            )
        )
        transactional_db.commit()

        day_breaks = list_break_times(transactional_db, shift_day.shift_id, "BRK-ASSOC")
        night_breaks = list_break_times(transactional_db, shift_night.shift_id, "BRK-ASSOC")

        assert len(day_breaks) == 1
        assert day_breaks[0].break_name == "Day Lunch"
        assert len(night_breaks) == 1
        assert night_breaks[0].break_name == "Night Snack"
