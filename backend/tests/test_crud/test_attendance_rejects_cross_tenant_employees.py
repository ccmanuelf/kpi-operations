"""Attendance rows must name an employee who belongs to their client.

`verify_client_access` asks whether the CALLER may write for a client. It never
asked whether the EMPLOYEE belongs to it, and an admin is authorised for every
client -- so both checks passed while the row itself was cross-tenant.

Measured before the guard, on the seeded contract database: a body naming
client DEMO-HOURLY with employee 1 (assigned DEMO-PIECE) returned 201 on BOTH
the single and bulk paths, and the row was written. Foreign keys would not have
caught it: the mismatch is composite -- both ids exist, they just do not belong
together.

Found by the contract harness. The bulk route only began running when write
capture gave it a request body, and the id-consistency spec written to keep the
capture honest is what made the acceptance visible.
"""

import pytest
from fastapi import HTTPException

from backend.crud.attendance import bulk_create_attendance_records, create_attendance_record
from backend.orm.attendance_entry import AttendanceEntry
from backend.schemas.attendance import AttendanceRecordCreate
from backend.tests.fixtures.factories import TestDataFactory

SHIFT_DATE = "2026-08-25"


@pytest.fixture
def two_clients(db_session):
    owner = TestDataFactory.create_client(db_session, client_id="TEN-A", client_name="Tenant A")
    other = TestDataFactory.create_client(db_session, client_id="TEN-B", client_name="Tenant B")
    admin = TestDataFactory.create_user(db_session, user_id="TEN-U1", role="admin")
    mine = TestDataFactory.create_employee(db_session, client_id="TEN-A", employee_name="Mine")
    theirs = TestDataFactory.create_employee(db_session, client_id="TEN-B", employee_name="Theirs")
    db_session.commit()
    return {"owner": owner, "other": other, "admin": admin, "mine": mine, "theirs": theirs}


def _record(client_id: str, employee_id: int) -> AttendanceRecordCreate:
    return AttendanceRecordCreate(
        client_id=client_id, employee_id=employee_id, shift_date=SHIFT_DATE, scheduled_hours=8
    )


def _rows_for(db_session, employee_id: int) -> int:
    count: int = db_session.query(AttendanceEntry).filter(AttendanceEntry.employee_id == employee_id).count()
    return count


def test_single_create_refuses_another_clients_employee(db_session, two_clients):
    before = _rows_for(db_session, two_clients["theirs"].employee_id)

    with pytest.raises(HTTPException) as excinfo:
        create_attendance_record(db_session, _record("TEN-A", two_clients["theirs"].employee_id), two_clients["admin"])

    assert excinfo.value.status_code == 422
    detail = str(excinfo.value.detail)
    assert "not available for client" in detail
    # And it must NOT name where the employee actually belongs: the caller is
    # authorised for TEN-A and nothing more, so leaking TEN-B would let anyone
    # scoped to one tenant enumerate every employee's tenancy by id.
    assert "TEN-B" not in detail, detail
    db_session.rollback()
    assert _rows_for(db_session, two_clients["theirs"].employee_id) == before


def test_bulk_create_refuses_it_per_row_and_writes_nothing(db_session, two_clients):
    """The bulk route answers 201 whatever its rows did, so the status code is
    not the assertion -- the absent row is."""
    theirs = two_clients["theirs"].employee_id
    before = _rows_for(db_session, theirs)

    result = bulk_create_attendance_records(db_session, [_record("TEN-A", theirs)], two_clients["admin"])

    assert result["failed"] == 1, result
    assert result["successful"] == 0, result
    assert "not available for client" in result["errors"][0]["error"]
    assert "TEN-B" not in result["errors"][0]["error"], result["errors"]
    assert _rows_for(db_session, theirs) == before


def test_an_employee_of_the_right_client_is_still_accepted(db_session, two_clients):
    """Guards the guard: without this, both tests above would pass against a
    route that rejected everything."""
    mine = two_clients["mine"].employee_id

    created = create_attendance_record(db_session, _record("TEN-A", mine), two_clients["admin"])
    db_session.commit()

    assert created.employee_id == mine
    assert _rows_for(db_session, mine) == 1


def test_a_multi_client_employee_is_accepted_for_each_of_their_clients(db_session, two_clients):
    """`client_id_assigned` is a comma-separated LIST, so a plain equality
    check would reject a legitimately multi-client employee. That is why the
    guard uses `client_token_clause` rather than `==`.
    """
    shared = TestDataFactory.create_employee(db_session, client_id="TEN-A", employee_name="Shared")
    shared.client_id_assigned = "TEN-A,TEN-B"
    db_session.commit()

    for client_id in ("TEN-A", "TEN-B"):
        created = create_attendance_record(db_session, _record(client_id, shared.employee_id), two_clients["admin"])
        db_session.commit()
        assert created.client_id == client_id

    assert _rows_for(db_session, shared.employee_id) == 2


def test_a_floating_pool_employee_is_not_locked_out(db_session, two_clients):
    """A NULL `client_id_assigned` is the documented shared floating-pool
    marker (`verify_employee_access` returns True for it). Rejecting it here
    would stop floating-pool employees having attendance recorded at all --
    a plausible over-correction this pins against.
    """
    floater = TestDataFactory.create_employee(db_session, client_id="TEN-A", employee_name="Floater")
    floater.client_id_assigned = None
    db_session.commit()

    created = create_attendance_record(db_session, _record("TEN-A", floater.employee_id), two_clients["admin"])
    db_session.commit()

    assert created.employee_id == floater.employee_id


def test_a_missing_employee_is_refused_the_same_way_as_someone_elses(db_session, two_clients):
    """The two refusals must be indistinguishable.

    A caller authorised for TEN-A and nothing more should not be able to tell
    "no such employee" from "that employee belongs to another client" -- if
    they can, they can enumerate the tenancy of every employee id by probing.
    So both raise with the same wording, and neither names a client the caller
    was not already authorised for.
    """
    theirs = two_clients["theirs"].employee_id
    missing = 9_999_999

    with pytest.raises(HTTPException) as their_employee:
        create_attendance_record(db_session, _record("TEN-A", theirs), two_clients["admin"])
    db_session.rollback()
    with pytest.raises(HTTPException) as no_employee:
        create_attendance_record(db_session, _record("TEN-A", missing), two_clients["admin"])
    db_session.rollback()

    theirs_detail = str(their_employee.value.detail).replace(str(theirs), "<id>")
    missing_detail = str(no_employee.value.detail).replace(str(missing), "<id>")

    assert theirs_detail == missing_detail, (
        "the two refusals differ, so a caller can tell an employee of another client from one "
        f"that does not exist: {theirs_detail!r} vs {missing_detail!r}"
    )
    assert their_employee.value.status_code == no_employee.value.status_code
