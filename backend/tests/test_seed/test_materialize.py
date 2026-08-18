from datetime import date, datetime

from sqlalchemy import func, select

from backend.database import Base
from backend.orm import HoldStatusTransition, WorkflowTransitionLog, WorkOrder
from backend.seed.generator import generate
from backend.seed.materialize import CLIENT_SCOPE_COLUMN, INSERT_ORDER, RowSink, materialize
from backend.seed.profiles import SMOKE
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 18)


def test_insert_order_is_derived_from_metadata_not_hand_written():
    """A hand-maintained FK order rots the first time a table is added. This
    one cannot: SQLAlchemy topologically sorts by foreign key."""
    assert INSERT_ORDER == [t.name for t in Base.metadata.sorted_tables]


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
    assert earliest < datetime(2026, 8, 1)


def test_created_at_is_back_dated_too(seed_engine):
    """created_at carries a server_default on every seeded table. A row whose
    created_at is the seed-run instant is a row the materializer forgot."""
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        earliest = conn.execute(select(func.min(WorkOrder.created_at))).scalar_one()

    assert earliest < datetime(2026, 8, 1)


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
