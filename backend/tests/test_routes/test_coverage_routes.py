"""Shift coverage write paths, which were entirely untested.

`create_shift_coverage`, the mutation body of `update_shift_coverage` and both
date-range filter branches never executed anywhere in the suite — the endpoints
existed, the read path had some coverage, and every write was dead code in
test. These pin the four defects that survived that gap:

  * a percentage that overflows the column it is stored in, which SQLite
    accepts and MariaDB rejects,
  * two contradictory coverage records for the same client, date and shift,
  * a coverage row pointing at another tenant's shift, and
  * a response with no client_id, which a multi-client reader cannot attribute.
"""

from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.auth.jwt import get_current_active_supervisor, get_current_contributor, get_current_user
from backend.crud.coverage import MAX_COVERAGE_PERCENTAGE
from backend.database import get_db
from backend.orm import ClientType
from backend.routes.coverage import router as coverage_router
from backend.tests.conftest import clone_template_engine
from backend.tests.fixtures.factories import TestDataFactory

COVERAGE_DATE = date(2026, 5, 12)


@pytest.fixture(scope="function")
def cov_db():
    engine = clone_template_engine()
    session = sessionmaker(bind=engine)()
    TestDataFactory.reset_counters()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


@pytest.fixture
def setup(cov_db):
    """Two tenants, so the cross-tenant checks are not vacuous."""
    db = cov_db
    client_a = TestDataFactory.create_client(
        db, client_id="COV-A", client_name="Coverage A", client_type=ClientType.HOURLY_RATE
    )
    client_b = TestDataFactory.create_client(
        db, client_id="COV-B", client_name="Coverage B", client_type=ClientType.HOURLY_RATE
    )
    admin = TestDataFactory.create_user(db, user_id="cov-admin", username="cov_admin", role="admin", client_id=None)
    operator = TestDataFactory.create_user(
        db, user_id="cov-op", username="cov_op", role="operator", client_id=client_a.client_id
    )
    shift_a = TestDataFactory.create_shift(
        db, client_id=client_a.client_id, shift_name="A day", start_time="06:00:00", end_time="14:00:00"
    )
    shift_b = TestDataFactory.create_shift(
        db, client_id=client_b.client_id, shift_name="B day", start_time="06:00:00", end_time="14:00:00"
    )
    db.commit()
    return {
        "db": db,
        "client_a": client_a,
        "client_b": client_b,
        "admin": admin,
        "operator": operator,
        "shift_a": shift_a,
        "shift_b": shift_b,
    }


def _client_for(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(coverage_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_contributor] = lambda: user
    app.dependency_overrides[get_current_active_supervisor] = lambda: user
    return TestClient(app)


def _body(setup, **over):
    payload = {
        "client_id": setup["client_a"].client_id,
        "shift_id": setup["shift_a"].shift_id,
        "coverage_date": COVERAGE_DATE.isoformat(),
        "required_employees": 8,
        "actual_employees": 8,
    }
    payload.update(over)
    return payload


class TestCreate:
    def test_creates_and_computes_the_percentage(self, setup):
        client = _client_for(setup["db"], setup["admin"])
        r = client.post("/api/coverage", json=_body(setup, actual_employees=6))
        assert r.status_code == 201
        assert r.json()["coverage_percentage"] == 75.0

    def test_the_response_says_which_client_the_row_belongs_to(self, setup):
        """A leader assigned several clients gets their rows interleaved; with
        no client_id there is no field to attribute them by."""
        client = _client_for(setup["db"], setup["admin"])
        r = client.post("/api/coverage", json=_body(setup))
        assert r.status_code == 201
        assert r.json()["client_id"] == setup["client_a"].client_id

    def test_an_overstaffed_shift_does_not_overflow_the_column(self, setup):
        """coverage_percentage is Numeric(5, 2): 999.99 is the ceiling.

        One required and fifty present computes 5000.00. SQLite stores that
        silently and MariaDB rejects it in strict mode, so without the clamp
        the whole suite passes and the write 500s in production.
        """
        client = _client_for(setup["db"], setup["admin"])
        r = client.post("/api/coverage", json=_body(setup, required_employees=1, actual_employees=50))
        assert r.status_code == 201
        assert r.json()["coverage_percentage"] == float(MAX_COVERAGE_PERCENTAGE)

    def test_a_second_record_for_the_same_shift_and_day_is_refused(self, setup):
        """Two rows for one client, date and shift are two contradictory
        answers to the same question."""
        client = _client_for(setup["db"], setup["admin"])
        assert client.post("/api/coverage", json=_body(setup)).status_code == 201

        clash = client.post("/api/coverage", json=_body(setup, actual_employees=3))
        assert clash.status_code == 409
        assert "already exists" in clash.json()["detail"]

    def test_the_database_refuses_a_duplicate_even_if_the_check_is_bypassed(self, setup):
        """The race the application check cannot close.

        `_assert_not_duplicate` is SELECT-then-INSERT, so two creates racing
        inside the same millisecond both pass it. Only the database can hold
        the invariant. This bypasses the pre-check entirely -- writing through
        the ORM the way a concurrent request would after winning the race --
        and asserts the constraint stops it.
        """
        from backend.orm.coverage import ShiftCoverage

        db = setup["db"]
        client = _client_for(db, setup["admin"])
        assert client.post("/api/coverage", json=_body(setup)).status_code == 201

        db.add(
            ShiftCoverage(
                client_id=setup["client_a"].client_id,
                shift_id=setup["shift_a"].shift_id,
                coverage_date=COVERAGE_DATE,
                required_employees=8,
                actual_employees=2,
                coverage_percentage=25,
                entered_by=setup["admin"].user_id,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_losing_the_race_reads_as_a_conflict_not_a_crash(self, setup):
        """And the constraint violation must surface as the same 409 the
        pre-check gives, not a 500."""
        db = setup["db"]
        client = _client_for(db, setup["admin"])
        assert client.post("/api/coverage", json=_body(setup)).status_code == 201

        # Second create through the API: the pre-check catches this one, but
        # the response must be identical either way.
        second = client.post("/api/coverage", json=_body(setup))
        assert second.status_code == 409

    def test_losing_the_race_returns_409_not_500(self, setup, monkeypatch):
        """The handler that turns the constraint violation into a 409.

        `test_losing_the_race_reads_as_a_conflict_not_a_crash` only reaches the
        PRE-CHECK; the winner of a real race gets past that and is stopped by
        the database instead. Neutering the pre-check is how a test reaches the
        handler at all.

        This is the test that catches deciding the question by matching the
        driver's message: SQLite names the COLUMNS in a unique violation and
        MariaDB names the CONSTRAINT, so a string match on the constraint name
        passes on MariaDB and 500s here.
        """
        import backend.crud.coverage as crud_coverage

        client = _client_for(setup["db"], setup["admin"])
        assert client.post("/api/coverage", json=_body(setup)).status_code == 201

        monkeypatch.setattr(crud_coverage, "_assert_not_duplicate", lambda *a, **k: None)
        raced = client.post("/api/coverage", json=_body(setup, actual_employees=3))
        assert raced.status_code == 409
        assert "already exists" in raced.json()["detail"]

    def test_a_non_duplicate_integrity_error_is_not_reported_as_a_duplicate(self, setup, monkeypatch):
        """A blanket `except IntegrityError` would send whoever hit a foreign-key
        or not-null failure looking for a duplicate that does not exist.

        Raised by the adversarial review. Forces a NOT NULL violation on
        `entered_by` past the pre-checks and asserts it does NOT come back as a
        409. NOT NULL rather than a foreign key because SQLite only enforces
        foreign keys under `PRAGMA foreign_keys=ON` -- an FK version of this
        test passes for the wrong reason, by never raising at all.
        """
        import backend.crud.coverage as crud_coverage

        # A DETACHED stand-in, not the session's own admin row: mutating the
        # persistent User makes the next autoflush fail on THAT row instead,
        # and the test then passes without the handler ever running.
        actor = SimpleNamespace(user_id=None, username="cov_admin", role="admin", client_id=None, is_active=True)
        client = _client_for(setup["db"], actor)
        monkeypatch.setattr(crud_coverage, "_assert_not_duplicate", lambda *a, **k: None)

        with pytest.raises(IntegrityError):
            client.post("/api/coverage", json=_body(setup))

    def test_an_edit_cannot_move_a_row_to_another_tenant(self, setup):
        """The ownership and duplicate checks live on create, not on update.

        That is only safe while `ShiftCoverageUpdate` cannot reach client_id,
        shift_id or coverage_date -- widening it would route around both checks
        and let an edit produce the cross-tenant row the create path refuses.
        Pinned here so the schema cannot quietly grow those fields.
        """
        client = _client_for(setup["db"], setup["admin"])
        created = client.post("/api/coverage", json=_body(setup)).json()

        r = client.put(
            f"/api/coverage/{created['coverage_id']}",
            json={
                "client_id": setup["client_b"].client_id,
                "shift_id": setup["shift_b"].shift_id,
                "coverage_date": (COVERAGE_DATE + timedelta(days=3)).isoformat(),
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["client_id"] == setup["client_a"].client_id
        assert body["shift_id"] == setup["shift_a"].shift_id
        assert body["coverage_date"] == COVERAGE_DATE.isoformat()

    def test_a_deleted_record_can_be_entered_again(self, setup):
        """Raised by the adversarial review as a possible bypass; it is the
        intended behaviour and pinned here so it is not "fixed" later.

        A soft-deleted row is deleted as far as its author is concerned.
        Treating it as a tombstone for its key would make a
        mistakenly-entered-then-removed record impossible to re-enter, which
        is why the constraint carries `active_marker` instead of binding the
        three business columns alone.
        """
        client = _client_for(setup["db"], setup["admin"])
        created = client.post("/api/coverage", json=_body(setup)).json()
        assert client.delete(f"/api/coverage/{created['coverage_id']}").status_code == 204

        again = client.post("/api/coverage", json=_body(setup, actual_employees=7))
        assert again.status_code == 201
        assert again.json()["coverage_id"] != created["coverage_id"]

    def test_the_clamp_is_logged_rather_than_silent(self, setup, caplog):
        """The ceiling is a column width, not a domain rule, so it is not
        rejected -- but a ratio that extreme is almost always a typo in
        required_employees, and it must be findable afterwards."""
        import logging

        client = _client_for(setup["db"], setup["admin"])
        with caplog.at_level(logging.WARNING, logger="backend.crud.coverage"):
            r = client.post("/api/coverage", json=_body(setup, required_employees=1, actual_employees=50))

        assert r.status_code == 201
        assert any("exceeds the column ceiling" in rec.getMessage() for rec in caplog.records)

    def test_a_different_day_for_the_same_shift_is_fine(self, setup):
        """Two-sided: the guard must not block the next day's record."""
        client = _client_for(setup["db"], setup["admin"])
        assert client.post("/api/coverage", json=_body(setup)).status_code == 201
        nxt = _body(setup, coverage_date=(COVERAGE_DATE + timedelta(days=1)).isoformat())
        assert client.post("/api/coverage", json=nxt).status_code == 201

    def test_a_shift_belonging_to_another_tenant_is_refused(self, setup):
        """The FK only requires the shift to EXIST, so this satisfies every
        database on every dialect and is silently cross-tenant."""
        client = _client_for(setup["db"], setup["admin"])
        r = client.post("/api/coverage", json=_body(setup, shift_id=setup["shift_b"].shift_id))
        assert r.status_code == 400
        assert "different client" in r.json()["detail"]

    def test_an_unknown_shift_is_refused(self, setup):
        client = _client_for(setup["db"], setup["admin"])
        r = client.post("/api/coverage", json=_body(setup, shift_id=999999))
        assert r.status_code == 400


class TestTheConstraintItself:
    """Written against raw SQL on purpose.

    Every other test here goes through the ORM, where the mapper event keeps
    `active_marker` in step with `is_active`. These bypass it entirely -- the
    shape a bulk UPDATE or a hand-written statement would take -- to show the
    invariant survives without the application's help.
    """

    INSERT = text(
        "INSERT INTO shift_coverage (client_id, shift_id, coverage_date, "
        "required_employees, actual_employees, coverage_percentage, entered_by, "
        "is_active, active_marker) VALUES "
        "(:client, :shift, :day, 8, 8, 100, :actor, :active, :marker)"
    )

    def _insert(self, setup, is_active, marker, day=COVERAGE_DATE):
        setup["db"].execute(
            self.INSERT,
            {
                "client": setup["client_a"].client_id,
                "shift": setup["shift_a"].shift_id,
                "day": day,
                "actor": setup["admin"].user_id,
                "active": is_active,
                "marker": marker,
            },
        )

    def test_a_second_active_row_is_rejected_by_the_database(self, setup):
        db = setup["db"]
        self._insert(setup, 1, 1)
        db.commit()
        with pytest.raises(IntegrityError):
            self._insert(setup, 1, 1)
            db.commit()
        db.rollback()

    def test_an_active_row_cannot_hide_from_the_index_with_a_null_marker(self, setup):
        """The hole the CHECK constraint closes.

        NULLs do not collide in a unique index, so an active row written with
        `active_marker = NULL` would be invisible to `uq_shift_coverage_active`
        -- exactly the duplicate it exists to forbid, admitted through the
        constraint's own escape hatch.
        """
        db = setup["db"]
        self._insert(setup, 1, 1)
        db.commit()
        with pytest.raises(IntegrityError):
            self._insert(setup, 1, None)
            db.commit()
        db.rollback()

    def test_a_deleted_row_cannot_keep_holding_its_slot(self, setup):
        """The other direction: `is_active = 0` with the marker left at 1 is a
        deleted row still occupying its key, which would make the record
        impossible to enter again."""
        db = setup["db"]
        with pytest.raises(IntegrityError):
            self._insert(setup, 0, 1)
            db.commit()
        db.rollback()

    def test_soft_deleted_rows_may_share_a_key(self, setup):
        """Two-sided: the constraint must not block the legitimate case it was
        shaped around -- any number of deleted rows for one key, plus one live
        row."""
        db = setup["db"]
        for _ in range(3):
            self._insert(setup, 0, None)
        self._insert(setup, 1, 1)
        db.commit()

        live = db.execute(
            text("SELECT COUNT(*) FROM shift_coverage WHERE is_active = 1 AND coverage_date = :d"),
            {"d": str(COVERAGE_DATE)},
        ).scalar()
        assert live == 1


class TestUpdate:
    def test_recomputes_the_percentage(self, setup):
        client = _client_for(setup["db"], setup["admin"])
        created = client.post("/api/coverage", json=_body(setup)).json()

        r = client.put(f"/api/coverage/{created['coverage_id']}", json={"actual_employees": 4})
        assert r.status_code == 200
        assert r.json()["coverage_percentage"] == 50.0

    def test_an_edit_cannot_overflow_the_column_either(self, setup):
        client = _client_for(setup["db"], setup["admin"])
        created = client.post("/api/coverage", json=_body(setup)).json()

        r = client.put(
            f"/api/coverage/{created['coverage_id']}",
            json={"required_employees": 1, "actual_employees": 80},
        )
        assert r.status_code == 200
        assert r.json()["coverage_percentage"] == float(MAX_COVERAGE_PERCENTAGE)


class TestList:
    def test_narrows_to_a_date_range(self, setup):
        client = _client_for(setup["db"], setup["admin"])
        client.post("/api/coverage", json=_body(setup))
        later = _body(setup, coverage_date=(COVERAGE_DATE + timedelta(days=10)).isoformat())
        client.post("/api/coverage", json=later)

        r = client.get(
            "/api/coverage",
            params={"start_date": COVERAGE_DATE.isoformat(), "end_date": COVERAGE_DATE.isoformat()},
        )
        assert r.status_code == 200
        assert [row["coverage_date"] for row in r.json()] == [COVERAGE_DATE.isoformat()]

    def test_narrows_to_one_client(self, setup):
        """The CRUD layer always accepted client_id; the route never offered
        it, so a multi-client reader could not narrow to one tenant."""
        client = _client_for(setup["db"], setup["admin"])
        client.post("/api/coverage", json=_body(setup))

        r = client.get("/api/coverage", params={"client_id": setup["client_a"].client_id})
        assert r.status_code == 200
        assert {row["client_id"] for row in r.json()} == {setup["client_a"].client_id}

        empty = client.get("/api/coverage", params={"client_id": setup["client_b"].client_id})
        assert empty.status_code == 200
        assert empty.json() == []

    def test_returns_more_than_a_hundred_rows(self, setup):
        """The old default of 100 silently truncated the 112 seeded rows, so a
        reader could not tell a short month from a clipped page."""
        client = _client_for(setup["db"], setup["admin"])
        for offset in range(105):
            client.post(
                "/api/coverage",
                json=_body(setup, coverage_date=(COVERAGE_DATE + timedelta(days=offset)).isoformat()),
            )

        r = client.get("/api/coverage")
        assert r.status_code == 200
        assert len(r.json()) == 105
