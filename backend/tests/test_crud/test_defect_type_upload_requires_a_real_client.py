"""`POST /api/defect-types/upload/{client_id}` must not write for a client that
does not exist, and must not report its own 4xx answers as server faults.

Two defects, both measured before the fix:

  * uploading to `/api/defect-types/upload/NO-SUCH-CLIENT-XYZ` answered 200
    with created=1, and the DEFECT_TYPE_CATALOG row landed -- orphan
    configuration keyed to a client nobody can look up. `verify_client_access`
    did not cover it: it asks whether the CALLER may act for a client, and an
    admin passes for every one, including clients that are not there.
  * the handler's `except Exception` sat below its own
    `raise HTTPException(400, "No valid defect types found in CSV")`, and
    `HTTPException` is an `Exception` -- so that deliberate 400 was caught and
    re-reported as a 500. The identical error raised ABOVE the `try` (a
    non-CSV filename) answered 400 correctly, which is how the asymmetry was
    spotted.

Found by the contract harness: the route only began running when write capture
learned to send a multipart body, and the id-sensitivity gate then noticed it
answering identically for a real and an impossible client.
"""

import pytest
from fastapi import HTTPException

from backend.crud.defect_type_catalog import bulk_create_defect_types
from backend.orm.defect_type_catalog import DefectTypeCatalog
from backend.schemas.defect_type_catalog import DefectTypeCatalogCSVRow
from backend.tests.fixtures.factories import TestDataFactory

MISSING = "NO-SUCH-CLIENT-XYZ"


@pytest.fixture
def seeded(db_session):
    client = TestDataFactory.create_client(db_session, client_id="DTC-C1", client_name="Defect Client")
    admin = TestDataFactory.create_user(db_session, user_id="DTC-U1", role="admin")
    db_session.commit()
    return {"client": client, "admin": admin}


def _rows() -> list:
    return [DefectTypeCatalogCSVRow(defect_code="DTC-1", defect_name="A Defect")]


def _count_for(db_session, client_id: str) -> int:
    count: int = db_session.query(DefectTypeCatalog).filter(DefectTypeCatalog.client_id == client_id).count()
    return count


def test_a_client_that_does_not_exist_is_refused(db_session, seeded):
    """404, and carried by the exception's own status rather than inferred by
    the route from the message text."""
    with pytest.raises(HTTPException) as excinfo:
        bulk_create_defect_types(db_session, MISSING, _rows(), seeded["admin"])

    assert excinfo.value.status_code == 404
    assert MISSING in str(excinfo.value.detail)


def test_the_refusal_leaves_no_orphan_rows(db_session, seeded):
    """The status code is not the point -- the absent row is. A guard that
    raised after the insert would satisfy the test above while leaving exactly
    the data this prevents."""
    with pytest.raises(HTTPException):
        bulk_create_defect_types(db_session, MISSING, _rows(), seeded["admin"])
    db_session.rollback()

    assert _count_for(db_session, MISSING) == 0


def test_a_real_client_still_gets_its_defect_types(db_session, seeded):
    """Guards the guard: without this, the two above would pass against a
    function that refused everything."""
    result = bulk_create_defect_types(db_session, seeded["client"].client_id, _rows(), seeded["admin"])
    db_session.commit()

    assert result["created"] == 1, result
    assert _count_for(db_session, seeded["client"].client_id) == 1


def test_a_deliberate_4xx_is_not_reported_as_a_server_fault(test_client, seeded):
    """The route's own 400 must survive its catch-all.

    Driven through the ASGI stack rather than the CRUD, because the defect was
    in the route's exception handling: `except Exception` sat below the
    `raise HTTPException(400, ...)` and swallowed it. The auth dependency is
    overridden rather than exercised -- this test is about the error mapping,
    and a 401 would hide the very distinction it exists to make.
    """
    from backend.auth.jwt import get_current_active_supervisor
    from backend.main import app

    app.dependency_overrides[get_current_active_supervisor] = lambda: seeded["admin"]
    try:
        response = test_client.post(
            f"/api/defect-types/upload/{seeded['client'].client_id}",
            files={"file": ("d.csv", b"defect_code,defect_name\n", "text/csv")},
        )
    finally:
        app.dependency_overrides.pop(get_current_active_supervisor, None)

    assert response.status_code != 500, response.text
    assert response.status_code == 400, response.text
    assert "No valid defect types" in response.text


def test_a_non_admin_global_upload_is_403_not_400(db_session, seeded):
    """An authorisation refusal must not be reported as malformed input.

    It was a ValueError the route mapped to 400 by inspecting the message --
    and before the error-handling fix, a 500. Neither says what actually
    happened. Raised with its own 403 at the raise site now, so no caller has
    to guess a status from prose.
    """
    from backend.crud.defect_type_catalog import GLOBAL_CLIENT_ID

    operator = TestDataFactory.create_user(db_session, user_id="DTC-U2", role="operator")
    db_session.commit()

    with pytest.raises(HTTPException) as excinfo:
        bulk_create_defect_types(db_session, GLOBAL_CLIENT_ID, _rows(), operator)

    assert excinfo.value.status_code == 403, excinfo.value.detail
