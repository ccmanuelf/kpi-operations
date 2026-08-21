"""
Regression tests for the DEMO_MODE gate on the startup auto-seeder (Run 7 C-1).

Before Run 7, the lifespan auto-seeder could execute a destructive schema
rebuild (rebuild_schema, which drops every table) when it decided demo data
was missing or incomplete, and that path was reachable on ANY database --
pointing DATABASE_URL at a populated production database would erase it on
first boot. Post-S1c the destructive rebuild step is gone entirely: Alembic
is the sole schema mechanism (C5) and backend.seed.cli.seed is INSERT-only,
scoped to its own demo-client allowlist, so a failed seed can no longer
half-drop a real database -- the whole step is best-effort.

These tests pin the surviving contract: with DEMO_MODE off, the seeder must
return before touching the database at all -- proven by patching
backend.seed.cli.seed and asserting it is never called (plus the
session-recorder asserting no DB access), NOT by asserting some retired
import is absent, which would pass while proving nothing. With DEMO_MODE on,
the original smart-reseed behavior is preserved (seed empty/incomplete data,
skip complete data), and a seeding failure is logged and swallowed
best-effort rather than crashing the boot.

NOTE: After C3 Task 5, _auto_seed_demo_data and its dependencies live in
backend.bootstrap.lifecycle (not backend.main). After S1c Task 3/4, the
seeder entry point is backend.seed.cli.seed -- backend.scripts.init_demo_
database, backend.db.migrate.rebuild_schema/SchemaRebuildError, and
run_best_effort_unless are no longer part of this path. Tests updated
accordingly.
"""

import logging
from collections import namedtuple

import backend.config
from backend.bootstrap import lifecycle
from backend.seed.cli import ALLOWLIST

_Row = namedtuple("_Row", "client_id")

# Derived from the real seeder allowlist, not hand-listed -- a fixture naming
# different clients than backend.seed.cli.ALLOWLIST actually produces is
# exactly the staleness that let test_demo_mode_with_complete_data_does_not_drop
# pass vacuously pre-S1c (it only checked the retired rebuild_schema wasn't
# called, never that seed() itself was skipped).
_DEMO_CLIENTS = sorted(ALLOWLIST)


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def query(self, *args):
        return _FakeQuery(self._rows)

    def commit(self):
        pass

    def close(self):
        pass


def _install_recorders(monkeypatch, rows):
    """Stub the DB session factory; return session_calls.

    lifecycle._auto_seed_demo_data imports SessionLocal lazily, so patch it
    where it's looked up: backend.database.SessionLocal. This proves the
    check never touches a real database during the suite -- an earlier
    version of this test left the module-level engine unstubbed and mutated
    the developer's default database/kpi_platform.db on every run (Run 7 C-1
    follow-up).
    """
    import backend.database

    session_calls = []

    def _session_factory():
        session_calls.append(1)
        return _FakeSession(rows)

    monkeypatch.setattr(backend.database, "SessionLocal", _session_factory)
    return session_calls


def test_auto_seed_skipped_when_demo_mode_off(monkeypatch):
    """DEMO_MODE off must return BEFORE any database access. Proven by
    patching the seeder and asserting it is never called -- not by asserting
    an import is absent, which would pass while proving nothing."""
    import backend.seed.cli as seed_cli

    calls = []
    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", False)
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    monkeypatch.setattr(seed_cli, "seed", lambda *a, **kw: calls.append(kw))
    session_calls = _install_recorders(monkeypatch, [_Row("REAL-CLIENT")])

    lifecycle._auto_seed_demo_data()

    assert calls == []
    assert session_calls == []


def test_force_reseed_does_not_bypass_demo_gate(monkeypatch):
    """FORCE_RESEED is a demo-mode tool; it must not seed when DEMO_MODE is off."""
    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", False)
    monkeypatch.setenv("FORCE_RESEED", "true")
    session_calls = _install_recorders(monkeypatch, [_Row("REAL-CLIENT")])

    lifecycle._auto_seed_demo_data()

    assert session_calls == []


def test_demo_mode_with_complete_data_does_not_drop(monkeypatch):
    """DEMO_MODE=True with all expected demo clients present must not reseed."""
    import backend.seed.cli as seed_cli

    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", True)
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    rows = [_Row(c) for c in _DEMO_CLIENTS]
    session_calls = _install_recorders(monkeypatch, rows)
    calls = []
    monkeypatch.setattr(seed_cli, "seed", lambda *a, **kw: calls.append(kw))

    lifecycle._auto_seed_demo_data()

    assert session_calls, "demo mode should inspect the database"
    assert calls == []


def test_demo_mode_incomplete_data_reseeds(monkeypatch):
    """DEMO_MODE=True with stale/incomplete data reseeds via backend.seed.cli.seed.

    Post-S1c there is no destructive rebuild step -- seed(..., reset=True) is
    the whole recovery story: INSERT-only, scoped to the demo allowlist, with
    Alembic (not this path) owning schema. Pin that seed() runs exactly once
    with reset=True.
    """
    import backend.seed.cli as seed_cli

    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", True)
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    session_calls = _install_recorders(monkeypatch, [_Row("STALE-CLIENT")])

    calls = []
    monkeypatch.setattr(seed_cli, "seed", lambda *a, **kw: calls.append(kw))

    lifecycle._auto_seed_demo_data()

    assert session_calls
    assert len(calls) == 1
    assert calls[0]["reset"] is True


def test_generic_seed_failure_is_swallowed(monkeypatch, caplog):
    """A seed() Exception is logged and swallowed (best-effort) when calling
    _auto_seed_demo_data directly -- an empty database still routes through
    seed(), which is now the only recovery path (no separate rebuild branch)."""
    import backend.seed.cli as seed_cli

    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", True)
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    _install_recorders(monkeypatch, [])

    def _boom(*a, **kw):
        raise RuntimeError("seed exploded")

    monkeypatch.setattr(seed_cli, "seed", _boom)

    with caplog.at_level(logging.WARNING):
        # Must NOT raise -- generic failures stay best-effort.
        lifecycle._auto_seed_demo_data()

    assert "Auto-seed check failed: seed exploded" in caplog.text


def test_seed_failure_via_lifespan_step_is_swallowed(monkeypatch, caplog):
    """A seed() failure does not crash the boot when invoked exactly as the
    lifespan invokes the step: run_best_effort("demo data seed",
    _auto_seed_demo_data). This replaces the retired
    SchemaRebuildError-is-fatal contract -- post-S1c there is no destructive
    rebuild step, so nothing on this path needs to be fatal; a seeder failure
    is swallowed best-effort like any other startup unit."""
    import backend.seed.cli as seed_cli

    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", True)
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    _install_recorders(monkeypatch, [_Row("STALE-CLIENT")])

    def _boom(*a, **kw):
        raise RuntimeError("seed exploded")

    monkeypatch.setattr(seed_cli, "seed", _boom)

    with caplog.at_level(logging.WARNING):
        # Must NOT raise -- exactly the call the lifespan makes.
        lifecycle.run_best_effort("demo data seed", lifecycle._auto_seed_demo_data)

    assert "Auto-seed check failed: seed exploded" in caplog.text


# --- Cross-worker seed serialization (F1) -----------------------------------
#
# On MariaDB/MySQL the 4 gunicorn workers race the seeder; the entire
# check+seed must run while holding a server-wide GET_LOCK named lock so
# exactly one worker seeds and the losers re-check inside the lock and skip.
# SQLite (single-process here) must take the byte-identical no-lock path. These
# fakes record a single ordered sequence across the lock cursor and the client
# query so we can pin GET_LOCK-before-query-before-RELEASE_LOCK.


class _RecordingCursor:
    def __init__(self, sequence):
        self._sequence = sequence

    def execute(self, sql, params=None):
        if "GET_LOCK" in sql:
            self._sequence.append("GET_LOCK")
        elif "RELEASE_LOCK" in sql:
            self._sequence.append("RELEASE_LOCK")

    def fetchall(self):
        return [(1,)]

    def close(self):
        pass


class _RecordingRawConn:
    def __init__(self, sequence):
        self._sequence = sequence
        self.closed = False

    def cursor(self):
        return _RecordingCursor(self._sequence)

    def close(self):
        self.closed = True


class _FakeDialect:
    def __init__(self, name):
        self.name = name


class _FakeEngine:
    def __init__(self, name, sequence):
        self.dialect = _FakeDialect(name)
        self._sequence = sequence
        self.raw_connection_calls = 0

    def raw_connection(self):
        self.raw_connection_calls += 1
        return _RecordingRawConn(self._sequence)


def _install_seq_engine(monkeypatch, dialect_name, sequence):
    """Patch engine + SessionLocal so both record into a shared ordered list.

    Complete demo clients → no reseed, so the recorded sequence is only the
    lock/query steps (no init_database noise).
    """
    import backend.database

    class _SeqSession:
        def query(self, *args):
            sequence.append("client_query")
            return _FakeQuery([_Row(c) for c in _DEMO_CLIENTS])

        def close(self):
            pass

    monkeypatch.setattr(backend.database, "SessionLocal", lambda: _SeqSession())
    fake_engine = _FakeEngine(dialect_name, sequence)
    monkeypatch.setattr(backend.database, "engine", fake_engine)
    return fake_engine


def test_mysql_dialect_acquires_named_lock_around_client_query(monkeypatch):
    """MariaDB/MySQL: GET_LOCK is taken before the client query and released
    after — the whole check runs inside the named lock (one worker serialized)."""
    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", True)
    monkeypatch.delenv("FORCE_RESEED", raising=False)

    sequence = []
    fake_engine = _install_seq_engine(monkeypatch, "mysql", sequence)

    lifecycle._auto_seed_demo_data()

    assert fake_engine.raw_connection_calls == 1
    assert sequence == ["GET_LOCK", "client_query", "RELEASE_LOCK"]


def test_sqlite_dialect_never_acquires_named_lock(monkeypatch):
    """SQLite is single-process → the no-lock path: GET_LOCK is never called and
    no dedicated raw connection is opened."""
    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", True)
    monkeypatch.delenv("FORCE_RESEED", raising=False)

    sequence = []
    fake_engine = _install_seq_engine(monkeypatch, "sqlite", sequence)

    lifecycle._auto_seed_demo_data()

    assert fake_engine.raw_connection_calls == 0
    assert sequence == ["client_query"]


# --- Shared cross-worker lock helper: metric-dep step + fail-closed skip ------
#
# _run_exclusive_across_workers is reused for BOTH the demo seed and the
# metric→assumption dependency seed. These fakes capture the exact lock name
# passed to GET_LOCK/RELEASE_LOCK and let GET_LOCK's result be pinned so the
# fail-closed (skip-when-not-acquired) contract can be asserted.


class _LockNameCursor:
    def __init__(self, calls, lock_result):
        self._calls = calls
        self._lock_result = lock_result

    def execute(self, sql, params=None):
        if "GET_LOCK" in sql:
            self._calls.append(("GET_LOCK", params[0]))
        elif "RELEASE_LOCK" in sql:
            self._calls.append(("RELEASE_LOCK", params[0]))

    def fetchall(self):
        return [(self._lock_result,)]

    def close(self):
        pass


class _LockNameRawConn:
    def __init__(self, calls, lock_result):
        self._calls = calls
        self._lock_result = lock_result

    def cursor(self):
        return _LockNameCursor(self._calls, self._lock_result)

    def close(self):
        pass


class _LockNameEngine:
    def __init__(self, calls, lock_result=1):
        self.dialect = _FakeDialect("mysql")
        self._calls = calls
        self._lock_result = lock_result

    def raw_connection(self):
        return _LockNameRawConn(self._calls, self._lock_result)


def test_metric_dep_seed_uses_named_lock_with_distinct_name(monkeypatch):
    """seed_metric_dependencies_step runs under the SAME GET_LOCK mechanics as
    the demo seed, with its own lock name 'kpi_metric_dep_seed', so the 4
    gunicorn workers serialize it too (no benign-IntegrityError spam)."""
    import backend.database

    calls = []
    monkeypatch.setattr(backend.database, "engine", _LockNameEngine(calls))
    ran = []
    monkeypatch.setattr(lifecycle, "_seed_metric_dependencies", lambda: ran.append(1))

    lifecycle.seed_metric_dependencies_step()

    assert ran == [1]
    assert calls == [
        ("GET_LOCK", "kpi_metric_dep_seed"),
        ("RELEASE_LOCK", "kpi_metric_dep_seed"),
    ]


def test_lock_not_acquired_skips_fn_and_warns(monkeypatch, caplog):
    """Fail-closed: GET_LOCK returning 0 (timeout) must SKIP fn (never run it
    unlocked, which would recreate the race) and log a warning."""
    import logging

    import backend.database

    calls = []
    monkeypatch.setattr(backend.database, "engine", _LockNameEngine(calls, lock_result=0))
    ran = []

    with caplog.at_level(logging.WARNING):
        lifecycle._run_exclusive_across_workers("kpi_demo_seed", 330, lambda: ran.append(1))

    assert ran == []
    assert "not acquired" in caplog.text
    # The lock is still released/closed even on the skip path.
    assert calls == [("GET_LOCK", "kpi_demo_seed"), ("RELEASE_LOCK", "kpi_demo_seed")]
