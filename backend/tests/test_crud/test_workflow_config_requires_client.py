"""Both workflow-config WRITE paths must refuse a client that does not exist.

`apply_workflow_template` and `update_workflow_configuration` each do

    config = db.query(ClientConfig).filter(...).first()
    if not config:
        config = ClientConfig(client_id=client_id)
        db.add(config)

so before `_require_client` an arbitrary string created a CLIENT_CONFIG row
keyed to a client that was never there -- orphan configuration nothing reads
and nothing cleans up. `verify_client_access` does not cover it: an admin is
authorised for every client, including the ones that do not exist.

Found by the contract harness's id-sensitivity gate, which noticed
`POST /api/workflow/config/{client_id}/apply-template` answering 200
identically for a real client and for `NO-SUCH-CLIENT-XYZ`.
"""

import pytest
from fastapi import HTTPException

from backend.crud.workflow.configuration import (
    apply_workflow_template,
    update_workflow_configuration,
)
from backend.orm.client_config import ClientConfig
from backend.tests.fixtures.factories import TestDataFactory

MISSING = "NO-SUCH-CLIENT-XYZ"


@pytest.fixture
def real_client(db_session):
    client = TestDataFactory.create_client(db_session, client_id="WF-CFG-C1", client_name="Workflow Config Test Client")
    db_session.commit()
    return client


@pytest.fixture
def admin(db_session, real_client):
    user = TestDataFactory.create_user(db_session, user_id="WF-CFG-U1", role="admin")
    db_session.commit()
    return user


def test_apply_template_404s_for_a_client_that_does_not_exist(db_session, admin):
    with pytest.raises(HTTPException) as excinfo:
        apply_workflow_template(db_session, MISSING, "standard", admin)

    assert excinfo.value.status_code == 404
    assert MISSING in str(excinfo.value.detail)


def test_update_config_404s_for_a_client_that_does_not_exist(db_session, admin):
    with pytest.raises(HTTPException) as excinfo:
        update_workflow_configuration(db_session, MISSING, {"workflow_statuses": ["RECEIVED"]}, admin)

    assert excinfo.value.status_code == 404
    assert MISSING in str(excinfo.value.detail)


def test_neither_refusal_leaves_a_config_row_behind(db_session, admin):
    """The point of the guard: not the status code, but the absent row.

    A 404 raised AFTER the `db.add` would still satisfy the two tests above
    while leaving the orphan this exists to prevent, so the row itself is
    what gets asserted.
    """
    for call in (
        lambda: apply_workflow_template(db_session, MISSING, "standard", admin),
        lambda: update_workflow_configuration(db_session, MISSING, {"workflow_statuses": ["RECEIVED"]}, admin),
    ):
        with pytest.raises(HTTPException):
            call()
        db_session.rollback()

    orphan = db_session.query(ClientConfig).filter(ClientConfig.client_id == MISSING).first()
    assert orphan is None


def test_a_real_client_still_gets_its_template_applied(db_session, admin, real_client):
    """The guard must refuse the missing client without refusing the present
    one -- otherwise both tests above would pass with the routes broken."""
    result = apply_workflow_template(db_session, real_client.client_id, "standard", admin)

    assert result["client_id"] == real_client.client_id
    assert result["workflow_statuses"]
