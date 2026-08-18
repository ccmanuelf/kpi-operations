import pytest
from sqlalchemy import create_engine, event

from backend.db.migrate import upgrade_to_head


@pytest.fixture
def seed_engine(tmp_path):
    """A real file-backed SQLite database with the schema built by Alembic.

    Alembic, not create_all: C5 made Alembic the single schema mechanism and
    test_no_create_all_outside_alembic enforces it. File-backed, not
    in-memory, because the materializer opens its own connection.

    Foreign keys are OFF by default on a bare create_engine(url) -- SQLite
    does not enforce them without PRAGMA foreign_keys=ON, which the app's own
    SQLiteProvider sets (backend/db/providers/sqlite.py:65) but this fixture,
    built directly rather than through the provider, did not. Without it, a
    writer bug that points a foreign key at a nonexistent row (the classic
    copy-paste swap of two id sources) inserts silently and every test in
    this suite stays green.
    """
    url = f"sqlite:///{tmp_path / 'seed.db'}"
    upgrade_to_head(url)
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_conn, connection_record):  # noqa: ANN001, ARG001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    yield engine
    engine.dispose()
