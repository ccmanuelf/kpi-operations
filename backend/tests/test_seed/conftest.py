import os

import pytest
from sqlalchemy import Engine, create_engine, event

from backend.db.migrate import rebuild_schema, upgrade_to_head

#: URL prefixes that name a MariaDB/MySQL server. SEED_TEST_DATABASE_URL
#: exists for exactly one purpose -- running this suite against the live
#: MariaDB service in ci.yml::mariadb-portability -- so anything else set
#: there is a broken CI job, not an alternative configuration.
MARIADB_URL_PREFIXES = ("mysql", "mariadb")


def resolve_seed_test_url(sqlite_path) -> str:
    """Which database this suite runs against, and the reason it refuses to
    guess.

    UNSET means "developer laptop": a file-backed SQLite database (not
    in-memory, because the materializer opens its own connection) unique to
    the calling test, built by Alembic. Alembic, not create_all: C5 made
    Alembic the single schema mechanism and test_no_create_all_outside_alembic
    enforces it.

    SET means "the mariadb-portability CI job", which points this suite at a
    live MariaDB -- where this repo's real dialect-only bug class lives (spec
    section 8). rebuild_schema, not upgrade_to_head, on that path: MariaDB is
    one shared, persistent service across every test in this suite, so each
    test must drop and rebuild the schema to get the same guaranteed-empty
    starting point tmp_path gives the SQLite path for free -- without it, the
    second test to run would collide on the first test's UNIQUE constraints
    (employee_code, username, email, per-client product/line codes, ...).

    SET BUT NOT MARIADB raises, and that is the whole point of this function
    existing. The check this replaces was `if url:` -- bare truthiness -- so
    an empty or unresolved SEED_TEST_DATABASE_URL fell through to the SQLite
    branch in total silence: not a skip, not an error. Stopping the MariaDB
    container and running the CI step with SEED_TEST_DATABASE_URL= gave
    `151 passed`, exit 0, zero skipped, with no database anywhere -- a job
    whose entire stated purpose is catching MariaDB-only behaviour, passing
    without ever reaching MariaDB. The trigger is not exotic:
    `${{ env.DATABASE_URL }}` resolves to the empty string if the job-level
    `env:` key is renamed, moved to step level, or the `mariadb` service block
    is dropped, and the workflow stays valid either way.

    The sibling step at ci.yml:319 is defended against exactly this by parsing
    its junit XML and asserting `skipped == "0"` ("job proves nothing"). This
    suite cannot borrow that defence, because it never skips -- it degrades.
    So the refusal lives here instead, and
    test_the_seed_fixtures_refuse_a_seed_test_database_url_that_is_not_mariadb
    pins it.
    """
    url = os.environ.get("SEED_TEST_DATABASE_URL")
    if url is None:
        url = f"sqlite:///{sqlite_path}"
        upgrade_to_head(url)
        return url

    if not url.startswith(MARIADB_URL_PREFIXES):
        raise RuntimeError(
            f"SEED_TEST_DATABASE_URL is set to {url!r}, which does not name a MariaDB server "
            f"(expected one of {MARIADB_URL_PREFIXES}). This variable exists only for "
            "ci.yml::mariadb-portability's 'Seed suite on MariaDB' step; an empty or unresolved "
            "value used to fall back to SQLite silently, which let that step pass with no database "
            "at all. Unset it to run on SQLite deliberately."
        )

    rebuild_schema(url)
    return url


def seed_test_engine(url: str) -> Engine:
    """An Engine on `url`, with SQLite's foreign keys switched ON.

    Foreign keys are OFF by default on a bare create_engine(url) -- SQLite
    does not enforce them without PRAGMA foreign_keys=ON, which the app's own
    SQLiteProvider sets (backend/db/providers/sqlite.py:65) but this fixture,
    built directly rather than through the provider, did not. Without it, a
    writer bug that points a foreign key at a nonexistent row (the classic
    copy-paste swap of two id sources) inserts silently and every test in this
    suite stays green. MariaDB/InnoDB enforces foreign keys unconditionally,
    so no equivalent pragma is needed on that path.
    """
    engine = create_engine(url)

    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_conn, connection_record):  # noqa: ANN001, ARG001
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


@pytest.fixture
def seed_engine(tmp_path):
    """A real database with the schema built by Alembic.

    Which database, and why an unusable SEED_TEST_DATABASE_URL is fatal rather
    than a silent SQLite fallback: see `resolve_seed_test_url`. Why the SQLite
    path needs a PRAGMA: see `seed_test_engine`.
    """
    engine = seed_test_engine(resolve_seed_test_url(tmp_path / "seed.db"))
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def seed_engine_module(tmp_path_factory):
    """Module-scoped twin of `seed_engine`, same body, for suites that seed the
    FULL profile once and run several assertions against the result.

    FULL is 39,400 rows and seeds in ~1.3s on SQLite -- affordable per test,
    but a module full of scripted-event assertions would otherwise pay that
    cost eight times over for identical output. `tmp_path_factory` in place of
    `tmp_path` because the per-test fixture is function-scoped and cannot be
    depended on by a module-scoped one.
    """
    engine = seed_test_engine(resolve_seed_test_url(tmp_path_factory.mktemp("seed_module") / "seed.db"))
    yield engine
    engine.dispose()
