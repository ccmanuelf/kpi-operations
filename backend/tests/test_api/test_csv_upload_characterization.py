"""Golden-master characterization of the CSV upload endpoints (pre/post C2 refactor).

Hits the REAL endpoints via TestClient. CRUD create_* is monkeypatched to a stub so
happy-path rows need no FK seeding — the real endpoint + mapper + processor still run.
"""

import io


def _csv_bytes(header: str, *rows: str) -> bytes:
    return ("\n".join([header, *rows]) + "\n").encode("utf-8")


def _files(content: bytes, name="upload.csv"):
    return {"file": (name, io.BytesIO(content), "text/csv")}


class _Created:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_holds_happy_path(test_client, admin_auth_headers, monkeypatch):
    captured = {}

    def stub(db, entry, user):
        captured["entry"] = entry
        return _Created(hold_entry_id="HOLD-1")

    monkeypatch.setattr("backend.endpoints.csv_upload.create_wip_hold", stub)
    content = _csv_bytes("client_id,work_order_number", "CLIENT-A,WO-1")
    resp = test_client.post("/api/holds/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["successful"] == 1
    assert body["failed"] == 0
    assert body["created_entries"] == ["HOLD-1"]
    assert captured["entry"] is not None  # mapper produced a schema object


def test_holds_invalid_row_recorded(test_client, admin_auth_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.endpoints.csv_upload.create_wip_hold",
        lambda db, e, u: _Created(hold_entry_id="X"),
    )
    # Missing required client_id → mapper raises → counted as failed (create never called)
    content = _csv_bytes("client_id,work_order_number", ",WO-1")
    resp = test_client.post("/api/holds/upload/csv", files=_files(content), headers=admin_auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["failed"] == 1
    assert body["successful"] == 0
    assert body["errors"][0]["row"] == 2


def test_holds_requires_elevated_role(test_client, auth_headers):
    # auth_headers self-registers => operator => 403 on this supervisor-tier endpoint
    content = _csv_bytes("client_id,work_order_number", "CLIENT-A,WO-1")
    resp = test_client.post("/api/holds/upload/csv", files=_files(content), headers=auth_headers)
    assert resp.status_code == 403
