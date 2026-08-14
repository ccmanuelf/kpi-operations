"""MariaDB portability guards.

The dialect-agnostic schema test runs in the default (SQLite) suite. The
integration tests skip unless the app engine is MariaDB (DATABASE_URL points
at MariaDB), which is the case only in the dedicated CI job — see
.github/workflows/ci.yml::mariadb-portability.
"""

from sqlalchemy import String
from unittest.mock import patch

from backend.orm.user import User
from backend.db.providers.mariadb import MariaDBProvider


def test_client_id_assigned_is_bounded_string_not_text():
    """MariaDB cannot index TEXT; the column must be a bounded String."""
    col = User.__table__.c.client_id_assigned
    assert isinstance(col.type, String)
    assert col.type.length == 500
    assert col.index is True


def test_mariadb_provider_enforces_utf8mb4():
    """The MariaDB provider must pass charset=utf8mb4 in connect_args."""
    provider = MariaDBProvider()
    with patch("backend.db.providers.mariadb.create_engine") as mock_create_engine:
        provider.create_engine("mysql+pymysql://u:p@localhost:3306/db")
    _, kwargs = mock_create_engine.call_args
    assert kwargs["connect_args"]["charset"] == "utf8mb4"


def test_register_all_models_populates_full_metadata():
    """The canonical registration helper must yield the complete table registry.

    Must match the Alembic baseline; update when adding a migration that
    creates/drops tables (backend/alembic/versions/0001_real_baseline.py
    has 57 `op.create_table(` calls; 0004_labor_hours_columns.py adds
    ATTENDANCE_HOUR_ALLOCATION, bringing the total to 58;
    0005_audit_trail.py adds AUDIT_ENTRY, bringing the total to 59;
    0006_hold_status_history.py adds HOLD_STATUS_TRANSITION, bringing the
    total to 60).
    """
    from backend.orm import register_all_models

    register_all_models()
    assert len(Base.metadata.tables) == 60


# ---------------------------------------------------------------------------
# FK type-consistency guard (always-on, dialect-agnostic). InnoDB (MariaDB)
# refuses to create a table whose FK column type differs from the referenced
# column (errno 150 "Foreign key constraint is incorrectly formed"); SQLite
# silently accepts the mismatch, so it must be caught statically here.
# ---------------------------------------------------------------------------

from backend.database import Base  # noqa: E402

# Populate Base.metadata with EVERY table using the canonical registration helper
# to avoid import-block drift.
from backend.orm import register_all_models  # noqa: E402

register_all_models()


def test_foreign_key_column_types_match_referenced_columns():
    """Every FK column's type must exactly match its referenced column's type."""
    mismatches = []
    for table in Base.metadata.sorted_tables:
        for constraint in table.foreign_key_constraints:
            for fk in constraint.elements:
                local, remote = fk.parent, fk.column
                same_class = type(local.type) is type(remote.type)
                same_length = getattr(local.type, "length", None) == getattr(remote.type, "length", None)
                if not (same_class and same_length):
                    mismatches.append(
                        f"{table.name}.{local.name} ({local.type!r}) -> "
                        f"{remote.table.name}.{remote.name} ({remote.type!r})"
                    )
    assert mismatches == []


# ---------------------------------------------------------------------------
# Integration tests: build the FULL schema via create_all against a live
# MariaDB and round-trip real data through it. These only run when the app
# engine is MariaDB; on SQLite (the default local/CI suite) they are skipped
# individually via @requires_mariadb rather than a module-level pytestmark,
# so the unit tests above keep running on every engine.
# ---------------------------------------------------------------------------

import pytest  # noqa: E402
from sqlalchemy import inspect, select  # noqa: E402

from backend.database import SessionLocal, engine  # noqa: E402
from backend.orm.event_store import EventStore  # noqa: E402

_IS_MARIADB = "mysql" in str(engine.url).lower()
requires_mariadb = pytest.mark.skipif(
    not _IS_MARIADB, reason="requires the app engine to be MariaDB (DATABASE_URL=mysql+pymysql://...)"
)


@pytest.fixture(scope="module")
def mariadb_schema():
    """Build the full schema on live MariaDB via Alembic; drop it afterwards."""
    from backend.db.migrate import rebuild_schema

    # render_as_string(hide_password=False): str(engine.url) masks the password
    # as "***", which Alembic would then use verbatim and fail to authenticate.
    rebuild_schema(engine.url.render_as_string(hide_password=False))
    yield
    Base.metadata.drop_all(bind=engine)


def _autogen_diff_is_empty(url: str) -> list:
    """Upgrade a throwaway DB to head and diff Base.metadata against it."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine as sa_create_engine

    from backend.db.migrate import upgrade_to_head

    upgrade_to_head(url)
    diff_engine = sa_create_engine(url)
    try:
        with diff_engine.connect() as conn:
            ctx = MigrationContext.configure(conn, opts={"compare_type": True, "render_as_batch": "sqlite" in url})
            return list(compare_metadata(ctx, Base.metadata))
    finally:
        diff_engine.dispose()


def test_baseline_builds_schema_equal_to_metadata_sqlite(tmp_path):
    """alembic upgrade head on SQLite must reproduce Base.metadata exactly."""
    url = f"sqlite:///{tmp_path}/baseline_guard.db"
    assert _autogen_diff_is_empty(url) == []


@requires_mariadb
def test_baseline_builds_schema_equal_to_metadata_mariadb(mariadb_schema):
    """Same guarantee against live MariaDB (runs in the mariadb-portability job)."""
    from backend.database import engine as app_engine

    # render_as_string(hide_password=False): str(url) masks the password as "***".
    assert _autogen_diff_is_empty(app_engine.url.render_as_string(hide_password=False)) == []


@requires_mariadb
def test_full_schema_creates_on_mariadb(mariadb_schema):
    """create_all must succeed and produce the USER table with its index."""
    inspector = inspect(engine)
    assert "USER" in inspector.get_table_names()
    indexed_cols = {c for ix in inspector.get_indexes("USER") for c in ix["column_names"]}
    assert "client_id_assigned" in indexed_cols


@requires_mariadb
def test_user_client_id_assigned_roundtrip(mariadb_schema):
    """A long, multi-byte (utf8mb4) comma-separated value round-trips intact."""
    value = ",".join(f"CLÍENT-Ñ-{i:02d}" for i in range(20))  # ~260 chars, accented
    session = SessionLocal()
    try:
        session.add(User(user_id="pt-user-1", username="pt-user-1", email="pt1@example.com", client_id_assigned=value))
        session.commit()
        fetched = session.execute(select(User.client_id_assigned).where(User.user_id == "pt-user-1")).scalar_one()
        assert fetched == value
    finally:
        session.close()


@requires_mariadb
def test_event_store_json_roundtrip(mariadb_schema):
    """A JSON column round-trips a nested dict on MariaDB."""
    from datetime import datetime

    payload = {"qty": 12, "nested": {"ok": True, "tags": ["a", "b"]}, "note": " café"}
    session = SessionLocal()
    try:
        session.add(
            EventStore(
                event_id="pt-evt-1",
                event_type="TEST",
                aggregate_type="X",
                aggregate_id="1",
                occurred_at=datetime(2026, 6, 26, 12, 0, 0),
                payload=payload,
            )
        )
        session.commit()
        fetched = session.execute(select(EventStore.payload).where(EventStore.event_id == "pt-evt-1")).scalar_one()
        assert fetched == payload
    finally:
        session.close()


@requires_mariadb
def test_app_engine_connection_charset_is_utf8mb4(mariadb_schema):
    """Proves the database.py fix: the app engine connects with utf8mb4."""
    from sqlalchemy import text

    session = SessionLocal()
    try:
        charset = session.execute(text("SELECT @@character_set_connection")).scalar()
        assert charset == "utf8mb4"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Schema-mechanism guard (always-on, dialect-agnostic). Alembic is the only
# schema mechanism, in app code AND in tests: test fixtures get a fresh
# schema by cloning the Alembic-built template (conftest.clone_template_engine
# / db_engine / db_session), never by calling create_all() imperatively.  # schema-guard: allow
# ---------------------------------------------------------------------------


def test_no_create_all_outside_alembic():
    """Alembic is the only schema mechanism: create_all() and raw CREATE TABLE  # schema-guard: allow
    DDL must not exist anywhere in backend/ outside Alembic itself.

    Catches both the ORM path (Base.metadata.create_all()) and hand-written  # schema-guard: allow
    SQL (e.g. a standalone script re-creating a table Alembic already owns —
    see backend/scripts/seed_defect_types.py's history).

    Line-level exemption: any individual line carrying the marker
    ``# schema-guard: allow`` is skipped. That lets this guard scan its OWN
    host file too — its regex literals and docstring mentions carry the marker,
    so it no longer needs a whole-file allowlist that could hide a real
    offender added to this file.
    """
    import pathlib
    import re

    backend_root = pathlib.Path(__file__).resolve().parent.parent
    marker = "# schema-guard: allow"
    create_all_re = re.compile(r"\bcreate_all\s*\(")  # schema-guard: allow
    create_table_re = re.compile(r"CREATE TABLE", re.IGNORECASE)  # schema-guard: allow

    offenders = []
    for py in backend_root.rglob("*.py"):
        if "alembic" in py.parts or ".venv" in py.parts:
            continue
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), start=1):
            if marker in line:
                continue
            if create_all_re.search(line) or create_table_re.search(line):
                offenders.append(f"{py.relative_to(backend_root)}:{lineno}")
    assert sorted(offenders) == []


# ---------------------------------------------------------------------------
# cast(col, Date) SQLite guard (always-on, dialect-agnostic). SQLite's
# numeric column affinity mangles CAST(<DateTime column> AS DATE) --
# CAST('2026-01-15 10:00:00' AS DATE) collapses to 2026, silently emptying
# every date-range/equality filter that uses it. MariaDB's CAST AS DATE
# works, so this was SQLite-only breakage (Render demo, local dev, the
# SQLite test suite). func.date(...) is the portable replacement used
# everywhere else in the codebase (12+ files) -- see
# calculations/availability.py's calculate_mtbf/calculate_mttr (first fixed)
# and the downtime-cause-taxonomy cycle's task-4b (remaining sites).
#
# The second-argument match is deliberately `\w*[Dd]ate\w*`, not a literal
# `Date`: task 4b independently found routes/downtime.py evading a literal
# match via aliased imports (`cast as sa_cast, Date as SADate`). A plain
# `cast(` + literal `Date` regex does not match `sa_cast(x, SADate)` -- the
# `\w*[Dd]ate\w*` wildcard closes that evasion (verified false-positive-free
# against the current tree: every typing.cast(...) site in backend/ was
# checked individually and none has "date" in its type argument).
# ---------------------------------------------------------------------------

import re  # noqa: E402

CAST_DATE_RE = re.compile(r"cast\([^,)]+,\s*\w*[Dd]ate\w*\s*\)")  # schema-guard: allow


def test_no_sql_cast_date():
    """cast(<col>, Date) must not appear in backend app code -- func.date(...) instead."""  # schema-guard: allow
    import pathlib

    backend_root = pathlib.Path(__file__).resolve().parent.parent
    marker = "# schema-guard: allow"

    offenders = []
    for py in backend_root.rglob("*.py"):
        if "alembic" in py.parts or ".venv" in py.parts or "tests" in py.parts:
            continue
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), start=1):
            if marker in line:
                continue
            if CAST_DATE_RE.search(line):
                offenders.append(f"{py.relative_to(backend_root)}:{lineno}")
    assert sorted(offenders) == []


@pytest.mark.parametrize(
    "snippet,should_match",
    [
        ("cast(QualityEntry.shift_date, Date)", True),
        ("sa_cast(DowntimeEntry.shift_date, SADate)", True),
        ("cast(x, SomeDateAlias)", True),
        ("typing.cast(str, value)", False),
        ("typing.cast(Optional[int], value)", False),
    ],
)
def test_cast_date_regex_catches_aliased_imports(snippet, should_match):
    """Self-test for CAST_DATE_RE: must catch both the literal `Date` form
    and the aliased `SADate` form (the exact evasion task 4b found in
    routes/downtime.py), while staying silent on unrelated typing.cast(...)
    calls whose type argument doesn't mention "date"."""
    assert bool(CAST_DATE_RE.search(snippet)) is should_match


# ---------------------------------------------------------------------------
# holds.py MariaDB portability: date_diff_days must EXECUTE on real MariaDB.
# Before the fix, holds.py used func.julianday(), which 500s on MariaDB with
# (1305, 'FUNCTION kpi_platform.julianday does not exist'). SQLite cannot
# reproduce that, so these run only in the mariadb-portability CI job.
# ---------------------------------------------------------------------------

from datetime import date, datetime, timedelta  # noqa: E402

from sqlalchemy import func, literal, text  # noqa: E402

from backend.db.sql_functions import date_diff_days  # noqa: E402


@requires_mariadb
def test_date_diff_days_executes_on_mariadb(mariadb_schema):
    """date_diff_days must run on MariaDB and return the fractional day delta."""
    start = datetime(2026, 6, 1, 0, 0, 0)
    end = datetime(2026, 6, 11, 0, 0, 0)  # exactly 10 days later
    session = SessionLocal()
    try:
        value = session.execute(select(date_diff_days(literal(end), literal(start)))).scalar()
    finally:
        session.close()
    assert value is not None
    assert abs(float(value) - 10.0) < 0.001


@requires_mariadb
def test_wip_aging_top_query_shape_executes_on_mariadb(mariadb_schema):
    """The get_top_aging_items query shape must execute on MariaDB without
    OperationalError, even against an empty HOLD_ENTRY table (proves every
    function/operator resolves; 1305 is raised at parse/exec time regardless
    of row count).

    Imports the PRODUCTION predicate rather than hand-copying the filter.
    An earlier revision of this test copied the shape, and when the route
    changed (ORDER BY date_diff_days + hold_status filter -> active_as_of +
    ORDER BY hold_date) the copy kept passing while asserting SQL production
    no longer builds -- a green gate proving nothing. Importing it means this
    job fails if the real predicate ever stops executing on MariaDB.

    SCOPE: execution only -- against an empty table `rows == []` holds
    however the predicate behaves. Row-level correctness is asserted by
    test_wip_aging_snapshot_boundary_is_exact_on_mariadb."""
    from backend.orm.work_order import WorkOrder
    from backend.calculations.wip_aging import HoldEntry, active_as_of

    session = SessionLocal()
    try:
        rows = (
            session.query(
                HoldEntry.work_order_id,
                WorkOrder.style_model,
                HoldEntry.hold_date,
            )
            .outerjoin(WorkOrder, HoldEntry.work_order_id == WorkOrder.work_order_id)
            .filter(active_as_of(datetime(2026, 6, 11).date()))
            .order_by(HoldEntry.hold_date.asc())
            .limit(10)
            .all()
        )
    finally:
        session.close()
    # Assert it EXECUTED, not that the table is empty: `mariadb_schema` is
    # module-scoped, so a `== []` assertion would silently depend on running
    # before mariadb_boundary_holds seeds its rows.
    assert isinstance(rows, list)


@requires_mariadb
def test_wip_aging_trend_avg_executes_on_mariadb(mariadb_schema):
    """The get_wip_aging_trend AVG(date_diff_days(DATE(...))) shape must
    execute on MariaDB. Empty table → AVG is NULL → scalar() is None, no
    OperationalError.

    Mirrors the route exactly, including the func.date() truncation inside
    the diff and the shared active_as_of predicate — DATE() and the
    NOT IN / IS NULL combination all have to resolve on MariaDB.

    SCOPE: this proves EXECUTION only. AVG over zero rows is NULL whatever
    date_diff_days returns, so this would pass even if the arithmetic were
    wrong on MariaDB. The correctness assertion lives in
    test_wip_aging_trend_average_is_correct_on_mariadb, which runs the same
    expression over seeded rows."""
    from backend.calculations.wip_aging import HoldEntry, active_as_of

    current_date = datetime(2026, 6, 11).date()
    session = SessionLocal()
    try:
        result = (
            session.query(func.avg(date_diff_days(current_date, func.date(HoldEntry.hold_date))))
            .filter(active_as_of(current_date))
            .scalar()
        )
    finally:
        session.close()
    # None (empty table) or a number (if seeded rows exist) both prove the
    # expression executed; see the boundary test for why this file cannot
    # assume an empty HOLD_ENTRY.
    assert result is None or float(result) >= 0


@pytest.fixture
def mariadb_boundary_holds(mariadb_schema):
    """Seed holds straddling the as-of boundary of 2026-06-11 on live MariaDB.

    Covers every arm of `active_as_of` with real rows, so the assertions
    below fail if MariaDB disagrees with SQLite about any of them:
      MDB-IN            opened at the last second of `as_of`      -> ACTIVE (age 0)
      MDB-AT-CUTOFF     resumed exactly AT the next midnight      -> ACTIVE (age 41)
      MDB-OUT           opened at the first second of the next day-> not yet open
      MDB-RESUMED       resumed during `as_of`                    -> already resumed
      MDB-SCRAPPED      terminal status, never resumed            -> not WIP
      MDB-PENDING-HOLD  hold only REQUESTED, never resumed        -> not WIP

    MDB-PENDING-HOLD and MDB-SCRAPPED both sit inside the active date range
    with a NULL resume_date, so they are excluded by status alone -- drop
    either from NON_WIP_HOLD_STATUSES and both the ID set and the average
    below move.
    """
    from backend.orm.client import Client
    from backend.orm.hold_entry import HoldStatus
    from backend.orm.work_order import WorkOrder
    from backend.routes.holds import HoldEntry

    holds = [
        ("MDB-IN", datetime(2026, 6, 11, 23, 59, 59), None, HoldStatus.ON_HOLD),
        ("MDB-AT-CUTOFF", datetime(2026, 5, 1, 9, 15), datetime(2026, 6, 12, 0, 0, 0), HoldStatus.RESUMED),
        ("MDB-OUT", datetime(2026, 6, 12, 0, 0, 0), None, HoldStatus.ON_HOLD),
        ("MDB-RESUMED", datetime(2026, 5, 1, 9, 15), datetime(2026, 6, 11, 10, 0), HoldStatus.RESUMED),
        ("MDB-SCRAPPED", datetime(2026, 5, 1, 9, 15), None, HoldStatus.SCRAPPED),
        ("MDB-PENDING-HOLD", datetime(2026, 5, 1, 9, 15), None, HoldStatus.PENDING_HOLD_APPROVAL),
    ]

    session = SessionLocal()
    try:
        session.add(Client(client_id="MDBBOUND", client_name="MariaDB Boundary"))
        session.flush()
        # HOLD_ENTRY.work_order_id is a real FK; InnoDB enforces it even where
        # SQLite would let an orphan through, so the parents come first.
        session.add_all(
            [
                WorkOrder(
                    work_order_id=f"WO-{hold_id}",
                    client_id="MDBBOUND",
                    style_model="MDB-STYLE",
                    planned_quantity=1,
                )
                for hold_id, _, _, _ in holds
            ]
        )
        session.flush()
        session.add_all(
            [
                HoldEntry(
                    hold_entry_id=hold_id,
                    client_id="MDBBOUND",
                    work_order_id=f"WO-{hold_id}",
                    hold_date=hold_date,
                    resume_date=resume_date,
                    hold_status=hold_status,
                    hold_reason_category="QUALITY",
                )
                for hold_id, hold_date, resume_date, hold_status in holds
            ]
        )
        session.commit()
        yield session
    finally:
        try:
            # A failed assertion query leaves the session pending-rollback;
            # without this the teardown DELETEs would fail too and the seeded
            # rows would survive into later tests.
            session.rollback()
            session.query(HoldEntry).filter(HoldEntry.client_id == "MDBBOUND").delete()
            session.query(WorkOrder).filter(WorkOrder.client_id == "MDBBOUND").delete()
            session.query(Client).filter(Client.client_id == "MDBBOUND").delete()
            session.commit()
        finally:
            # Nested so a failing teardown still returns the connection.
            session.close()


@requires_mariadb
def test_wip_aging_snapshot_boundary_is_exact_on_mariadb(mariadb_boundary_holds):
    """The as-of boundary must land identically on MariaDB and SQLite.

    This is the assertion the SQLite suite structurally cannot make: the
    cutoff is compared against DATETIME columns declared without fractional
    seconds, which is exactly where dialect-dependent rounding would bite.
    Includes the equality case on BOTH sides of the cutoff (a hold resumed
    exactly at the next midnight is still active), which is what separates
    `>=` from `>` — a test without it passes under either operator."""
    from backend.calculations.wip_aging import HoldEntry, active_as_of

    session = mariadb_boundary_holds
    # Scoped to this fixture's client, and REQUIRED rather than defensive:
    # `mariadb_schema` is module-scoped, so the schema is built once for the
    # whole file and HOLD_ENTRY rows survive between tests in it. An
    # unscoped read here would take whatever any other test left behind into
    # its ID set.
    active = (
        session.query(HoldEntry.hold_entry_id)
        .filter(active_as_of(datetime(2026, 6, 11).date()))
        .filter(HoldEntry.client_id == "MDBBOUND")
        .all()
    )
    assert sorted(row[0] for row in active) == ["MDB-AT-CUTOFF", "MDB-IN"]


@requires_mariadb
def test_wip_aging_trend_average_is_correct_on_mariadb(mariadb_boundary_holds):
    """The trend AVG must produce the same integer-day ages as the snapshot
    endpoints compute in Python.

    Over an EMPTY table AVG is NULL no matter what date_diff_days returns, so
    an empty-table test proves nothing about the arithmetic. Against the
    seeded rows the two active holds age 0 (opened on `as_of`) and 41
    (2026-05-01 -> 2026-06-11), so a correct MariaDB result is exactly 20.5.
    Without the func.date() truncation the times-of-day would drag this off
    the whole number."""
    from backend.calculations.wip_aging import HoldEntry, active_as_of

    current_date = datetime(2026, 6, 11).date()
    session = mariadb_boundary_holds
    result = (
        session.query(func.avg(date_diff_days(current_date, func.date(HoldEntry.hold_date))))
        .filter(active_as_of(current_date))
        .filter(HoldEntry.client_id == "MDBBOUND")  # see boundary test: don't depend on an empty table
        .scalar()
    )
    assert result is not None
    assert abs(float(result) - 20.5) < 0.001


# ---------------------------------------------------------------------------
# Audit-trail write path on real MariaDB. Everything above this point tested
# the audit feature only on SQLite; three of its column types had never once
# executed against MariaDB:
#   * `changes` is a JSON column written by a Core insert with a nested dict
#     (SQLite stores it as TEXT; MariaDB stores it as LONGTEXT + a JSON check
#     constraint, and pymysql serializes it on a different code path),
#   * `operation` is Enum(AuditOperation) — a native MariaDB ENUM, not the
#     VARCHAR + CHECK that SQLite emits,
#   * `occurred_at` binds a datetime that the writer strips to naive UTC.
# This repo's portability history is a list of exactly this shape reaching
# production (SQLite-only julianday(), Decimal-as-string, DateTime boundary
# rounding), so the write path is exercised end-to-end here, through the real
# production listeners rather than a re-implementation of them.
# ---------------------------------------------------------------------------


@pytest.fixture
def mariadb_audit_capture(mariadb_schema):
    """Register the REAL capture listeners for one test, then remove them.

    Mapper events attach process-wide, not per-Session, so leaving them on
    would make every later test in this module (which commits WORK_ORDER and
    HOLD_ENTRY rows — both audited) start writing AUDIT_ENTRY rows too.
    """
    from backend.audit.capture import register_audit_listener, unregister_audit_listener

    register_audit_listener()
    yield
    unregister_audit_listener()


@requires_mariadb
def test_audit_capture_round_trips_on_mariadb(mariadb_audit_capture):
    """A real audited INSERT, UPDATE and DELETE must execute on MariaDB and
    read back with their `changes` diff, enum operation and actor intact.

    Uses the production listeners (`register_audit_listener`) and a normal ORM
    session, so this fails if the real write path stops working on MariaDB for
    any reason — it is not a re-implementation that could drift green while
    the shipped code breaks (the failure mode
    test_wip_aging_top_query_shape_executes_on_mariadb documents).
    """
    from backend.audit.context import current_actor, set_actor
    from backend.orm.audit_entry import AuditEntry, AuditOperation
    from backend.orm.kpi_threshold import KPIThreshold

    threshold_id = "MDB-AUD-1"
    token = set_actor("MDB-USR-1", "mariadb_actor")
    session = SessionLocal()
    try:
        before = datetime.utcnow().replace(microsecond=0)

        session.add(KPIThreshold(threshold_id=threshold_id, kpi_key="oee", target_value=80.0))
        session.commit()

        threshold = session.query(KPIThreshold).filter_by(threshold_id=threshold_id).one()
        threshold.target_value = 91.5
        session.commit()

        session.delete(threshold)
        session.commit()

        rows = (
            session.query(AuditEntry)
            .filter(AuditEntry.table_name == "KPI_THRESHOLD", AuditEntry.record_pk == threshold_id)
            .order_by(AuditEntry.entry_id)
            .all()
        )

        # Enum(AuditOperation) — a native MariaDB ENUM — round-trips as the
        # Python enum member, in order.
        assert [r.operation for r in rows] == [
            AuditOperation.INSERT,
            AuditOperation.UPDATE,
            AuditOperation.DELETE,
        ]

        # JSON column: the nested {field: {old, new}} dict survives MariaDB's
        # LONGTEXT+JSON storage, with numbers still numbers (not the "0.00"
        # strings MariaDB has handed this codebase before).
        insert_changes = rows[0].changes
        assert insert_changes["kpi_key"] == {"old": None, "new": "oee"}
        assert insert_changes["target_value"] == {"old": None, "new": 80.0}
        assert rows[1].changes == {"target_value": {"old": 80.0, "new": 91.5}}
        assert isinstance(rows[1].changes["target_value"]["new"], float)
        # The DELETE snapshot is the widest JSON payload the writer produces:
        # every column, including the ones that were never set.
        delete_changes = rows[2].changes
        assert delete_changes["target_value"] == {"old": 91.5, "new": None}
        assert set(delete_changes) == {c.key for c in KPIThreshold.__table__.columns}

        # Actor snapshot columns.
        assert {r.actor_user_id for r in rows} == {"MDB-USR-1"}
        assert {r.actor_username for r in rows} == {"mariadb_actor"}

        # occurred_at binds naive UTC on pymysql too (MariaDB DATETIME has no
        # offset; the writer strips tzinfo explicitly so the contract is the
        # same on both dialects).
        after = datetime.utcnow()
        for row in rows:
            assert row.occurred_at.tzinfo is None
            assert before <= row.occurred_at <= after
    finally:
        try:
            session.rollback()
            session.query(AuditEntry).filter(AuditEntry.record_pk == threshold_id).delete()
            session.query(KPIThreshold).filter(KPIThreshold.threshold_id == threshold_id).delete()
            session.commit()
        finally:
            session.close()
            if token is not None:
                current_actor.reset(token)


# ---------------------------------------------------------------------------
# Audit-trail READ path on real MariaDB. The write path is covered above; the
# read endpoints (backend/routes/audit.py) filter a naive-UTC DateTime column
# by date range and this repo's portability failures have consistently lived
# exactly there (SQLite-only julianday(), a DateTime-vs-date boundary bug
# spanning 27 sites, Decimal serialising as "0.00" on MariaDB but as a number
# on SQLite). _end_of_day()'s tz-aware-vs-naive-bound choice was never
# executed against a live MariaDB before these tests.
#
# The PRODUCTION route functions are imported and called directly (not
# through TestClient/HTTP), matching this file's convention elsewhere
# (date_diff_days, active_as_of): a hand-copied query shape is exactly how
# the mariadb-portability job previously went green while the real code
# was broken (see test_wip_aging_top_query_shape_executes_on_mariadb).
# ---------------------------------------------------------------------------


@requires_mariadb
def test_audit_date_range_boundary_is_inclusive_on_mariadb(mariadb_schema):
    """An entry recorded late on the end date must be returned.

    Proves _end_of_day()'s "compare against the NEXT midnight" fix actually
    holds on MariaDB, not only on SQLite where a DateTime-vs-date mismatch
    has silently passed before (the 27-site boundary bug class).
    """
    from backend.orm.audit_entry import AuditEntry, AuditOperation
    from backend.routes.audit import list_audit_entries

    late = datetime(2026, 8, 11, 23, 59)  # naive UTC, matching what the writer stores
    record_pk = "HOLD-MDB-BOUNDARY"
    session = SessionLocal()
    try:
        session.add(
            AuditEntry(
                occurred_at=late,
                table_name="HOLD_ENTRY",
                record_pk=record_pk,
                operation=AuditOperation.INSERT,
                changes={},
            )
        )
        session.commit()

        result = list_audit_entries(
            table_name="HOLD_ENTRY",
            actor_user_id=None,
            client_id=None,
            start_date=late.date(),
            end_date=late.date(),
            limit=100,
            offset=0,
            db=session,
            _admin=None,
        )

        matches = [e for e in result.entries if e.record_pk == record_pk]
        assert len(matches) == 1
    finally:
        try:
            session.rollback()
            session.query(AuditEntry).filter(AuditEntry.record_pk == record_pk).delete()
            session.commit()
        finally:
            session.close()


@requires_mariadb
def test_audit_json_changes_round_trip_through_read_path_on_mariadb(mariadb_schema):
    """The `changes` JSON column must survive MariaDB's LONGTEXT+JSON storage
    AND the route's pydantic serialization with numeric values still numbers,
    not the "0.00"-as-string shape MariaDB has handed this codebase before
    (see the kpi-serialization Decimal-as-string fix). Read through the
    production route function, not a raw query, so a regression in either the
    ORM read or the response model is caught."""
    from backend.orm.audit_entry import AuditEntry, AuditOperation
    from backend.routes.audit import list_audit_entries

    record_pk = "HOLD-MDB-JSON"
    session = SessionLocal()
    try:
        session.add(
            AuditEntry(
                occurred_at=datetime(2026, 8, 11, 10, 0),
                actor_user_id="u-json",
                actor_username="json_actor",
                table_name="HOLD_ENTRY",
                record_pk=record_pk,
                operation=AuditOperation.UPDATE,
                changes={
                    "hold_status": {"old": "ON_HOLD", "new": "RELEASED"},
                    "target_value": {"old": 80.0, "new": 91.5},
                },
            )
        )
        session.commit()

        result = list_audit_entries(
            table_name="HOLD_ENTRY",
            actor_user_id=None,
            client_id=None,
            start_date=None,
            end_date=None,
            limit=100,
            offset=0,
            db=session,
            _admin=None,
        )

        matches = [e for e in result.entries if e.record_pk == record_pk]
        assert len(matches) == 1
        changes = matches[0].changes
        assert changes["hold_status"] == {"old": "ON_HOLD", "new": "RELEASED"}
        assert changes["target_value"] == {"old": 80.0, "new": 91.5}
        # The specific failure mode this repo has hit before: MariaDB handing
        # back a numeric-looking string instead of a JSON number.
        assert isinstance(changes["target_value"]["new"], float)
        assert isinstance(changes["target_value"]["old"], float)
    finally:
        try:
            session.rollback()
            session.query(AuditEntry).filter(AuditEntry.record_pk == record_pk).delete()
            session.commit()
        finally:
            session.close()


@requires_mariadb
def test_trail_started_at_is_none_empty_then_real_once_seeded_on_mariadb(mariadb_schema):
    """trail_started_at is the signal callers use to tell "nothing happened"
    apart from "before we were watching" (there is no backfill -- see
    routes/audit.py::get_entity_history). Both states must resolve correctly
    against a real MariaDB DATETIME column, not just SQLite's typing.

    Force-clears AUDIT_ENTRY immediately before the empty-table assertion
    rather than relying on no earlier test in this module-scoped schema
    having left rows behind -- that would make this test's correctness
    depend on file ordering instead of proving the empty case itself.
    """
    from backend.orm.audit_entry import AuditEntry, AuditOperation
    from backend.routes.audit import _trail_started_at

    session = SessionLocal()
    seeded_pk = "HOLD-MDB-TRAIL-START"
    try:
        session.query(AuditEntry).delete()
        session.commit()
        assert _trail_started_at(session) is None

        seeded_at = datetime(2026, 8, 11, 9, 0)
        session.add(
            AuditEntry(
                occurred_at=seeded_at,
                table_name="HOLD_ENTRY",
                record_pk=seeded_pk,
                operation=AuditOperation.INSERT,
                changes={},
            )
        )
        session.commit()

        assert _trail_started_at(session) == seeded_at
    finally:
        try:
            session.rollback()
            session.query(AuditEntry).filter(AuditEntry.record_pk == seeded_pk).delete()
            session.commit()
        finally:
            session.close()


@requires_mariadb
def test_get_entity_history_returns_seeded_entity_on_mariadb(mariadb_schema):
    """get_entity_history is the per-record read path -- the endpoint Project
    B's widget hits hardest -- and had never been executed against MariaDB;
    only list_audit_entries and _trail_started_at were covered above. Its
    query differs from list_audit_entries only by dropping the date-range
    filter, but that's a stated coverage goal, not an assumption to lean on.
    """
    from backend.orm.audit_entry import AuditEntry, AuditOperation
    from backend.routes.audit import get_entity_history

    record_pk = "HOLD-MDB-HISTORY"
    other_pk = "HOLD-MDB-HISTORY-OTHER"
    session = SessionLocal()
    try:
        session.add_all(
            [
                AuditEntry(
                    occurred_at=datetime(2026, 8, 11, 8, 0),
                    table_name="HOLD_ENTRY",
                    record_pk=record_pk,
                    operation=AuditOperation.INSERT,
                    changes={"hold_status": {"old": None, "new": "ON_HOLD"}},
                ),
                AuditEntry(
                    occurred_at=datetime(2026, 8, 11, 9, 0),
                    table_name="HOLD_ENTRY",
                    record_pk=record_pk,
                    operation=AuditOperation.UPDATE,
                    changes={"hold_status": {"old": "ON_HOLD", "new": "RELEASED"}},
                ),
                # A different record, same table: proves the filter is
                # scoped to record_pk, not just returning everything.
                AuditEntry(
                    occurred_at=datetime(2026, 8, 11, 9, 30),
                    table_name="HOLD_ENTRY",
                    record_pk=other_pk,
                    operation=AuditOperation.INSERT,
                    changes={},
                ),
            ]
        )
        session.commit()

        result = get_entity_history(
            table_name="HOLD_ENTRY",
            record_pk=record_pk,
            limit=100,
            offset=0,
            db=session,
            _admin=None,
        )

        assert result.total == 2
        assert {e.record_pk for e in result.entries} == {record_pk}
        assert [e.operation for e in result.entries] == [AuditOperation.UPDATE, AuditOperation.INSERT]
        assert result.trail_started_at is not None
    finally:
        try:
            session.rollback()
            session.query(AuditEntry).filter(AuditEntry.record_pk.in_([record_pk, other_pk])).delete(
                synchronize_session=False
            )
            session.commit()
        finally:
            session.close()


@requires_mariadb
def test_audit_newest_first_holds_for_entries_in_the_same_second_on_mariadb(mariadb_schema):
    """The newest-first contract must survive MariaDB's whole-second DATETIME.

    ``AuditEntry.occurred_at`` is a plain ``DateTime``, which MariaDB renders
    as DATETIME with NO fractional-seconds precision: 20 rows written with 20
    distinct microsecond values collapse to ONE distinct stored value. With
    ``ORDER BY occurred_at DESC`` alone that makes the row order unspecified,
    and in practice InnoDB returns the ties in insertion order -- i.e. the
    trail comes back OLDEST-first, the exact reverse of what both endpoints
    document. An admin reading a hold's history would conclude the FIRST
    change was the last one.

    Same-second writes are the normal case, not an edge case: one flush emits
    several AUDIT_ENTRY rows and a CSV upload emits hundreds per second.

    ``test_get_entity_history_returns_seeded_entity_on_mariadb`` above cannot
    see this -- its two entries are an hour apart, so ``occurred_at`` alone is
    already a total order there. This one writes them in the SAME second, which
    is the only shape that exercises the tiebreaker, and it goes through the
    production route functions so it fails if either endpoint loses it.

    Each row is committed in its own transaction so they are genuinely written
    in sequence, the way the capture engine writes them.

    THE ROWS OF UNRELATED NOISE ARE LOAD-BEARING, not scene-setting. Against a
    near-empty AUDIT_ENTRY the optimizer answers ``ORDER BY occurred_at DESC``
    with a reverse scan of ``ix_AUDIT_ENTRY_occurred_at``, whose leaf entries
    are (occurred_at, PK) -- so the ties come back entry_id-descending by
    accident and the bug hides. Once the table looks like production (the
    entity index becomes the selective one), the plan becomes a ref lookup +
    filesort, and the filesort returns the ties in the order it read them:
    OLDEST first. Measured on mariadb:11.4: with the tiebreaker removed and
    50 noise rows present, both endpoints returned
    ['actor-first', 'actor-second', 'actor-third'] -- fully reversed. The
    filesort assertion below is a tripwire so a future optimizer change cannot
    turn this test vacuously green without saying so.
    """
    from backend.orm.audit_entry import AuditEntry, AuditOperation
    from backend.routes.audit import get_entity_history, list_audit_entries

    record_pk = "HOLD-MDB-SAMESECOND"
    noise_pks = [f"NOISE-SAMESECOND-{i}" for i in range(50)]
    session = SessionLocal()
    try:
        noise_base = datetime(2026, 1, 1, 0, 0, 0)
        session.add_all(
            [
                AuditEntry(
                    occurred_at=noise_base + timedelta(seconds=i),
                    table_name="WORK_ORDER",
                    record_pk=pk,
                    operation=AuditOperation.UPDATE,
                    changes={},
                )
                for i, pk in enumerate(noise_pks)
            ]
        )
        session.commit()

        # One timestamp, three rows: MariaDB stores all three identically.
        tied_at = datetime(2026, 8, 11, 14, 30, 15)
        for actor in ("actor-first", "actor-second", "actor-third"):
            session.add(
                AuditEntry(
                    occurred_at=tied_at,
                    actor_user_id=actor,
                    table_name="HOLD_ENTRY",
                    record_pk=record_pk,
                    operation=AuditOperation.UPDATE,
                    changes={},
                )
            )
            session.commit()

        # The stored values really are indistinguishable — if MariaDB ever
        # started keeping microseconds here, the ordering assertions below
        # would stop testing the tiebreaker and quietly pass for free.
        distinct = session.query(func.count(func.distinct(AuditEntry.occurred_at))).filter(
            AuditEntry.record_pk == record_pk
        )
        assert distinct.scalar() == 1

        # Tripwire: the ordering below only exercises the tiebreaker while the
        # server is actually SORTING. If this ever stops being a filesort, the
        # assertions pass for free and this test must be re-shaped.
        plan = session.execute(
            text(
                "EXPLAIN SELECT * FROM AUDIT_ENTRY WHERE table_name = :t "
                "AND record_pk = :pk ORDER BY occurred_at DESC LIMIT 100"
            ),
            {"t": "HOLD_ENTRY", "pk": record_pk},
        ).first()
        assert "Using filesort" in (plan[-1] or ""), (
            "the entity-history query is no longer sorted by the server (plan: "
            f"{plan[-1]!r}); it is answered in index order, so the same-second "
            "assertions below no longer prove the entry_id tiebreaker exists"
        )

        history = get_entity_history(
            table_name="HOLD_ENTRY",
            record_pk=record_pk,
            limit=100,
            offset=0,
            db=session,
            _admin=None,
        )
        assert [e.actor_user_id for e in history.entries] == ["actor-third", "actor-second", "actor-first"]

        listing = list_audit_entries(
            table_name="HOLD_ENTRY",
            actor_user_id=None,
            client_id=None,
            start_date=None,
            end_date=None,
            limit=100,
            offset=0,
            db=session,
            _admin=None,
        )
        ours = [e.actor_user_id for e in listing.entries if e.record_pk == record_pk]
        assert ours == ["actor-third", "actor-second", "actor-first"]

        # Offset paging over a tied set must be stable, not just ordered:
        # page 2 of 1 is the middle row, never a repeat of page 1.
        page_two = get_entity_history(
            table_name="HOLD_ENTRY",
            record_pk=record_pk,
            limit=1,
            offset=1,
            db=session,
            _admin=None,
        )
        assert [e.actor_user_id for e in page_two.entries] == ["actor-second"]
        assert page_two.total == 3
    finally:
        try:
            session.rollback()
            session.query(AuditEntry).filter(AuditEntry.record_pk.in_([record_pk] + noise_pks)).delete(
                synchronize_session=False
            )
            session.commit()
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Hold-status-history lookup on real MariaDB (Cycle 4 PR-C1, Task 6).
# `active_as_of` (backend/calculations/wip_aging.py) was rewritten in Task 4
# to read a hold's status AS OF a past date from HOLD_STATUS_TRANSITION via a
# correlated scalar subquery (ORDER BY transitioned_at DESC, transition_id
# DESC LIMIT 1), rather than trusting HOLD_ENTRY's CURRENT status. SQLite
# cannot catch this repo's recurring bug class: holds.py's func.julianday()
# reached production and 500'd on MariaDB while the whole SQLite suite stayed
# green (see the top-of-file comment on date_diff_days). The SQLite-side
# equivalents of these tests live in
# backend/tests/test_calculations/test_hold_status_history.py.
# ---------------------------------------------------------------------------


@pytest.fixture
def mariadb_hold_history(mariadb_schema):
    """Seed holds + explicit HOLD_STATUS_TRANSITION rows on live MariaDB,
    mirroring `hold_with_history` + `same_second_hold` from
    test_calculations/test_hold_status_history.py.

    MariaDB DATETIME stores WHOLE SECONDS -- every timestamp below is built
    without a microsecond component (matches every other fixture in this
    file). `same_second`'s pair is the one whose entire point is the
    transition_id tiebreak that whole-second storage forces: two transitions
    sharing one instant, inserted as separate rows so they get distinct
    auto-assigned transition_ids -- asserted explicitly below so a future
    change that collapses them into one INSERT can't silently defeat the test.
    """
    from backend.orm.client import Client
    from backend.orm.hold_entry import HoldEntry, HoldStatus
    from backend.orm.hold_status_transition import HoldStatusTransition
    from backend.orm.work_order import WorkOrder

    session = SessionLocal()
    try:
        session.add(Client(client_id="MDBHIST", client_name="MariaDB Hold History"))
        session.flush()

        session.add_all(
            [
                WorkOrder(
                    work_order_id=f"WO-MDBHIST-{suffix}",
                    client_id="MDBHIST",
                    style_model="MDB-HIST-STYLE",
                    planned_quantity=1,
                )
                for suffix in ("PENDING", "CANCELLED", "SAMESEC")
            ]
        )
        session.flush()

        # pending_then_approved: PENDING_HOLD_APPROVAL through day 4, approved
        # into ON_HOLD at 10:00 on day 5 -- NOT active WIP on 2026-03-03. Its
        # presence is what proves the day-3 assertion below is a real filter,
        # not an unfiltered table that happens to contain one row.
        pending_then_approved = HoldEntry(
            hold_entry_id="MDBHIST-PENDING",
            client_id="MDBHIST",
            work_order_id="WO-MDBHIST-PENDING",
            hold_status=HoldStatus.ON_HOLD,
            hold_date=datetime(2026, 3, 1, 8, 0, 0),
            resume_date=None,
            hold_reason_category="QUALITY",
        )
        # held_then_cancelled: ON_HOLD from day 1, cancelled at 11:00 on day 8
        # -- active WIP on 2026-03-03, the only member of the expected set.
        held_then_cancelled = HoldEntry(
            hold_entry_id="MDBHIST-CANCELLED",
            client_id="MDBHIST",
            work_order_id="WO-MDBHIST-CANCELLED",
            hold_status=HoldStatus.CANCELLED,
            hold_date=datetime(2026, 3, 1, 9, 0, 0),
            resume_date=None,
            hold_reason_category="QUALITY",
        )
        # same_second: current status is ON_HOLD -- the OPPOSITE of the
        # correct as-of answer (CANCELLED, per the transition chain below).
        # If the transition_id tiebreak is broken, COALESCE's fallback would
        # land on (or the subquery could resolve to) ON_HOLD, which is active
        # WIP -- masking the bug instead of catching it.
        #
        # hold_date is 2026-03-04 (the SAME day as its transitions), not
        # 2026-03-01 like the other two holds. All three holds share one
        # table across all three tests below (unlike the SQLite fixtures,
        # which isolate same_second_hold in its own fixture). Dating the hold
        # itself to day 4 excludes it from day 3 via the *hold_date* arm of
        # active_as_of, independent of status, so the ON_HOLD "opposite" trap
        # above stays intact for the day-5 same-second assertion. This keeps
        # the hold out of that day's scope regardless of any status query logic.
        same_second_hold = HoldEntry(
            hold_entry_id="MDBHIST-SAMESEC",
            client_id="MDBHIST",
            work_order_id="WO-MDBHIST-SAMESEC",
            hold_status=HoldStatus.ON_HOLD,
            hold_date=datetime(2026, 3, 4, 6, 0, 0),
            resume_date=None,
            hold_reason_category="QUALITY",
        )
        session.add_all([pending_then_approved, held_then_cancelled, same_second_hold])
        session.flush()

        session.add_all(
            [
                HoldStatusTransition(
                    hold_entry_id="MDBHIST-PENDING",
                    client_id="MDBHIST",
                    from_status=None,
                    to_status="PENDING_HOLD_APPROVAL",
                    transitioned_at=datetime(2026, 3, 1, 8, 0, 0),
                ),
                HoldStatusTransition(
                    hold_entry_id="MDBHIST-PENDING",
                    client_id="MDBHIST",
                    from_status="PENDING_HOLD_APPROVAL",
                    to_status="ON_HOLD",
                    transitioned_at=datetime(2026, 3, 5, 10, 0, 0),
                ),
                HoldStatusTransition(
                    hold_entry_id="MDBHIST-CANCELLED",
                    client_id="MDBHIST",
                    from_status=None,
                    to_status="ON_HOLD",
                    transitioned_at=datetime(2026, 3, 1, 9, 0, 0),
                ),
                HoldStatusTransition(
                    hold_entry_id="MDBHIST-CANCELLED",
                    client_id="MDBHIST",
                    from_status="ON_HOLD",
                    to_status="CANCELLED",
                    transitioned_at=datetime(2026, 3, 8, 11, 0, 0),
                ),
            ]
        )
        session.flush()

        # The same-second pair: two separate INSERTs sharing one
        # `transitioned_at`, so MariaDB's whole-second DATETIME stores them
        # identically and only the auto-assigned transition_id can order them.
        same_instant = datetime(2026, 3, 4, 12, 0, 0)
        first = HoldStatusTransition(
            hold_entry_id="MDBHIST-SAMESEC",
            client_id="MDBHIST",
            from_status=None,
            to_status="ON_HOLD",
            transitioned_at=same_instant,
        )
        session.add(first)
        session.flush()
        second = HoldStatusTransition(
            hold_entry_id="MDBHIST-SAMESEC",
            client_id="MDBHIST",
            from_status="ON_HOLD",
            to_status="CANCELLED",
            transitioned_at=same_instant,
        )
        session.add(second)
        session.flush()
        assert first.transition_id != second.transition_id

        session.commit()

        ids = {
            "pending_then_approved": "MDBHIST-PENDING",
            "held_then_cancelled": "MDBHIST-CANCELLED",
            "same_second": "MDBHIST-SAMESEC",
        }
        yield session, ids
    finally:
        try:
            # A failed assertion query leaves the session pending-rollback;
            # without this the teardown DELETEs would fail too and the seeded
            # rows would survive into later tests (mariadb_boundary_holds's
            # own teardown comment documents the same hazard).
            session.rollback()
            session.query(HoldStatusTransition).filter(HoldStatusTransition.client_id == "MDBHIST").delete()
            session.query(HoldEntry).filter(HoldEntry.client_id == "MDBHIST").delete()
            session.query(WorkOrder).filter(WorkOrder.client_id == "MDBHIST").delete()
            session.query(Client).filter(Client.client_id == "MDBHIST").delete()
            session.commit()
        finally:
            session.close()


@requires_mariadb
def test_active_as_of_history_lookup_executes_on_mariadb(mariadb_hold_history):
    """The correlated scalar subquery with ORDER BY + LIMIT must execute on
    MariaDB, not just SQLite."""
    from backend.calculations.wip_aging import HoldEntry, active_as_of

    session, ids = mariadb_hold_history

    # Scoped to this fixture's client for the same reason the boundary test
    # above scopes its query (lines 510-514): `mariadb_schema` is
    # module-scoped, so rows from other tests in this file survive between
    # tests, and an unscoped read here would take whatever they left behind
    # into this equality assertion.
    active = {
        h.hold_entry_id
        for h in session.query(HoldEntry)
        .filter(active_as_of(date(2026, 3, 3)))
        .filter(HoldEntry.client_id == "MDBHIST")
        .all()
    }

    assert active == {ids["held_then_cancelled"]}


@requires_mariadb
def test_same_second_transitions_resolve_on_mariadb(mariadb_hold_history):
    """MariaDB DATETIME truncates to whole seconds, so the tie-break on
    transition_id is load-bearing here in a way it is not on SQLite."""
    from backend.calculations.wip_aging import HoldEntry, active_as_of

    session, ids = mariadb_hold_history

    active = {h.hold_entry_id for h in session.query(HoldEntry).filter(active_as_of(date(2026, 3, 5))).all()}

    assert ids["same_second"] not in active


@requires_mariadb
def test_top_n_with_history_predicate_uses_index_on_mariadb(mariadb_hold_history):
    """Explains the query built WITH active_as_of, not a hand-written string --
    a literal SQL string would pass regardless of what the predicate does.

    The assertion is scoped to the PRIMARY (outer HOLD_ENTRY) row of the
    plan, not every row EXPLAIN returns. Verified against live mariadb:11.4:
    once any hold has 2+ HOLD_STATUS_TRANSITION rows -- which the same-second
    pair in `mariadb_hold_history` requires -- the DEPENDENT SUBQUERY row
    also reports "Using filesort", but that is a real, bounded, per-hold sort
    over at most a couple of candidate rows. MariaDB's classic EXPLAIN format
    puts `table` and `Extra` in separate columns, so an unscoped "Using filesort"
    check would fire on the subquery's per-hold sort as well -- unrelated to
    what `active_as_of`'s docstring promises callers ("index-assisted ORDER BY
    ... LIMIT instead of loading every candidate hold into memory"), which is
    about the OUTER top-N/aggregate query never degrading into a full HOLD_ENTRY
    scan. That promise is what the PRIMARY row's plan actually proves, and it
    never showed a filesort in any fixture shape tried here.
    """
    from backend.calculations.wip_aging import HoldEntry, active_as_of

    session, _ = mariadb_hold_history

    query = (
        session.query(HoldEntry.hold_entry_id)
        .filter(active_as_of(date(2026, 3, 10)))
        .order_by(HoldEntry.hold_date)
        .limit(5)
    )
    compiled = query.statement.compile(session.bind, compile_kwargs={"literal_binds": True})
    plan = session.execute(text(f"EXPLAIN {compiled}")).fetchall()

    outer_rows = [row for row in plan if row.table == "HOLD_ENTRY"]
    assert len(outer_rows) == 1
    assert "Using filesort" not in (outer_rows[0].Extra or "")


# ---------------------------------------------------------------------------
# Cycle 4 PR-C1b Task 2: tier 2 (earliest-transition from_status fallback) on
# live MariaDB. Task 1 proved this tier on SQLite only. SQLite's
# transition_id is INTEGER PRIMARY KEY AUTOINCREMENT (the ROWID), so
# insertion order and ascending transition_id coincide by construction and
# same-timestamp ties already come back ascending from B-tree physical
# order -- no SQLite fixture can defeat the tie-break. InnoDB (MariaDB) has
# no such guarantee for same-timestamp rows without an explicit ORDER BY, so
# the tie-break's load-bearing-ness can only be shown here.
# ---------------------------------------------------------------------------


@pytest.fixture
def mariadb_earliest_fallback(mariadb_schema):
    """Mirrors `hold_with_only_later_history` from
    test_calculations/test_hold_status_history.py against live MariaDB.

    Two client-scoped holds, no transition before the 2026-03-03 cutoff
    (2026-03-04 00:00:00) -- tier 1 is empty for both, so tier 2 alone
    decides, and it disagrees with current status in both directions:
      MDBEARLY-CANCELLED  current CANCELLED, single transition 2026-08-08
                          from_status=ON_HOLD   -> WAS on hold on 2026-03-03
      MDBEARLY-REOPENED   current ON_HOLD,     single transition 2026-08-08
                          from_status=CANCELLED -> WAS cancelled on 2026-03-03
    """
    from backend.orm.client import Client
    from backend.orm.hold_entry import HoldEntry, HoldStatus
    from backend.orm.hold_status_transition import HoldStatusTransition
    from backend.orm.work_order import WorkOrder

    session = SessionLocal()
    try:
        session.add(Client(client_id="MDBEARLY", client_name="MariaDB Earliest Fallback"))
        session.flush()

        session.add_all(
            [
                WorkOrder(
                    work_order_id=f"WO-MDBEARLY-{suffix}",
                    client_id="MDBEARLY",
                    style_model="MDB-EARLY-STYLE",
                    planned_quantity=1,
                )
                for suffix in ("CANCELLED", "REOPENED")
            ]
        )
        session.flush()

        later_cancelled = HoldEntry(
            hold_entry_id="MDBEARLY-CANCELLED",
            client_id="MDBEARLY",
            work_order_id="WO-MDBEARLY-CANCELLED",
            hold_status=HoldStatus.CANCELLED,
            hold_date=datetime(2026, 2, 1, 8, 0, 0),
            resume_date=None,
            hold_reason_category="QUALITY",
        )
        later_reopened = HoldEntry(
            hold_entry_id="MDBEARLY-REOPENED",
            client_id="MDBEARLY",
            work_order_id="WO-MDBEARLY-REOPENED",
            hold_status=HoldStatus.ON_HOLD,
            hold_date=datetime(2026, 2, 1, 9, 0, 0),
            resume_date=None,
            hold_reason_category="QUALITY",
        )
        session.add_all([later_cancelled, later_reopened])
        session.flush()

        session.add_all(
            [
                HoldStatusTransition(
                    hold_entry_id="MDBEARLY-CANCELLED",
                    client_id="MDBEARLY",
                    from_status="ON_HOLD",
                    to_status="CANCELLED",
                    transitioned_at=datetime(2026, 8, 8, 10, 0, 0),
                ),
                HoldStatusTransition(
                    hold_entry_id="MDBEARLY-REOPENED",
                    client_id="MDBEARLY",
                    from_status="CANCELLED",
                    to_status="ON_HOLD",
                    transitioned_at=datetime(2026, 8, 8, 11, 0, 0),
                ),
            ]
        )
        session.flush()
        session.commit()

        ids = {
            "later_cancelled": "MDBEARLY-CANCELLED",
            "later_reopened": "MDBEARLY-REOPENED",
        }
        yield session, ids
    finally:
        try:
            # A failed assertion query leaves the session pending-rollback;
            # without this the teardown DELETEs would fail too and the seeded
            # rows would survive into later tests (mariadb_boundary_holds's
            # own teardown comment documents the same hazard).
            session.rollback()
            session.query(HoldStatusTransition).filter(HoldStatusTransition.client_id == "MDBEARLY").delete()
            session.query(HoldEntry).filter(HoldEntry.client_id == "MDBEARLY").delete()
            session.query(WorkOrder).filter(WorkOrder.client_id == "MDBEARLY").delete()
            session.query(Client).filter(Client.client_id == "MDBEARLY").delete()
            session.commit()
        finally:
            session.close()


@requires_mariadb
def test_earliest_from_status_fallback_executes_on_mariadb(mariadb_earliest_fallback):
    """Tier 2 adds a second correlated subquery with ORDER BY + LIMIT; it must
    execute and resolve correctly on MariaDB, not only SQLite.

    Scoped to this fixture's client (lines 510-514's convention): `mariadb_schema`
    is module-scoped, so rows from other tests in this file survive between
    tests, and an unscoped read here would take whatever they left behind
    into this equality assertion.
    """
    from backend.calculations.wip_aging import HoldEntry, active_as_of

    session, ids = mariadb_earliest_fallback

    active = {
        h.hold_entry_id
        for h in session.query(HoldEntry)
        .filter(active_as_of(date(2026, 3, 3)))
        .filter(HoldEntry.client_id == "MDBEARLY")
        .all()
    }

    assert active == {ids["later_cancelled"]}


@requires_mariadb
def test_three_tier_predicate_keeps_outer_index_on_mariadb(mariadb_earliest_fallback):
    """Two correlated subqueries must not cost the outer top-N its index.

    Explains the query built WITH active_as_of, not a hand-written SQL
    string -- a literal SQL string would pass regardless of what the
    predicate does. Unscoped by client_id like its tier-1 sibling
    (test_top_n_with_history_predicate_uses_index_on_mariadb): this is a
    structural check of the plan shape, not of row content.
    """
    from backend.calculations.wip_aging import HoldEntry, active_as_of

    session, _ = mariadb_earliest_fallback

    query = (
        session.query(HoldEntry.hold_entry_id)
        .filter(active_as_of(date(2026, 3, 10)))
        .order_by(HoldEntry.hold_date)
        .limit(5)
    )
    compiled = query.statement.compile(session.bind, compile_kwargs={"literal_binds": True})
    plan = session.execute(text(f"EXPLAIN {compiled}")).fetchall()

    outer = [row for row in plan if row.table == "HOLD_ENTRY"]
    assert len(outer) == 1
    assert "Using filesort" not in str(outer[0].Extra or "")


@requires_mariadb
def test_tier_two_subquery_uses_composite_index_on_mariadb(mariadb_earliest_fallback):
    """backend/orm/hold_status_transition.py:26-31 claims
    ix_hold_transition_hold_asof (hold_entry_id, transitioned_at,
    transition_id) already serves tier 2's ascending scan, so no dedicated
    index is needed for it. Nothing asserted that until now:
    test_three_tier_predicate_keeps_outer_index_on_mariadb only looks at the
    PRIMARY (outer HOLD_ENTRY) row and deliberately ignores both DEPENDENT
    SUBQUERY rows.

    `active_as_of`'s COALESCE has tier 1 (status_as_of, descending) as its
    first argument and tier 2 (status_before_history, ascending) as its
    second, so MariaDB's classic EXPLAIN consistently numbers tier 1's
    DEPENDENT SUBQUERY row `id=2` and tier 2's `id=3` (verified against live
    mariadb:11.4 with this fixture's exact data/as_of: id=2 comes back
    type=range key=ix_HOLD_STATUS_TRANSITION_transitioned_at, id=3 comes
    back type=ref key=ix_hold_transition_hold_asof, ref=<...>.hold_entry_id).
    That id-ordering is an artifact of the optimizer, not a documented
    contract, so this assertion does not lean on it: it identifies the
    tier-2 row structurally instead -- the DEPENDENT SUBQUERY row whose
    access `type` is `ref` on `HOLD_ENTRY.hold_entry_id` (an equality
    lookup, which is what an ascending per-hold LIMIT 1 scan against the
    composite index produces; tier 1's descending scan came back as a
    `range` scan on the single-column transitioned_at index instead in the
    same plan, so `type` reliably tells the two apart here). Falls back to
    the ambiguity-tolerant check the task allows if that ever stops holding:
    at least one HOLD_STATUS_TRANSITION row uses the composite index and
    none does a full ALL scan.
    """
    from backend.calculations.wip_aging import HoldEntry, active_as_of

    session, _ = mariadb_earliest_fallback

    query = (
        session.query(HoldEntry.hold_entry_id)
        .filter(active_as_of(date(2026, 3, 10)))
        .order_by(HoldEntry.hold_date)
        .limit(5)
    )
    compiled = query.statement.compile(session.bind, compile_kwargs={"literal_binds": True})
    plan = session.execute(text(f"EXPLAIN {compiled}")).fetchall()

    subquery_rows = [row for row in plan if row.table == "HOLD_STATUS_TRANSITION"]
    assert len(subquery_rows) == 2
    assert not any(row.type == "ALL" for row in subquery_rows)

    ref_rows = [row for row in subquery_rows if row.type == "ref" and (row.ref or "").endswith("hold_entry_id")]
    if len(ref_rows) == 1:
        assert ref_rows[0].key == "ix_hold_transition_hold_asof"
    else:
        # Ambiguous which row is tier 2 -- fall back to the weaker but still
        # meaningful claim: the composite index is in play for this table
        # at all, and nothing degraded into a full scan.
        assert any(row.key == "ix_hold_transition_hold_asof" for row in subquery_rows)


@pytest.fixture
def mariadb_earliest_tie_break(mariadb_schema):
    """A single client-scoped hold with TWO transitions sharing one
    whole-second instant, both at or after the cutoff, with OPPOSITE
    `from_status` -- proving tier 2's `transition_id.asc()` tie-break is
    load-bearing on MariaDB, the way `mariadb_hold_history`'s same-second
    pair already does for tier 1.

    MDBEARTIE-TIE: current status CANCELLED, hold_date well before the
    2026-03-03 cutoff so tier 1 finds nothing (no transition precedes it).
    Two transitions at 2026-08-10 10:00:00 (no microseconds -- MariaDB
    DATETIME truncates to whole seconds), inserted as separate rows so they
    get distinct auto-assigned transition_ids: first-inserted from_status
    is ON_HOLD, second-inserted is CANCELLED. Correct tie-break
    (transitioned_at ASC, transition_id ASC) picks the first-inserted row,
    so the hold reads active; the opposite pick would read inactive.
    """
    from backend.orm.client import Client
    from backend.orm.hold_entry import HoldEntry, HoldStatus
    from backend.orm.hold_status_transition import HoldStatusTransition
    from backend.orm.work_order import WorkOrder

    session = SessionLocal()
    try:
        session.add(Client(client_id="MDBEARTIE", client_name="MariaDB Earliest Tie-Break"))
        session.flush()
        session.add(
            WorkOrder(
                work_order_id="WO-MDBEARTIE-TIE",
                client_id="MDBEARTIE",
                style_model="MDB-EARTIE-STYLE",
                planned_quantity=1,
            )
        )
        session.flush()

        hold = HoldEntry(
            hold_entry_id="MDBEARTIE-TIE",
            client_id="MDBEARTIE",
            work_order_id="WO-MDBEARTIE-TIE",
            hold_status=HoldStatus.CANCELLED,
            hold_date=datetime(2026, 2, 1, 8, 0, 0),
            resume_date=None,
            hold_reason_category="QUALITY",
        )
        session.add(hold)
        session.flush()

        same_instant = datetime(2026, 8, 10, 10, 0, 0)
        first = HoldStatusTransition(
            hold_entry_id="MDBEARTIE-TIE",
            client_id="MDBEARTIE",
            from_status="ON_HOLD",
            to_status="CANCELLED",
            transitioned_at=same_instant,
        )
        session.add(first)
        session.flush()
        second = HoldStatusTransition(
            hold_entry_id="MDBEARTIE-TIE",
            client_id="MDBEARTIE",
            from_status="CANCELLED",
            to_status="ON_HOLD",
            transitioned_at=same_instant,
        )
        session.add(second)
        session.flush()
        assert first.transition_id != second.transition_id

        session.commit()
        yield session, "MDBEARTIE-TIE"
    finally:
        try:
            session.rollback()
            session.query(HoldStatusTransition).filter(HoldStatusTransition.client_id == "MDBEARTIE").delete()
            session.query(HoldEntry).filter(HoldEntry.client_id == "MDBEARTIE").delete()
            session.query(WorkOrder).filter(WorkOrder.client_id == "MDBEARTIE").delete()
            session.query(Client).filter(Client.client_id == "MDBEARTIE").delete()
            session.commit()
        finally:
            session.close()


@requires_mariadb
def test_earliest_tier_same_second_transitions_break_tie_by_insertion_order_on_mariadb(mariadb_earliest_tie_break):
    """Tier 2's `transition_id.asc()` tie-break, proven on MariaDB rather
    than SQLite (see the module comment above this fixture for why SQLite
    structurally cannot make this assertion).

    This test is also the harness for a deliberate mutation experiment
    (Cycle 4 PR-C1b Task 2): with `HoldStatusTransition.transition_id.asc()`
    temporarily deleted from tier 2's `order_by` in
    backend/calculations/wip_aging.py, this test was re-run against this
    same live MariaDB fixture and the result recorded in
    .superpowers/sdd/2026-08-14-hold-history-earliest-fallback/task-2-report.md
    before the clause was restored.
    """
    from backend.calculations.wip_aging import HoldEntry, active_as_of

    session, hold_id = mariadb_earliest_tie_break

    active = {
        h.hold_entry_id
        for h in session.query(HoldEntry)
        .filter(active_as_of(date(2026, 3, 3)))
        .filter(HoldEntry.client_id == "MDBEARTIE")
        .all()
    }

    assert active == {hold_id}
