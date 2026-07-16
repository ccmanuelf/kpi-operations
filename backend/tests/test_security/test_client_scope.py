import pytest
from fastapi import HTTPException
from sqlalchemy import Column, String
from backend.auth.jwt import ClientScope, resolve_client_scope
from backend.middleware.client_auth import ClientAccessError

_col = Column("client_id", String)


def test_scope_filter_all_is_true_clause():
    # None client_ids -> a clause that filters nothing (renders as a truthy constant)
    clause = ClientScope(None).filter(_col)
    assert "true" in str(clause).lower() or "1 = 1" in str(clause)


def test_scope_filter_uses_in_for_concrete_clients():
    assert "IN" in str(ClientScope(("CLIENT-A", "CLIENT-B")).filter(_col)).upper()


def test_as_single_none_one_and_many():
    assert ClientScope(None).as_single() is None
    assert ClientScope(("CLIENT-A",)).as_single() == "CLIENT-A"
    with pytest.raises(HTTPException) as e:
        ClientScope(("CLIENT-A", "CLIENT-B")).as_single()
    assert e.value.status_code == 400


def test_resolve_admin_all_and_narrow(admin_user):
    assert resolve_client_scope(client_id=None, current_user=admin_user, db=None).client_ids is None
    assert resolve_client_scope(client_id="CLIENT-X", current_user=admin_user, db=None).client_ids == ("CLIENT-X",)


def test_resolve_operator_own_ok(operator_user_client_a):
    assert resolve_client_scope(client_id="CLIENT-A", current_user=operator_user_client_a, db=None).client_ids == (
        "CLIENT-A",
    )
    # omitted -> their own single client
    assert resolve_client_scope(client_id=None, current_user=operator_user_client_a, db=None).client_ids == (
        "CLIENT-A",
    )


def test_resolve_operator_other_client_forbidden(operator_user_client_a):
    with pytest.raises(ClientAccessError) as e:
        resolve_client_scope(client_id="CLIENT-B", current_user=operator_user_client_a, db=None)
    assert e.value.status_code == 403


def test_resolve_leader_multi(leader_user_multi_client):
    # one of theirs -> that one
    assert resolve_client_scope(client_id="CLIENT-B", current_user=leader_user_multi_client, db=None).client_ids == (
        "CLIENT-B",
    )
    # not theirs -> 403
    with pytest.raises(ClientAccessError):
        resolve_client_scope(client_id="CLIENT-C", current_user=leader_user_multi_client, db=None)
    # omitted -> full authorized set
    assert set(resolve_client_scope(client_id=None, current_user=leader_user_multi_client, db=None).client_ids) == {
        "CLIENT-A",
        "CLIENT-B",
    }
