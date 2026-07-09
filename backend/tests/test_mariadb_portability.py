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
    """The canonical registration helper must yield the complete table registry."""
    from backend.orm import register_all_models

    register_all_models()
    assert len(Base.metadata.tables) >= 45


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
    """Create the full schema on the live MariaDB, drop it afterwards."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)  # would raise 1170 before the Task 1 fix
    yield
    Base.metadata.drop_all(bind=engine)


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
