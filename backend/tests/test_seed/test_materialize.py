import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from backend.database import Base
from backend.orm import HoldStatusTransition, WorkflowTransitionLog, WorkOrder
from backend.seed.generator import generate
from backend.seed.materialize import CLIENT_SCOPE_COLUMN, INSERT_ORDER, RowSink, materialize
from backend.seed.profiles import FULL, SMOKE
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 18)

#: .../backend/tests/test_seed/test_materialize.py -> repo root, four parents up.
_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_insert_order_respects_every_foreign_key():
    """INSERT_ORDER exists to satisfy one property: every table a foreign key
    points AT is inserted before the table that points to it. Comparing
    INSERT_ORDER against `[t.name for t in Base.metadata.sorted_tables]` (the
    identical expression that DEFINES it) does not prove that -- it would
    pass just as well for a hand-written list pasted from today's output,
    which is exactly the failure mode this module's docstring warns against.
    Prove the actual invariant instead, against Base.metadata directly."""
    assert INSERT_ORDER  # a hand-written [] would trivially pass an FK-order check below

    position = {name: i for i, name in enumerate(INSERT_ORDER)}
    violations = []
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            parent, child = fk.column.table.name, table.name
            if parent == child:
                continue  # self-referential FK: no cross-table ordering to satisfy
            if position[parent] >= position[child]:
                violations.append(
                    f"{child} (pos {position[child]}) references {parent} (pos {position[parent]}) out of order"
                )
    assert violations == []


def test_insert_order_is_populated_in_a_fresh_process():
    """Base.metadata only carries tables whose ORM classes were imported
    somewhere in the process -- that registration is a side effect of
    importing backend.orm, not of importing backend.database. Every test in
    this suite (including this file's own `from backend.orm import ...`
    above) triggers that import before materialize.py's module body runs,
    which would hide a materialize.py that forgot to import backend.orm
    itself: INSERT_ORDER would silently compute to [] and flush() would
    silently write nothing. Only a genuinely fresh subprocess -- where
    nothing else touches backend.orm first -- reproduces that."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from backend.database import Base\n"
            "from backend.seed.materialize import INSERT_ORDER\n"
            "import sys\n"
            "sys.exit(0 if INSERT_ORDER and 'WORK_ORDER' in INSERT_ORDER else 1)\n",
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"


def test_every_client_scoped_table_declares_its_scope_column():
    """Three different column names carry the tenant across these tables. The
    map is the writer-side contract -- a missing entry means the materializer
    has no declared tenant column to write, and
    test_the_platform_sentinel_never_reaches_a_client_column below stops
    checking that table. (--reset derives its own, wider set; see
    cli.CLIENT_SCOPED_TABLES.)"""
    for table_name in ("PRODUCTION_ENTRY", "DEFECT_DETAIL", "EMPLOYEE"):
        assert table_name in CLIENT_SCOPE_COLUMN

    assert CLIENT_SCOPE_COLUMN["PRODUCTION_ENTRY"] == "client_id"
    assert CLIENT_SCOPE_COLUMN["DEFECT_DETAIL"] == "client_id_fk"
    assert CLIENT_SCOPE_COLUMN["EMPLOYEE"] == "client_id_assigned"


def test_sink_preserves_stream_order_within_a_table():
    """Spec section 12: cross-table order is irrelevant, but active_as_of
    tie-breaks on ascending transition_id, so a batch must never be sorted."""
    sink = RowSink()
    sink.add("WORK_ORDER", {"work_order_id": "B"})
    sink.add("SHIFT", {"shift_id": 1})
    sink.add("WORK_ORDER", {"work_order_id": "A"})

    assert [r["work_order_id"] for r in sink.rows("WORK_ORDER")] == ["B", "A"]


def test_a_smoke_seed_writes_rows(seed_engine):
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)

    with seed_engine.begin() as conn:
        counts = materialize(conn, events, SMOKE)

    assert counts["WORK_ORDER"] > 0
    assert counts["ATTENDANCE_ENTRY"] > counts["PRODUCTION_ENTRY"]


def test_transition_timestamps_are_not_all_the_seed_run_instant(seed_engine):
    """The defect this whole project exists to fix: 40 chains collapsed into a
    single instant because transitioned_at fell through to its server_default.
    That column HAS a server default -- omitting it is the failure mode."""
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        distinct = conn.execute(select(func.count(func.distinct(WorkflowTransitionLog.transitioned_at)))).scalar_one()
        earliest = conn.execute(select(func.min(WorkflowTransitionLog.transitioned_at))).scalar_one()

    assert distinct > 10
    # A fixed calendar-date literal here doesn't scale with AS_OF/SMOKE.days:
    # SMOKE's own window is [AS_OF - SMOKE.days, AS_OF], so the earliest
    # possible event is AS_OF minus ~14 days -- comparing against a date more
    # than 14 days before AS_OF (as this test did before Task 7 first
    # exercised it end-to-end) can never be satisfied. Compare against the
    # actual run instant instead, which is what "fell through to
    # server_default" would produce: today, not a backdated window.
    assert earliest < datetime.now() - timedelta(days=1)


def test_created_at_is_back_dated_on_every_seeded_table(seed_engine):
    """created_at carries a server_default on every seeded table -- not just
    WorkOrder. Checking WorkOrder alone is vacuous for every OTHER table:
    dropping created_at/updated_at from _production_recorded (4160 rows at
    FULL -- the exact defect this rebuild exists to remove) left this test
    green when it checked only WorkOrder. Sweep every table the writers
    actually populated (materialize()'s own returned counts, keyed the same
    as RowSink.tables()) that declares a created_at column.

    Per-table MIN, not per-row: a systematic omission (a handler that always
    forgets the column) still makes every row in that table land at "now",
    so MIN alone catches it -- and it's the failure mode the mutation below
    proves. See test_transition_timestamps_are_not_all_the_seed_run_instant
    above for why this compares against the real run instant rather than a
    fixed calendar-date literal.
    """
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        counts = materialize(conn, events, SMOKE)

    assert counts  # sanity: materialize() wrote something at all
    cutoff = datetime.now() - timedelta(days=1)

    with seed_engine.connect() as conn:
        checked = 0
        for table_name in counts:
            table = Base.metadata.tables[table_name]
            if "created_at" not in table.c:
                continue
            checked += 1
            earliest = conn.execute(select(func.min(table.c.created_at))).scalar_one()
            assert earliest is not None, f"{table_name}.created_at is NULL"
            assert earliest < cutoff, f"{table_name}.created_at is not backdated: {earliest}"
            if "updated_at" in table.c:
                earliest_u = conn.execute(select(func.min(table.c.updated_at))).scalar_one()
                assert earliest_u is not None, f"{table_name}.updated_at is NULL"
                assert earliest_u < cutoff, f"{table_name}.updated_at is not backdated: {earliest_u}"

    # 21 of the 23 tables the writers touch carry created_at (the other two,
    # WORKFLOW_TRANSITION_LOG and HOLD_STATUS_TRANSITION, carry
    # transitioned_at instead -- covered by their own dedicated tests). A
    # count far below that would mean this loop silently stopped covering
    # tables it used to.
    assert checked >= 20, f"only swept {checked} tables with a created_at column"


def test_hold_status_history_is_monotonic_per_hold(seed_engine):
    """FULL/seed=1234, not SMOKE: SMOKE's short window and low hold rate
    produces at most a handful of hold status rows total (seed=7 yields zero
    holds outright; seed=1234 yields exactly one), so the `if hold_id in
    seen:` branch below would rarely or never execute and the assertion
    would prove nothing -- the multi > 0 guard is what catches that, the
    same way test_transition_chains_strictly_increase_per_order's sibling
    guard does for work orders. FULL/1234 produces 21 multi-step holds
    (checked directly against the generator), comfortably non-vacuous."""
    events = generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, FULL)

    with seed_engine.connect() as conn:
        rows = conn.execute(
            select(
                HoldStatusTransition.hold_entry_id,
                HoldStatusTransition.transition_id,
                HoldStatusTransition.transitioned_at,
            ).order_by(HoldStatusTransition.hold_entry_id, HoldStatusTransition.transition_id)
        ).all()

    assert rows
    seen: dict = {}
    multi = 0
    for hold_id, _tid, at in rows:
        if hold_id in seen:
            assert at >= seen[hold_id]
            multi += 1
        seen[hold_id] = at

    assert multi > 0, "no hold had more than one transition -- the monotonicity assertion proved nothing"


def test_users_cover_all_six_roles_and_can_authenticate(seed_engine):
    """A seeded password hash the verifier rejects is a demo nobody can log
    into -- and unit tests that only count rows would not notice."""
    from backend.auth.password import verify_password
    from backend.orm import User
    from backend.seed.scenarios import DEMO_PASSWORD

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        rows = conn.execute(select(User.username, User.role, User.password_hash)).all()

    assert {r.role for r in rows} == {"admin", "poweruser", "leader", "supervisor", "operator", "viewer"}
    for r in rows:
        assert verify_password(DEMO_PASSWORD, r.password_hash) is True


def test_the_platform_sentinel_never_reaches_a_client_column(seed_engine):
    from backend.seed.events import PLATFORM_CLIENT_ID

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        for table_name, column in CLIENT_SCOPE_COLUMN.items():
            if column is None:
                continue
            table = Base.metadata.tables[table_name]
            hits = conn.execute(
                select(func.count()).select_from(table).where(table.c[column] == PLATFORM_CLIENT_ID)
            ).scalar_one()
            assert hits == 0, f"{table_name}.{column} carries the stream sentinel"


def test_the_leader_reaches_three_clients_through_the_real_scope_resolver(seed_engine):
    """USER_CLIENT_ASSIGNMENT was zero for the entire life of the client-scope
    feature. Counting rows would not prove the resolver reads them.

    get_user_client_filter is the plain function resolve_client_scope delegates
    to (backend/middleware/client_auth.py); resolve_client_scope itself is a
    FastAPI dependency and needs a request to call. None means "all clients".
    """
    from sqlalchemy.orm import Session

    from backend.middleware.client_auth import get_user_client_filter
    from backend.orm import User

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with Session(seed_engine) as session:
        leader = session.query(User).filter(User.username == "demo_leader").one()
        viewer = session.query(User).filter(User.username == "demo_viewer").one()

        assert len(get_user_client_filter(leader, session)) == 3
        assert len(get_user_client_filter(viewer, session)) == 1


def test_integer_pks_are_assigned_and_resolvable(seed_engine):
    """Uniqueness alone is a property the database's own PRIMARY KEY
    constraint already guarantees -- asserting it exercises nothing about
    IdMap/IntPkAllocator. "Resolvable" means a LATER event's foreign-key
    reference (a production entry's line_id, an attendance row's shift_id)
    actually lands on the integer PRODUCTION_LINE/SHIFT row an EARLIER event
    minted in this same run, not a stale or swapped one.

    seed_engine now enforces foreign keys (PRAGMA foreign_keys=ON, see
    conftest.py) -- materialize() completing here at all is direct proof
    every resolved id landed on a real row: a swapped id source (line_id
    resolved where product_id belongs, the classic copy-paste bug) raises
    sqlite3.IntegrityError instead of silently inserting. The subset checks
    below additionally confirm the FK columns are actually POPULATED with
    resolved ids, not merely absent (nullable columns pass FK enforcement
    trivially when NULL)."""
    from backend.orm import AttendanceEntry, ProductionEntry, ProductionLine, Shift

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)  # would raise IntegrityError on any dangling FK

    with seed_engine.connect() as conn:
        line_ids = {r.line_id for r in conn.execute(select(ProductionLine.line_id)).all()}
        shift_ids = {r.shift_id for r in conn.execute(select(Shift.shift_id)).all()}
        production_lines_used = {r.line_id for r in conn.execute(select(ProductionEntry.line_id)).all()}
        attendance_shifts_used = {
            r.shift_id for r in conn.execute(select(AttendanceEntry.shift_id)).all() if r.shift_id is not None
        }

    assert production_lines_used, "no PRODUCTION_ENTRY.line_id was populated -- the check below would be vacuous"
    assert production_lines_used <= line_ids
    assert attendance_shifts_used, "no ATTENDANCE_ENTRY.shift_id was populated -- the check below would be vacuous"
    assert attendance_shifts_used <= shift_ids


def test_defect_catalog_covers_every_code_per_client(seed_engine):
    from backend.orm import DefectTypeCatalog
    from backend.seed.scenarios import DEFECT_CODES, SCENARIOS as S

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        rows = conn.execute(select(DefectTypeCatalog.client_id, DefectTypeCatalog.defect_code)).all()

    by_client: dict = {}
    for r in rows:
        by_client.setdefault(r.client_id, set()).add(r.defect_code)

    assert set(by_client) == {s.client_id for s in S}
    for codes in by_client.values():
        assert codes == set(DEFECT_CODES)


def test_kpi_thresholds_are_scoped_per_client_not_shared(seed_engine):
    """KPI_THRESHOLD.client_id is a real nullable FK under
    UniqueConstraint(client_id, kpi_key) -- not a global row. Emitting the
    four targets only under the first scenario (the old behavior) would mean
    a --reset of that one client deletes the "global" defaults for the other
    three. Every seeded client must carry its own full set."""
    from backend.orm import KPIThreshold
    from backend.seed.scenarios import SCENARIOS as S, THRESHOLDS

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        rows = conn.execute(select(KPIThreshold.client_id, KPIThreshold.kpi_key)).all()

    by_client: dict = {}
    for r in rows:
        by_client.setdefault(r.client_id, set()).add(r.kpi_key)

    assert set(by_client) == {s.client_id for s in S}
    for kpi_keys in by_client.values():
        assert kpi_keys == {kpi_key for kpi_key, _ in THRESHOLDS}


def test_every_work_order_has_an_opening_transition(seed_engine):
    """60 of 100 orders had no chain at all in the old dataset, so 'what status
    was this on date D' was unanswerable -- the premise of PR-C.

    Checks POSITION, not just presence: a NULL from_status row must be the
    FIRST transition (lowest transition_id) for its order, not merely
    present somewhere in the chain. A presence-only check (`orders -
    opening == set()`) would still pass if a mid-chain row were NULL and the
    genuine opening row were not -- transition_id is autoincrement in
    insertion/stream order, so grouping by work_order_id after an ORDER BY
    transition_id and taking the first row per group is the real "opens the
    chain" check.
    """
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        orders = {r.work_order_id for r in conn.execute(select(WorkOrder.work_order_id)).all()}
        rows = conn.execute(
            select(WorkflowTransitionLog.work_order_id, WorkflowTransitionLog.from_status).order_by(
                WorkflowTransitionLog.work_order_id, WorkflowTransitionLog.transition_id
            )
        ).all()

    assert orders
    assert rows
    first_from_status_by_order: dict = {}
    for work_order_id, from_status in rows:
        first_from_status_by_order.setdefault(work_order_id, from_status)

    assert set(first_from_status_by_order) == orders
    for work_order_id, from_status in first_from_status_by_order.items():
        assert from_status is None, f"{work_order_id}: opening transition has from_status={from_status!r}, not NULL"


def test_every_hold_has_an_opening_transition_with_a_null_from_status(seed_engine):
    """Hold-side sibling of test_every_work_order_has_an_opening_transition.
    active_as_of's pre-history resolution reads a NULL from_status to mean
    'this hold began here' (PR-C1b) -- the same invariant, same positional
    check, for HOLD_ENTRY / HOLD_STATUS_TRANSITION instead of WORK_ORDER /
    WORKFLOW_TRANSITION_LOG."""
    from backend.orm import HoldEntry

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        holds = {r.hold_entry_id for r in conn.execute(select(HoldEntry.hold_entry_id)).all()}
        rows = conn.execute(
            select(HoldStatusTransition.hold_entry_id, HoldStatusTransition.from_status).order_by(
                HoldStatusTransition.hold_entry_id, HoldStatusTransition.transition_id
            )
        ).all()

    assert holds
    assert rows
    first_from_status_by_hold: dict = {}
    for hold_entry_id, from_status in rows:
        first_from_status_by_hold.setdefault(hold_entry_id, from_status)

    assert set(first_from_status_by_hold) == holds
    for hold_entry_id, from_status in first_from_status_by_hold.items():
        assert from_status is None, f"{hold_entry_id}: opening transition has from_status={from_status!r}, not NULL"


def test_transition_chains_strictly_increase_per_order(seed_engine):
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        rows = conn.execute(
            select(
                WorkflowTransitionLog.work_order_id,
                WorkflowTransitionLog.transition_id,
                WorkflowTransitionLog.transitioned_at,
            ).order_by(WorkflowTransitionLog.work_order_id, WorkflowTransitionLog.transition_id)
        ).all()

    last: dict = {}
    multi = 0
    for wo, _tid, at in rows:
        if wo in last:
            assert at > last[wo], f"{wo}: {at} does not follow {last[wo]}"
            multi += 1
        last[wo] = at

    assert multi > 0, "no order had more than one transition -- the chain assertion proved nothing"


def test_every_defect_detail_joins_to_its_clients_catalog(seed_engine):
    """All 80 live DEFECT_DETAIL rows say 'Stitching', a display name in no
    catalog, so the taxonomy DHU slices by is unjoinable."""
    from backend.orm import DefectDetail, DefectTypeCatalog

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(DefectDetail)).scalar_one()
        joined = conn.execute(
            select(func.count())
            .select_from(DefectDetail)
            .join(
                DefectTypeCatalog,
                (DefectDetail.defect_type == DefectTypeCatalog.defect_code)
                & (DefectDetail.client_id_fk == DefectTypeCatalog.client_id),
            )
        ).scalar_one()

    assert total > 0
    assert joined == total


def test_shift_date_is_never_midnight(seed_engine):
    """A midnight shift_date sits on a half-open range boundary and same-day
    queries return zero -- the date-boundary class fixed in #146.

    Reads rows and asserts in Python rather than using SQLite's strftime():
    Task 10 runs this suite on MariaDB too, and strftime() is SQLite-only.
    """
    from backend.orm import AttendanceEntry, ProductionEntry

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        for model in (ProductionEntry, AttendanceEntry):
            rows = conn.execute(select(model.shift_date)).all()
            assert rows
            for (shift_date,) in rows:
                assert (shift_date.hour, shift_date.minute) != (0, 0), f"{model.__name__}: {shift_date}"


def test_quality_entries_reference_real_work_orders(seed_engine):
    from backend.orm import QualityEntry

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        orphans = conn.execute(
            select(func.count())
            .select_from(QualityEntry)
            .outerjoin(WorkOrder, QualityEntry.work_order_id == WorkOrder.work_order_id)
            .where(WorkOrder.work_order_id.is_(None))
        ).scalar_one()

    assert orphans == 0


def test_work_orders_carry_a_planned_ship_date_for_otds_full_confidence_tier(seed_engine):
    """OTD's date-inference chain (backend/calculations/otd.py:43) prefers
    planned_ship_date at confidence 1.0 over required_date's 0.8 fallback.
    Every seeded order should reach the higher tier, not the fallback."""
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        rows = conn.execute(select(WorkOrder.planned_ship_date, WorkOrder.required_date)).all()

    assert rows
    for planned_ship_date, required_date in rows:
        assert planned_ship_date is not None
        assert planned_ship_date == required_date


def test_materializing_twice_in_one_process_resets_open_row_state(seed_engine, tmp_path):
    """writers_operations._open_rows is module-level state keyed by business
    id (WO:<id>, HOLD:<id>), amended in place by later status-change events --
    the only place the materializer mutates a row after handing it to the
    sink, since a Core insert() cannot UPDATE an accumulated row. Without
    writers_operations.reset() at the top of materialize(), a second seed in
    the same process would carry the first run's entries forward forever.

    Proven end-to-end, not by inspecting reset() in isolation: seed SMOKE
    (work_orders_per_client=6, so every client mints a WO-0006) into one
    engine, confirm that id is now sitting in _open_rows (state IS used
    during a run, so this isn't vacuous), then seed a SECOND, unrelated
    engine with a profile that only mints WO-0001 per client. If reset()
    doesn't fire, WO-0006's stale entry survives untouched -- run 2 never
    references it, so nothing else would clear it.
    """
    import backend.seed.writers_operations as writers_operations
    from backend.db.migrate import upgrade_to_head
    from backend.seed.profiles import Profile
    from sqlalchemy import create_engine

    events_a = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events_a, SMOKE)

    smoke_only_keys = [k for k in writers_operations._open_rows if k.endswith("-WO-0006")]
    assert smoke_only_keys, "SMOKE run left no WO-0006 entries -- the setup below would prove nothing"

    tiny = Profile(
        name="tiny-second-run",
        days=SMOKE.days,
        lines_per_client=SMOKE.lines_per_client,
        shifts_per_client=SMOKE.shifts_per_client,
        employees_per_client=SMOKE.employees_per_client,
        work_orders_per_client=1,
        defect_rows_per_inspection=SMOKE.defect_rows_per_inspection,
    )
    events_b = generate(SCENARIOS, tiny, seed=1234, as_of=AS_OF)
    url_b = f"sqlite:///{tmp_path / 'second_run.db'}"
    upgrade_to_head(url_b)
    engine_b = create_engine(url_b)
    try:
        with engine_b.begin() as conn:
            materialize(conn, events_b, tiny)
    finally:
        engine_b.dispose()

    surviving = [k for k in smoke_only_keys if k in writers_operations._open_rows]
    assert surviving == [], f"stale WO-0006 entries survived a second materialize() call: {surviving}"


def test_every_string_value_fits_its_column_length(tmp_path):
    """SQLite ignores VARCHAR(N) declarations, so a key formula that overflows
    a real column passes silently here and only fails on MariaDB (ERROR 1406:
    Data too long) -- or, worse, silently truncates under a non-strict
    sql_mode, collapsing distinct rows onto one truncated key. Sweep every
    string column's actual persisted length against Base.metadata's declared
    length, across BOTH profiles: FULL's larger integer pks are what push a
    derived key closest to its column's limit."""
    from sqlalchemy import String, create_engine

    from backend.db.migrate import upgrade_to_head

    for profile in (SMOKE, FULL):
        events = generate(SCENARIOS, profile, seed=1234, as_of=AS_OF)
        url = f"sqlite:///{tmp_path / f'{profile.name}.db'}"
        upgrade_to_head(url)
        engine = create_engine(url)
        try:
            with engine.begin() as conn:
                materialize(conn, events, profile)
            with engine.connect() as conn:
                for table_name, table in Base.metadata.tables.items():
                    for column in table.columns:
                        if not isinstance(column.type, String) or column.type.length is None:
                            continue
                        for (value,) in conn.execute(select(column)).all():
                            if value is None:
                                continue
                            assert len(value) <= column.type.length, (
                                f"{profile.name}: {table_name}.{column.name}={value!r} "
                                f"({len(value)} chars) exceeds VARCHAR({column.type.length})"
                            )
        finally:
            engine.dispose()
