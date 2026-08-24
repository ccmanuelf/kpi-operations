"""Fixture-generating seeders must produce NO audit rows; user-facing bulk
writers (CSV/XLSX upload) must still be fully captured.

Owner ruling (2026-08-12, fix round 1) narrowed this file's original scope:
suppression is ONLY for the demo seeder, which generates machine-created
fixture data carrying no human decision. process_csv_upload is reached from
11 authenticated, user-facing endpoints -- a supervisor uploading 500 hold
records must leave the same trail as editing one hold in the UI, so it is
deliberately NOT suppressed. See backend/services/csv_upload_processor.py's
docstring.

S1c repoints this file at the ONE seeder that survives the cutover:
`backend.seed.cli.seed()`. The two retiring seeders (seed_sample_client.main(),
init_demo_database.init_database()) each had their own test here; both are
gone now that S1c's later task deletes the modules they drove. S2 changes
this file's contract again: once the materializer authors its own audit
trail for the events it plays back, "zero AUDIT_ENTRY rows" becomes "every
audit row is one the materializer authored" -- a materializer-attributed
trail, not an absence of one.

Behavioural on purpose: an earlier draft of this task's plan asserted
`"audit_suppressed" in inspect.getsource(module)`, which passes if the name
merely appears in a comment and proves nothing about what the writer
actually wrote. Every test here runs the real writer with audit capture
registered and counts AUDIT_ENTRY rows.

`backend.seed.cli.seed()` is a special case worth recording rather than
silently relying on: `backend/seed/materialize.py` writes exclusively
through Core (`Connection.execute(insert(table), rows)`), never through an
ORM `Session`. `register_audit_listener()`'s handlers are ORM *mapper*
events (`after_insert`/`before_update`/`before_delete` on `Base`,
`propagate=True`) that SQLAlchemy fires only from a `Session` flush's unit
of work -- a bare Core insert never reaches them. So the zero-row count
below holds structurally, independent of `@audit_suppressed()`; verified
directly (commenting out the decorator on `seed()` and rerunning left the
count at 0). The count assertion is kept anyway as the documented contract
and a regression guard against a future writer that starts touching the ORM
without suppression, but the assertion that actually discriminates the
decorator being present is `test_seed_cli_seed_writes_no_audit_rows`'s spy
on `is_suppressed()` sampled from inside the real `materialize()` call --
the only point that can observe the contextvar `audit_suppressed()` resets
in a `finally` the instant `seed()` returns.

Also includes a mandatory control (`test_writes_outside_suppression_are_still_captured`):
without it, an all-zero count above would be equally satisfied by capture
being broken entirely, not by suppression working.

`register_audit_listener()` attaches process-wide SQLAlchemy mapper events
(see backend/audit/capture.py's module docstring) -- not scoped to a
Session -- so every test here registers it explicitly (mirroring
backend/tests/test_audit/test_capture.py) and an autouse fixture unregisters
it on teardown to avoid bleeding into later test modules.
"""

from datetime import date

import pytest

from backend.orm.audit_entry import AuditEntry


@pytest.fixture(autouse=True)
def _cleanup_audit_listener():
    from backend.audit.capture import unregister_audit_listener

    yield
    unregister_audit_listener()


def _audit_count(db) -> int:
    return int(db.query(AuditEntry).count())


# ==================== backend.seed.cli.seed ====================


def test_seed_cli_seed_writes_no_audit_rows(monkeypatch):
    """`seed()` (backend/seed/cli.py) is the one seeder left after S1c; this
    replaces the two retiring seeder-specific tests this file used to carry.
    Runs against a real Alembic-built schema (`clone_template_engine` --
    Alembic is the single schema mechanism, never `create_all`; see
    `test_no_create_all_outside_alembic`) with the real audit listener
    registered, the worst case for suppression: if anything in the write
    path went through the ORM, this would capture it unless genuinely
    suppressed.

    Two independent checks, because either alone is weak here (see the
    module docstring's explanation of why this writer is Core-only):

    1. The documented contract, zero AUDIT_ENTRY rows -- holds structurally
       for this writer regardless of the decorator, so it alone would not
       catch the decorator being removed.
    2. A spy on `materialize()`, patched by the name `cli.py` binds it under
       (`backend.seed.cli.materialize`, not `backend.seed.materialize.materialize`
       -- cli.py's `from ... import materialize` gives it its own reference,
       so patching the origin module would leave cli.py still calling the
       original), that samples `is_suppressed()` from inside the real call.
       That is the assertion the mutation proof in this task's report
       actually breaks.
    """
    import backend.seed.cli as cli_module
    from sqlalchemy import func, select

    from backend.audit.capture import register_audit_listener
    from backend.audit.context import is_suppressed
    from backend.database import Base
    from backend.tests.conftest import clone_template_engine

    observed = {}
    real_materialize = cli_module.materialize

    def _spy(conn, events, profile):
        observed["suppressed"] = is_suppressed()
        return real_materialize(conn, events, profile)

    monkeypatch.setattr(cli_module, "materialize", _spy)

    register_audit_listener()
    engine = clone_template_engine()
    try:
        client_id = sorted(cli_module.ALLOWLIST)[0]
        cli_module.seed(
            engine,
            client_ids=(client_id,),
            profile_name="smoke",
            seed_value=1234,
            as_of=date(2026, 8, 18),
            reset=False,
        )

        client_table = Base.metadata.tables["CLIENT"]
        work_order = Base.metadata.tables["WORK_ORDER"]
        hold_entry = Base.metadata.tables["HOLD_ENTRY"]
        audit_table = Base.metadata.tables["AUDIT_ENTRY"]
        with engine.connect() as conn:
            # Sanity: the run actually performed writes to audited tables
            # (CLIENT, WORK_ORDER, HOLD_ENTRY), so a zero AUDIT_ENTRY count
            # below is not merely "nothing happened".
            client_count = conn.execute(
                select(func.count()).select_from(client_table).where(client_table.c.client_id == client_id)
            ).scalar_one()
            work_order_count = conn.execute(
                select(func.count()).select_from(work_order).where(work_order.c.client_id == client_id)
            ).scalar_one()
            hold_entry_count = conn.execute(
                select(func.count()).select_from(hold_entry).where(hold_entry.c.client_id == client_id)
            ).scalar_one()
            audit_count = conn.execute(select(func.count()).select_from(audit_table)).scalar_one()

            assert client_count == 1
            assert work_order_count == 6  # smoke profile, single client: deterministic, not just non-zero
            assert hold_entry_count > 0
            assert audit_count == 0
    finally:
        engine.dispose()

    assert observed.get("suppressed") is True, (
        "materialize() ran without audit suppression active "
        "(or seed() never reached materialize() at all, leaving the spy unset)"
    )


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
