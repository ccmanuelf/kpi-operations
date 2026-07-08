# PR-1: MariaDB Portability Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the KPI-operations schema and runtime engine fully MariaDB-compatible, and prove it with a real MariaDB CI job — de-risking the database migration before the larger C5 (Alembic) work.

**Architecture:** Three small production-code fixes (an un-indexable `TEXT` column, the app engine's missing `utf8mb4` charset, and the same charset gap in the secondary provider path), each guarded by tests. Because the existing suite runs only on SQLite (which indexes `TEXT` fine and ignores charset), the fixes are verified by a new GitHub Actions job that stands up a `mariadb:11.4` service container and exercises the real engine path.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0, PyMySQL, pytest, GitHub Actions service containers, MariaDB 11.4.

## Global Constraints

- Coverage gate ≥75% must hold (run from `backend/`: `pytest tests/`).
- **No permissive assertions** — every test asserts exactly one expected value/status; never `in [...]`.
- `black --check .`, `flake8 .`, and `mypy backend --ignore-missing-imports` must pass (run from repo root for mypy).
- All 4 required CI checks stay green (`backend-tests`, `frontend-lint-and-tests`, `docker-build`, `e2e-sqlite`); the new MariaDB job is additive.
- Cross-review gate (`/cross-review`) must run for HEAD before `gh pr create`/`gh pr merge`.
- Surgical edits only — touch only what this PR requires. Files under 500 lines.
- The running app's engine is `backend/database.py` (`SessionLocal` binds to it at line 79). The `backend/db/providers/*` system is a secondary path; fix both, but `database.py` is the one that matters at runtime.

---

### Task 1: Fix the un-indexable `client_id_assigned` column

`backend/orm/user.py:62` declares `client_id_assigned` as `Text` with `index=True`. MariaDB cannot index a `TEXT` column without a prefix length (error 1170). The column stores a **comma-separated list** of client IDs (a single client id is `String(50)`), so it needs a generous, index-safe width: `String(500)` = 2000 bytes in utf8mb4, well under InnoDB's 3072-byte index limit.

**Files:**
- Modify: `backend/orm/user.py` (line 11 import, line 62 column)
- Test: `backend/tests/test_mariadb_portability.py` (new)

**Interfaces:**
- Produces: `User.client_id_assigned` is now `String(500)`, `index=True`, nullable. No API/behavior change — same Python `str` values.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_mariadb_portability.py`:

```python
"""MariaDB portability guards.

The dialect-agnostic schema test runs in the default (SQLite) suite. The
integration tests skip unless the app engine is MariaDB (DATABASE_URL points
at MariaDB), which is the case only in the dedicated CI job — see
.github/workflows/ci.yml::mariadb-portability.
"""

from sqlalchemy import String

from backend.orm.user import User


def test_client_id_assigned_is_bounded_string_not_text():
    """MariaDB cannot index TEXT; the column must be a bounded String."""
    col = User.__table__.c.client_id_assigned
    assert isinstance(col.type, String)
    assert col.type.length == 500
    assert col.index is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_mariadb_portability.py::test_client_id_assigned_is_bounded_string_not_text -v`
Expected: FAIL — the current type is `Text` (not `String`), so `isinstance(col.type, String)` is `False`.

- [ ] **Step 3: Apply the fix**

In `backend/orm/user.py`, change the import on line 11 from:

```python
from sqlalchemy import Boolean, DateTime, String, Text
```

to (drop now-unused `Text`):

```python
from sqlalchemy import Boolean, DateTime, String
```

Change line 62 from:

```python
    client_id_assigned: Mapped[Optional[str]] = mapped_column(Text, index=True)
```

to:

```python
    client_id_assigned: Mapped[Optional[str]] = mapped_column(String(500), index=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_mariadb_portability.py::test_client_id_assigned_is_bounded_string_not_text -v`
Expected: PASS

- [ ] **Step 5: Verify no other use of `Text` in the file and lint**

Run: `cd backend && grep -n "Text" orm/user.py && flake8 orm/user.py`
Expected: no `Text` matches; flake8 clean (no unused-import F401).

- [ ] **Step 6: Commit**

```bash
git add backend/orm/user.py backend/tests/test_mariadb_portability.py
git commit -m "fix(db): make USER.client_id_assigned an indexable String(500) for MariaDB"
```

---

### Task 2: Enforce utf8mb4 charset on the MariaDB engine paths

`backend/database.py:38-49` (the engine the app binds to) sets no `connect_args`, so a MariaDB connection inherits the server's default charset instead of `utf8mb4`. The `MySQLProvider` already enforces `utf8mb4` (`backend/db/providers/mysql.py:67-69`); the `MariaDBProvider` does not. Fix both.

**Files:**
- Modify: `backend/database.py:38-49`
- Modify: `backend/db/providers/mariadb.py:54-76`
- Test: `backend/tests/test_mariadb_portability.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: any MariaDB/MySQL engine created by the app or the MariaDB provider uses `charset=utf8mb4`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_mariadb_portability.py`. (The app engine in `database.py` is built at import time, so the provider is unit-tested by mocking `create_engine`; the app engine's charset is proven live in Task 3.)

```python
from unittest.mock import patch

from backend.db.providers.mariadb import MariaDBProvider


def test_mariadb_provider_enforces_utf8mb4():
    """The MariaDB provider must pass charset=utf8mb4 in connect_args."""
    provider = MariaDBProvider()
    with patch("backend.db.providers.mariadb.create_engine") as mock_create_engine:
        provider.create_engine("mysql+pymysql://u:p@localhost:3306/db")
    _, kwargs = mock_create_engine.call_args
    assert kwargs["connect_args"]["charset"] == "utf8mb4"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_mariadb_portability.py::test_mariadb_provider_enforces_utf8mb4 -v`
Expected: FAIL — before the fix the provider calls `create_engine` with no `connect_args`, so `kwargs["connect_args"]` raises `KeyError`.

- [ ] **Step 3: Apply the fix — MariaDB provider**

In `backend/db/providers/mariadb.py`, inside `create_engine`, after the pool overrides (after line 64) and before the `engine = create_engine(...)` call (line 66), add:

```python
        # MariaDB connection charset (parity with MySQLProvider)
        connect_args = kwargs.pop("connect_args", {})
        if "charset" not in connect_args:
            connect_args["charset"] = "utf8mb4"
```

Then add `connect_args=connect_args,` to the `create_engine(...)` call (alongside `pool_pre_ping=True,`):

```python
        engine = create_engine(
            url,
            echo=echo,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,  # Always enable for production
            connect_args=connect_args,
            **kwargs,
        )
```

- [ ] **Step 4: Apply the fix — app engine (`database.py`)**

In `backend/database.py`, change the `else` branch (lines 40-49) `create_engine(...)` call to include `connect_args`:

```python
    else:
        # MySQL/MariaDB configuration: QueuePool with production settings
        engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            poolclass=QueuePool,
            pool_size=settings.DATABASE_POOL_SIZE,  # Base pool size: 20 connections
            max_overflow=settings.DATABASE_MAX_OVERFLOW,  # Additional connections: 10
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,  # Wait timeout: 30 seconds
            pool_recycle=settings.DATABASE_POOL_RECYCLE,  # Recycle after: 3600 seconds (1 hour)
            pool_pre_ping=True,  # Test connections before using (prevents invalid connections)
            connect_args={"charset": "utf8mb4"},  # Ensure UTF-8 (utf8mb4) on MariaDB/MySQL
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_mariadb_portability.py -v`
Expected: the two non-integration tests PASS; integration tests (Task 3) SKIP (no MariaDB engine).

- [ ] **Step 6: Commit**

```bash
git add backend/database.py backend/db/providers/mariadb.py backend/tests/test_mariadb_portability.py
git commit -m "fix(db): enforce utf8mb4 charset on app and provider MariaDB engines"
```

---

### Task 3: Real-MariaDB integration tests (schema DDL + data round-trips)

These prove the fixes against a live MariaDB. They build the **full** schema via `create_all` (the current mechanism — PR-2 will switch this to Alembic), which is exactly what failed before Task 1 (error 1170 on the `TEXT` index). They run only when the app engine is MariaDB.

**Files:**
- Modify: `backend/tests/test_mariadb_portability.py`

**Interfaces:**
- Consumes: `backend.database.engine`, `Base`, `SessionLocal`; `User`; `EventStore`.
- Produces: nothing for later tasks; pure verification.

- [ ] **Step 1: Add the integration tests**

Append to `backend/tests/test_mariadb_portability.py`:

```python
import pytest
from sqlalchemy import inspect, select

from backend.database import Base, SessionLocal, engine

# Populate Base.metadata with EVERY table before create_all. Copy the model-
# import block from backend/alembic/env.py VERBATIM (it is the canonical list
# that registers all core + capacity models); the two imports below are the
# expected shape — replace them with env.py's exact block if it differs.
import backend.orm  # noqa: E402,F401  (registers all core ORM models)
import backend.orm.capacity  # noqa: E402,F401  (registers capacity-planning models)
from backend.orm.event_store import EventStore  # noqa: E402

_IS_MARIADB = "mysql" in str(engine.url).lower()
pytestmark = pytest.mark.skipif(
    not _IS_MARIADB, reason="requires the app engine to be MariaDB (DATABASE_URL=mysql+pymysql://...)"
)


@pytest.fixture(scope="module")
def mariadb_schema():
    """Create the full schema on the live MariaDB, drop it afterwards."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)  # would raise 1170 before the Task 1 fix
    yield
    Base.metadata.drop_all(bind=engine)


def test_full_schema_creates_on_mariadb(mariadb_schema):
    """create_all must succeed and produce the USER table with its index."""
    inspector = inspect(engine)
    assert "USER" in inspector.get_table_names()
    indexed_cols = {c for ix in inspector.get_indexes("USER") for c in ix["column_names"]}
    assert "client_id_assigned" in indexed_cols


def test_user_client_id_assigned_roundtrip(mariadb_schema):
    """A long, multi-byte (utf8mb4) comma-separated value round-trips intact."""
    value = ",".join(f"CLÍENT-Ñ-{i:02d}" for i in range(20))  # ~260 chars, accented
    session = SessionLocal()
    try:
        session.add(
            User(user_id="pt-user-1", username="pt-user-1", email="pt1@example.com",
                 client_id_assigned=value)
        )
        session.commit()
        fetched = session.execute(
            select(User.client_id_assigned).where(User.user_id == "pt-user-1")
        ).scalar_one()
        assert fetched == value
    finally:
        session.close()


def test_event_store_json_roundtrip(mariadb_schema):
    """A JSON column round-trips a nested dict on MariaDB."""
    from datetime import datetime

    payload = {"qty": 12, "nested": {"ok": True, "tags": ["a", "b"]}, "note": " café"}
    session = SessionLocal()
    try:
        session.add(
            EventStore(event_id="pt-evt-1", event_type="TEST", aggregate_type="X",
                       aggregate_id="1", occurred_at=datetime(2026, 6, 26, 12, 0, 0),
                       payload=payload)
        )
        session.commit()
        fetched = session.execute(
            select(EventStore.payload).where(EventStore.event_id == "pt-evt-1")
        ).scalar_one()
        assert fetched == payload
    finally:
        session.close()


def test_app_engine_connection_charset_is_utf8mb4(mariadb_schema):
    """Proves the database.py fix: the app engine connects with utf8mb4."""
    from sqlalchemy import text

    session = SessionLocal()
    try:
        charset = session.execute(text("SELECT @@character_set_connection")).scalar()
        assert charset == "utf8mb4"
    finally:
        session.close()
```

- [ ] **Step 2: Verify they skip cleanly on SQLite**

Run: `cd backend && pytest tests/test_mariadb_portability.py -v`
Expected: the two unit tests (Task 1 + Task 2) PASS; the four integration tests show `SKIPPED` (engine is SQLite locally).

- [ ] **Step 3: (Optional) Verify against a local MariaDB**

```bash
docker run -d --rm --name mdb-pt -e MARIADB_ROOT_PASSWORD=root -e MARIADB_DATABASE=kpi_test -p 3306:3306 mariadb:11.4
# wait ~15s for init, then:
cd backend && DATABASE_URL="mysql+pymysql://root:root@127.0.0.1:3306/kpi_test" pytest tests/test_mariadb_portability.py -v  # pragma: allowlist secret
docker stop mdb-pt
```
Expected: all six tests PASS. (Confirm: on a checkout *before* Task 1, `test_full_schema_creates_on_mariadb` fails with `(1170, "BLOB/TEXT column 'client_id_assigned' used in key specification without a length")`.)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_mariadb_portability.py
git commit -m "test(db): real-MariaDB schema DDL + String/JSON round-trip guards"
```

---

### Task 4: Add the MariaDB service-container CI job

Add a job that stands up `mariadb:11.4` and runs the portability file against it, so the fixes are protected on every PR.

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Produces: a CI job named `mariadb-portability`.

- [ ] **Step 1: Add the job**

In `.github/workflows/ci.yml`, add a new job under `jobs:` (sibling of `backend-tests`):

```yaml
  mariadb-portability:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: backend
    services:
      mariadb:
        image: mariadb:11.4
        env:
          MARIADB_ROOT_PASSWORD: root
          MARIADB_DATABASE: kpi_test
        ports:
          - 3306:3306
        options: >-
          --health-cmd="healthcheck.sh --connect --innodb_initialized"
          --health-interval=10s --health-timeout=5s --health-retries=10
    env:
      DATABASE_URL: mysql+pymysql://root:root@127.0.0.1:3306/kpi_test  # pragma: allowlist secret
      SECRET_KEY: ci-portability-secret-key-not-used-in-prod-0001
    steps:
      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10 # v6.0.3

      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v5.3.0
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: backend/requirements-dev.lock

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install --require-hashes --only-binary=:all: -r requirements-dev.lock

      - name: Run MariaDB portability tests
        run: pytest tests/test_mariadb_portability.py -v
```

- [ ] **Step 2: Validate the workflow YAML locally**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"`
Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add mariadb:11.4 service-container job for portability tests"
```

---

## Post-implementation (PR open + verification)

- [ ] Run full local backend suite from `backend/`: `pytest tests/` — expect green, coverage ≥75%.
- [ ] `black --check .`, `flake8 .` (from `backend/`); `mypy backend --ignore-missing-imports` (from repo root).
- [ ] Push branch; confirm the new `mariadb-portability` job runs and goes green on the PR (this is where the real-MariaDB proof lands).
- [ ] Run `/cross-review` for HEAD (cross-model gate) and `/code-review`.
- [ ] Open PR; merge on green.
- [ ] **Manual admin follow-up (you, as repo admin):** add `mariadb-portability` to the branch-protection required checks on `main` so the MariaDB proof is enforced, not just additive.

## Self-Review (against the spec)

- **Spec coverage:** PR-1 implements spec §"PR-1 — MariaDB portability fixes" (Text→String, utf8mb4, JSON round-trip verification) plus the spec gap "CI runs backend tests on SQLite only → add a MariaDB service-container CI job." ✓
- **Type consistency:** `User.client_id_assigned` = `String(500)` referenced consistently; `EventStore` fields match `backend/orm/event_store.py`. ✓
- **No placeholders:** all steps carry concrete code/commands and expected output. ✓
- Deferred to later PRs (correctly out of PR-1 scope): switching the schema mechanism to Alembic (PR-2 — at which point Task 3's `create_all` becomes `alembic upgrade head`), running the *full* test suite on MariaDB (PR-3), Caddy/DB compose services (PR-3), host bootstrap (PR-4).
