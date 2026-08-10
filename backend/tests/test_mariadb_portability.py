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
    ATTENDANCE_HOUR_ALLOCATION, bringing the total to 58).
    """
    from backend.orm import register_all_models

    register_all_models()
    assert len(Base.metadata.tables) == 58


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

from datetime import datetime  # noqa: E402

from sqlalchemy import func, literal  # noqa: E402

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
    changed (ORDER BY date_diff_days + hold_status filter -> _active_as_of +
    ORDER BY hold_date) the copy kept passing while asserting SQL production
    no longer builds -- a green gate proving nothing. Importing it means this
    job fails if the real predicate ever stops executing on MariaDB.

    SCOPE: execution only -- against an empty table `rows == []` holds
    however the predicate behaves. Row-level correctness is asserted by
    test_wip_aging_snapshot_boundary_is_exact_on_mariadb."""
    from backend.orm.work_order import WorkOrder
    from backend.routes.holds import HoldEntry, _active_as_of

    session = SessionLocal()
    try:
        rows = (
            session.query(
                HoldEntry.work_order_id,
                WorkOrder.style_model,
                HoldEntry.hold_date,
            )
            .outerjoin(WorkOrder, HoldEntry.work_order_id == WorkOrder.work_order_id)
            .filter(_active_as_of(datetime(2026, 6, 11).date()))
            .order_by(HoldEntry.hold_date.asc())
            .limit(10)
            .all()
        )
    finally:
        session.close()
    assert rows == []


@requires_mariadb
def test_wip_aging_trend_avg_executes_on_mariadb(mariadb_schema):
    """The get_wip_aging_trend AVG(date_diff_days(DATE(...))) shape must
    execute on MariaDB. Empty table → AVG is NULL → scalar() is None, no
    OperationalError.

    Mirrors the route exactly, including the func.date() truncation inside
    the diff and the shared _active_as_of predicate — DATE() and the
    NOT IN / IS NULL combination all have to resolve on MariaDB.

    SCOPE: this proves EXECUTION only. AVG over zero rows is NULL whatever
    date_diff_days returns, so this would pass even if the arithmetic were
    wrong on MariaDB. The correctness assertion lives in
    test_wip_aging_trend_average_is_correct_on_mariadb, which runs the same
    expression over seeded rows."""
    from backend.routes.holds import HoldEntry, _active_as_of

    current_date = datetime(2026, 6, 11).date()
    session = SessionLocal()
    try:
        result = (
            session.query(func.avg(date_diff_days(current_date, func.date(HoldEntry.hold_date))))
            .filter(_active_as_of(current_date))
            .scalar()
        )
    finally:
        session.close()
    assert result is None


@pytest.fixture
def mariadb_boundary_holds(mariadb_schema):
    """Seed holds straddling the as-of boundary of 2026-06-11 on live MariaDB.

    Covers every arm of `_active_as_of` with real rows, so the assertions
    below fail if MariaDB disagrees with SQLite about any of them:
      MDB-IN            opened at the last second of `as_of`      -> ACTIVE (age 0)
      MDB-AT-CUTOFF     resumed exactly AT the next midnight      -> ACTIVE (age 41)
      MDB-OUT           opened at the first second of the next day-> not yet open
      MDB-RESUMED       resumed during `as_of`                    -> already resumed
      MDB-SCRAPPED      terminal status, never resumed            -> not WIP
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
    from backend.routes.holds import HoldEntry, _active_as_of

    session = mariadb_boundary_holds
    active = session.query(HoldEntry.hold_entry_id).filter(_active_as_of(datetime(2026, 6, 11).date())).all()
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
    from backend.routes.holds import HoldEntry, _active_as_of

    current_date = datetime(2026, 6, 11).date()
    session = mariadb_boundary_holds
    result = (
        session.query(func.avg(date_diff_days(current_date, func.date(HoldEntry.hold_date))))
        .filter(_active_as_of(current_date))
        .scalar()
    )
    assert result is not None
    assert abs(float(result) - 20.5) < 0.001
