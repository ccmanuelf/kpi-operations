"""The S1 soft-delete path, against a live MariaDB.

This repo's recurring bug class is MariaDB-only behaviour SQLite cannot catch
(``julianday``, ``SUM`` returning Decimal, null-ordering syntax), and a migration
plus a new WHERE clause is exactly where it bites:

* ``op.add_column(..., sa.Boolean(), nullable=False, server_default="1")`` has
  to be accepted by InnoDB on a populated table, and has to give existing rows
  1 rather than NULL or an error;
* ``model.is_active.is_(True)`` renders ``IS true`` on MySQL/MariaDB and
  ``IS 1`` on SQLite — different SQL, and only one of them is exercised by the
  default suite;
* ``soft_delete()`` writes the integer ``0`` (``isinstance(True, int)`` is True
  in Python), which has to compare false against MariaDB's BOOL/TINYINT.

Runs in the ``mariadb-portability`` job, which asserts zero skips — so if the
guard silently stops applying, that job fails rather than reporting green.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, insert, select

from backend.database import Base, SessionLocal, engine
from backend.db.soft_delete_filter import INCLUDE_INACTIVE, include_inactive
from backend.db.soft_delete_registry import AUTO_FILTERED_TABLES
from backend.orm import register_all_models
from backend.orm.client import Client, ClientType
from backend.orm.work_order import WorkOrder
from backend.utils.soft_delete import soft_delete

register_all_models()

_IS_MARIADB = "mysql" in str(engine.url).lower()
requires_mariadb = pytest.mark.skipif(
    not _IS_MARIADB, reason="requires the app engine to be MariaDB (DATABASE_URL=mysql+pymysql://...)"
)

CLIENT_ID = "SD-MARIA"


@pytest.fixture(scope="module")
def mariadb_schema():
    from backend.db.migrate import rebuild_schema

    # render_as_string(hide_password=False): str(engine.url) masks the password
    # as "***", which Alembic would then use verbatim and fail to authenticate.
    rebuild_schema(engine.url.render_as_string(hide_password=False))
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def seeded_client(mariadb_schema):
    session = SessionLocal()
    try:
        session.add(Client(client_id=CLIENT_ID, client_name="SD Maria", client_type=ClientType.HOURLY_RATE))
        session.commit()
        yield session
    finally:
        session.query(WorkOrder).delete()
        session.query(Client).delete()
        session.commit()
        session.close()


def _new_work_order(work_order_id: str) -> dict:
    return {
        "work_order_id": work_order_id,
        "client_id": CLIENT_ID,
        "style_model": "SD-STYLE",
        "planned_quantity": 10,
        "actual_quantity": 0,
        "received_date": datetime.now(tz=timezone.utc),
    }


@requires_mariadb
@pytest.mark.parametrize("table", sorted(AUTO_FILTERED_TABLES))
def test_migration_added_a_non_nullable_is_active_with_a_true_default(mariadb_schema, table):
    """The column InnoDB actually built, not the one the model declares."""
    column = next(c for c in inspect(engine).get_columns(table) if c["name"] == "is_active")
    assert column["nullable"] is False
    assert str(column["default"]) == "1"


@requires_mariadb
@pytest.mark.parametrize("table", sorted(AUTO_FILTERED_TABLES))
def test_migration_added_nullable_deleted_at_and_deleted_by(mariadb_schema, table):
    """NULL means "not deleted", which is true of every pre-existing row — so
    these must be nullable with no default on InnoDB too."""
    columns = {c["name"]: c for c in inspect(engine).get_columns(table)}
    assert columns["deleted_at"]["nullable"] is True
    assert columns["deleted_at"]["default"] is None
    assert columns["deleted_by"]["nullable"] is True
    assert columns["deleted_by"]["default"] is None


@requires_mariadb
def test_soft_delete_attribution_round_trips_on_mariadb(seeded_client):
    """deleted_at is a DATETIME on MariaDB with whole-second precision and no
    tz offset — a naive UTC value has to survive the round trip intact."""
    from datetime import timedelta

    from backend.db.soft_delete_service import soft_delete_record

    session = seeded_client
    session.add(WorkOrder(**_new_work_order("SD-WO-4")))
    session.commit()

    class _Actor:
        user_id = "SD-ACTOR-1"

    before = datetime.now(tz=timezone.utc).replace(tzinfo=None) - timedelta(seconds=5)
    target = session.query(WorkOrder).filter(WorkOrder.work_order_id == "SD-WO-4").one()
    assert soft_delete_record(session, target, _Actor()) is True
    session.expunge_all()

    with include_inactive(session):
        row = session.query(WorkOrder).filter(WorkOrder.work_order_id == "SD-WO-4").one()
        assert row.is_active is False
        assert row.deleted_by == "SD-ACTOR-1"
        assert row.deleted_at.replace(tzinfo=None) >= before


@requires_mariadb
def test_a_blocked_delete_is_refused_on_mariadb(seeded_client):
    """The blocker count is a COUNT(*) over a child table on InnoDB, and this
    repo's history says a SUM/COUNT can come back as a type the caller did not
    expect. Asserted against a live server, not a SQLite stand-in.
    """
    from fastapi import HTTPException

    from backend.db.soft_delete_service import soft_delete_record
    from backend.orm.job import Job

    session = seeded_client
    session.add(WorkOrder(**_new_work_order("SD-WO-5")))
    session.flush()
    session.add(
        Job(
            job_id="SD-JOB-1",
            work_order_id="SD-WO-5",
            client_id_fk=CLIENT_ID,
            part_number="SD-PART-1",
            operation_code="ASSY",
            operation_name="Assembly",
            sequence_number=1,
            planned_quantity=10,
            completed_quantity=0,
        )
    )
    session.commit()

    target = session.query(WorkOrder).filter(WorkOrder.work_order_id == "SD-WO-5").one()
    with pytest.raises(HTTPException) as exc_info:
        soft_delete_record(session, target)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["blocked_by"] == [{"table": "JOB", "count": 1}]
    session.rollback()
    session.query(Job).delete()
    session.commit()


@requires_mariadb
def test_soft_delete_round_trip_on_mariadb(seeded_client):
    """soft_delete() writes 0, and MariaDB's IS true excludes it."""
    session = seeded_client
    session.add(WorkOrder(**_new_work_order("SD-WO-1")))
    session.commit()

    assert [w.work_order_id for w in session.query(WorkOrder).all()] == ["SD-WO-1"]

    target = session.query(WorkOrder).filter(WorkOrder.work_order_id == "SD-WO-1").one()
    assert soft_delete(session, target) is True
    session.expunge_all()

    assert session.query(WorkOrder).all() == []
    assert session.get(WorkOrder, "SD-WO-1") is None
    assert session.execute(select(WorkOrder.work_order_id)).all() == []


@requires_mariadb
def test_soft_deleted_row_is_still_there_and_reachable_by_opt_in(seeded_client):
    """Soft delete preserves the audit record; the row is hidden, not removed."""
    session = seeded_client
    session.add(WorkOrder(**_new_work_order("SD-WO-2")))
    session.commit()
    soft_delete(session, session.query(WorkOrder).filter(WorkOrder.work_order_id == "SD-WO-2").one())
    session.expunge_all()

    via_option = session.query(WorkOrder.work_order_id, WorkOrder.is_active)
    assert via_option.execution_options(**{INCLUDE_INACTIVE: True}).all() == [("SD-WO-2", False)]

    with include_inactive(session):
        assert [r[0] for r in session.query(WorkOrder.work_order_id).all()] == ["SD-WO-2"]


@requires_mariadb
def test_a_raw_insert_that_omits_is_active_gets_the_server_default(seeded_client):
    """The seeder writes rows column-by-column without the ORM default, so the
    server default is what keeps freshly seeded rows visible."""
    session = seeded_client
    session.execute(insert(WorkOrder.__table__).values(**_new_work_order("SD-WO-3")))
    session.commit()

    assert [r[0] for r in session.query(WorkOrder.work_order_id).all()] == ["SD-WO-3"]
    assert session.query(WorkOrder).one().is_active is True


@requires_mariadb
def test_the_filter_renders_mariadb_syntax_not_sqlite_syntax(mariadb_schema):
    """Pins the dialect-specific SQL actually sent to the server.

    ``with_loader_criteria`` is added at execution time by the do_orm_execute
    listener, not at statement-build time, so the only honest way to see the
    WHERE clause is to capture what the driver receives. MariaDB gets
    ``IS true``; the same code on SQLite emits ``IS 1``.
    """
    from sqlalchemy import event

    captured = []

    def _capture(conn, cursor, statement, parameters, context, executemany):
        captured.append(statement)

    session = SessionLocal()
    event.listen(engine, "before_cursor_execute", _capture)
    try:
        session.query(WorkOrder.work_order_id).all()
    finally:
        event.remove(engine, "before_cursor_execute", _capture)
        session.close()

    flattened = [s.replace("`", "").replace("\n", " ") for s in captured]
    assert [s for s in flattened if "is_active IS true" in s] != [], flattened
