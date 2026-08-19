import os

import pytest
from sqlalchemy import create_engine, event

from backend.db.migrate import rebuild_schema, upgrade_to_head


@pytest.fixture
def seed_engine(tmp_path):
    """A real database with the schema built by Alembic.

    Alembic, not create_all: C5 made Alembic the single schema mechanism and
    test_no_create_all_outside_alembic enforces it.

    Defaults to a file-backed SQLite database (not in-memory, because the
    materializer opens its own connection) unique to this test via tmp_path.
    When SEED_TEST_DATABASE_URL is set -- the mariadb-portability CI job --
    it points at a live MariaDB instead, which is where this repo's real
    dialect-only bug class lives (spec section 8). rebuild_schema, not
    upgrade_to_head, on that path: MariaDB is one shared, persistent service
    across every test in this file, so each test must drop and rebuild the
    schema to get the same guaranteed-empty starting point tmp_path gives the
    SQLite path for free -- without it, the second test to run would collide
    on the first test's UNIQUE constraints (employee_code, username, email,
    per-client product/line codes, ...).

    Foreign keys are OFF by default on a bare create_engine(url) -- SQLite
    does not enforce them without PRAGMA foreign_keys=ON, which the app's own
    SQLiteProvider sets (backend/db/providers/sqlite.py:65) but this fixture,
    built directly rather than through the provider, did not. Without it, a
    writer bug that points a foreign key at a nonexistent row (the classic
    copy-paste swap of two id sources) inserts silently and every test in
    this suite stays green. MariaDB/InnoDB enforces foreign keys unconditionally,
    so no equivalent pragma is needed on that path.
    """
    url = os.environ.get("SEED_TEST_DATABASE_URL")
    if url:
        rebuild_schema(url)
    else:
        url = f"sqlite:///{tmp_path / 'seed.db'}"
        upgrade_to_head(url)

    engine = create_engine(url)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_conn, connection_record):  # noqa: ANN001, ARG001
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    yield engine
    engine.dispose()
