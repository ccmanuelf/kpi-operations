"""Bulk writers must produce NO audit rows.

Behavioural on purpose: an earlier draft of this task's plan asserted
`"audit_suppressed" in inspect.getsource(module)`, which passes if the name
merely appears in a comment and proves nothing about what the writer
actually wrote. Every test here runs the real writer with audit capture
registered and counts AUDIT_ENTRY rows.

Also includes a mandatory control (`test_writes_outside_suppression_are_still_captured`):
without it, all-zero counts in the suppression tests would be equally
satisfied by capture being broken entirely, not by suppression working.

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


def test_csv_upload_writes_no_audit_rows(transactional_db):
    """Bulk CSV import is data movement, not a per-row human decision.

    Drives process_csv_upload directly with a create_fn that inserts a real
    audited-table row (KPI_THRESHOLD), matching the direct-invocation unit
    pattern in tests/test_services/test_csv_upload_processor.py (rather than
    the full HTTP endpoint, which needs FK-heavy fixture data the
    characterization tests stub out).
    """
    from backend.audit.capture import register_audit_listener
    from backend.orm.kpi_threshold import KPIThreshold
    from backend.services.csv_upload_processor import process_csv_upload

    register_audit_listener()
    before = _audit_count(transactional_db)

    def create_fn(db, entry, user):
        threshold = KPIThreshold(threshold_id=entry["id"], kpi_key=entry["key"], target_value=80.0)
        db.add(threshold)
        db.flush()
        return threshold

    rows = [{"id": "CSV-AUD-1", "key": "efficiency"}, {"id": "CSV-AUD-2", "key": "oee"}]
    res = process_csv_upload(
        rows,
        db=transactional_db,
        current_user=None,
        row_mapper=lambda row, _user: row,
        create_fn=create_fn,
        id_getter=lambda c: c.threshold_id,
    )

    assert res.successful == 2
    assert res.failed == 0
    assert _audit_count(transactional_db) == before


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
