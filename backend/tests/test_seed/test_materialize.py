import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select

from backend.database import Base
from backend.orm import HoldStatusTransition, WorkflowTransitionLog, WorkOrder
from backend.seed.generator import generate
from backend.seed.materialize import CLIENT_SCOPE_COLUMN, INSERT_ORDER, RowSink, materialize
from backend.seed.profiles import SMOKE
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
    map is what --reset filters on; a missing entry means a client's rows
    survive a reset and collide on re-seed."""
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


def test_created_at_is_back_dated_too(seed_engine):
    """created_at carries a server_default on every seeded table. A row whose
    created_at is the seed-run instant is a row the materializer forgot."""
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        earliest = conn.execute(select(func.min(WorkOrder.created_at))).scalar_one()

    # See test_transition_timestamps_are_not_all_the_seed_run_instant above
    # for why this compares against the real run instant rather than a fixed
    # calendar-date literal.
    assert earliest < datetime.now() - timedelta(days=1)


def test_hold_status_history_is_monotonic_per_hold(seed_engine):
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

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
    for hold_id, _tid, at in rows:
        if hold_id in seen:
            assert at >= seen[hold_id]
        seen[hold_id] = at


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
    from backend.orm import ProductionLine, Shift

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        lines = conn.execute(select(ProductionLine.line_id, ProductionLine.line_code)).all()
        shifts = conn.execute(select(Shift.shift_id, Shift.client_id)).all()

    assert len({r.line_id for r in lines}) == len(lines)
    assert len({r.shift_id for r in shifts}) == len(shifts)


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
    was this on date D' was unanswerable -- the premise of PR-C."""
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        orders = {r.work_order_id for r in conn.execute(select(WorkOrder.work_order_id)).all()}
        opening = {
            r.work_order_id
            for r in conn.execute(
                select(WorkflowTransitionLog.work_order_id).where(WorkflowTransitionLog.from_status.is_(None))
            ).all()
        }

    assert orders
    assert orders - opening == set()


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
