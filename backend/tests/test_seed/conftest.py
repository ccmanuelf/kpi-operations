import pytest
from sqlalchemy import create_engine

from backend.db.migrate import upgrade_to_head


@pytest.fixture
def seed_engine(tmp_path):
    """A real file-backed SQLite database with the schema built by Alembic.

    Alembic, not create_all: C5 made Alembic the single schema mechanism and
    test_no_create_all_outside_alembic enforces it. File-backed, not
    in-memory, because the materializer opens its own connection.
    """
    url = f"sqlite:///{tmp_path / 'seed.db'}"
    upgrade_to_head(url)
    engine = create_engine(url)
    yield engine
    engine.dispose()
