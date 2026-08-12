"""Fixture-generating seeders must produce NO audit rows; user-facing bulk
writers (CSV/XLSX upload) must still be fully captured.

Owner ruling (2026-08-12, fix round 1) narrowed this file's original scope:
suppression is ONLY for the two demo seeders (seed_sample_client.main(),
init_demo_database.init_database()), which generate machine-created fixture
data carrying no human decision. process_csv_upload is reached from 11
authenticated, user-facing endpoints -- a supervisor uploading 500 hold
records must leave the same trail as editing one hold in the UI, so it is
deliberately NOT suppressed. See backend/services/csv_upload_processor.py's
docstring.

Behavioural on purpose: an earlier draft of this task's plan asserted
`"audit_suppressed" in inspect.getsource(module)`, which passes if the name
merely appears in a comment and proves nothing about what the writer
actually wrote. Every test here runs the real writer with audit capture
registered and counts AUDIT_ENTRY rows.

Also includes a mandatory control (`test_writes_outside_suppression_are_still_captured`):
without it, all-zero counts in the two seeder suppression tests would be
equally satisfied by capture being broken entirely, not by suppression
working.

`register_audit_listener()` attaches process-wide SQLAlchemy mapper events
(see backend/audit/capture.py's module docstring) -- not scoped to a
Session -- so every test here registers it explicitly (mirroring
backend/tests/test_audit/test_capture.py) and an autouse fixture unregisters
it on teardown to avoid bleeding into later test modules.
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from backend.orm.audit_entry import AuditEntry

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def _cleanup_audit_listener():
    from backend.audit.capture import unregister_audit_listener

    yield
    unregister_audit_listener()


def _audit_count(db) -> int:
    return int(db.query(AuditEntry).count())


# ==================== seed_sample_client.py ====================


def test_seed_sample_client_main_writes_no_audit_rows(tmp_path, monkeypatch):
    """`main()` is the real CLI/production entry point (the module's own
    docstring documents the VM invocation as `python -m
    backend.scripts.seed_sample_client`) and is what runs on a `--reset`
    re-seed. It owns its own engine/session (built from DATABASE_URL), so
    this drives it end-to-end against a throwaway file-based sqlite db
    rather than a shared fixture session.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from backend.audit.capture import register_audit_listener
    from backend.db.factories import TestDataFactory
    from backend.db.migrate import upgrade_to_head
    from backend.orm import HoldEntry, WorkOrder
    from backend.scripts import seed_sample_client as seed

    db_path = tmp_path / "seed_audit_test.db"
    db_url = f"sqlite:///{db_path}"
    upgrade_to_head(db_url)

    # seed.main() resolves entered_by via a real admin user -- seed it first,
    # same as the existing full-orchestrator tests in
    # tests/test_scripts/test_seed_sample_client.py (`_seed_admin`).
    setup_engine = create_engine(db_url)
    try:
        with Session(setup_engine) as session:
            TestDataFactory.create_user(session, username="seed_admin", role="admin")
            session.commit()
    finally:
        setup_engine.dispose()

    register_audit_listener()
    monkeypatch.setenv("DATABASE_URL", db_url)

    rc = seed.main(["--client", "DEMO-PIECE", "--days", "1"])
    assert rc == 0

    check_engine = create_engine(db_url)
    try:
        with Session(check_engine) as session:
            # Sanity: the run actually performed writes to audited tables
            # (CLIENT, WORK_ORDER, HOLD_ENTRY), so a zero AUDIT_ENTRY count
            # below is not merely "nothing happened".
            assert session.query(seed.Client).filter_by(client_id="DEMO-PIECE").count() == 1
            assert session.query(WorkOrder).filter_by(client_id="DEMO-PIECE").count() >= 1
            assert session.query(HoldEntry).filter_by(client_id="DEMO-PIECE").count() >= 1

            assert _audit_count(session) == 0
    finally:
        check_engine.dispose()


# ==================== init_demo_database.py ====================


def test_init_demo_database_writes_no_audit_rows(tmp_path):
    """`init_database()` is the single canonical demo seeder (per its own
    docstring: "Run 8 unification"), invoked by CI's seed step and the
    e2e-sqlite job against a file-based DATABASE_URL -- exactly as driven
    here (mirrors tests/test_scripts/test_init_demo_database.py's subprocess
    pattern). It never imports the FastAPI app, so audit capture is not
    registered by anything in-process here; the driver script below
    registers it explicitly to exercise the worst case: capture IS active,
    and suppression must still hold.
    """
    db_path = tmp_path / "demo_audit_test.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["PYTHONPATH"] = "."

    driver = (
        "from backend.audit.capture import register_audit_listener; "
        "register_audit_listener(); "
        "from backend.scripts.init_demo_database import init_database; "
        "init_database()"
    )
    result = subprocess.run(
        [sys.executable, "-c", driver],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"demo seeder crashed (exit {result.returncode})\n"
        f"--- stdout tail ---\n{result.stdout[-2000:]}\n"
        f"--- stderr tail ---\n{result.stderr[-2000:]}"
    )

    conn = sqlite3.connect(str(db_path))
    try:
        # Sanity: the run actually performed writes to audited tables
        # (CLIENT, USER) before checking AUDIT_ENTRY is empty.
        (client_count,) = conn.execute("SELECT COUNT(*) FROM CLIENT").fetchone()
        (user_count,) = conn.execute("SELECT COUNT(*) FROM USER").fetchone()
        assert client_count >= 1
        assert user_count >= 1

        (audit_count,) = conn.execute("SELECT COUNT(*) FROM AUDIT_ENTRY").fetchone()
    finally:
        conn.close()

    assert audit_count == 0


# ==================== csv_upload_processor.py ====================


def test_csv_upload_is_audited(test_client, admin_auth_headers):
    """CSV/XLSX bulk import IS captured, same as any other write.

    Owner ruling 2026-08-12 (reverses this test's original intent): a
    supervisor uploading 500 hold records must leave the same entity-level
    trail as editing one hold in the UI -- bulk changes are exactly the
    writes most worth tracing. process_csv_upload is therefore NOT
    suppressed. See backend/services/csv_upload_processor.py.

    Drives the REAL /api/clients/upload/csv endpoint through the real ASGI
    app with create_client NOT stubbed (unlike
    tests/test_api/test_csv_upload_characterization.py, which stubs every
    create_fn to avoid FK-heavy fixture data -- CLIENT has none, so the
    real CRUD function can run here). This is the same pattern
    test_audit_wiring.py's test_actor_context_survives_a_real_request_through_the_asgi_app
    uses, and answers whether the CSV path attributes a real actor rather
    than "system": get_current_admin -> get_current_user (Depends chain)
    calls set_actor() before the endpoint body -- including
    process_csv_upload -- ever runs, so if actor attribution survives
    FastAPI's real threadpool dispatch for one endpoint (already proven by
    that test), it holds for this one too on the same mechanism. Verified
    here directly rather than assumed.
    """
    import io

    from backend.audit.capture import register_audit_listener
    from backend.database import get_db
    from backend.orm.audit_entry import AuditOperation

    # Idempotent: importing backend.main.app (which test_client does) already
    # registers this process-wide via configure_middleware(). Explicit here
    # too so this test does not depend on ambient state left by another test
    # in this file's registration order.
    register_audit_listener()

    id1, id2 = "AUD-CSV-1", "AUD-CSV-2"
    content = ("client_id,client_name\n" f"{id1},CSV Audit Co 1\n" f"{id2},CSV Audit Co 2\n").encode("utf-8")

    resp = test_client.post(
        "/api/clients/upload/csv",
        files={"file": ("upload.csv", io.BytesIO(content), "text/csv")},
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["successful"] == 2
    assert body["failed"] == 0
    assert set(body["created_entries"]) == {id1, id2}

    # Read back through the SAME dependency override the request used (see
    # test_audit_wiring.py's module docstring for why a direct
    # get_test_engine() import would silently read the wrong module copy).
    db_override = test_client.app.dependency_overrides[get_db]
    db_gen = db_override()
    session = next(db_gen)
    try:
        rows = (
            session.query(AuditEntry)
            .filter(AuditEntry.table_name == "CLIENT", AuditEntry.record_pk.in_([id1, id2]))
            .order_by(AuditEntry.record_pk)
            .all()
        )
        # Pinned, not merely ">0": exactly one INSERT row per uploaded client.
        assert len(rows) == 2, f"expected exactly 2 AUDIT_ENTRY rows for the CSV-created clients, got {len(rows)}"
        assert [r.record_pk for r in rows] == [id1, id2]
        for row in rows:
            assert row.table_name == "CLIENT"
            assert row.operation == AuditOperation.INSERT
            assert row.actor_user_id == "USR-ADMINTEST", (
                f"expected the authenticated admin's user_id, got {row.actor_user_id!r} -- "
                "the CSV upload path did not attribute a real actor"
            )
    finally:
        db_gen.close()


# ==================== control ====================


def test_writes_outside_suppression_are_still_captured(transactional_db):
    """The opt-out must stay deliberate -- it is not an ambient default.

    Without this, the all-zero counts above would be equally satisfied by
    audit capture being broken entirely, not by suppression working.
    """
    from backend.audit.capture import register_audit_listener
    from backend.tests.fixtures.factories import TestDataFactory

    register_audit_listener()
    before = _audit_count(transactional_db)

    TestDataFactory.create_client(transactional_db, client_id="SUPP-CTRL", client_name="Control")
    transactional_db.flush()

    assert _audit_count(transactional_db) == before + 1
