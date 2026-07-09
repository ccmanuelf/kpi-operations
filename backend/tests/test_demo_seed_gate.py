"""
Regression tests for the DEMO_MODE gate on the startup auto-seeder (Run 7 C-1).

The lifespan auto-seeder can execute a destructive schema rebuild
(rebuild_schema, which drops every table) when it decides demo data is missing
or incomplete. Before Run 7 that path was reachable on ANY database — pointing
DATABASE_URL at a populated production database would erase it on first boot.
These tests pin the contract: with DEMO_MODE off, the seeder must return before
touching the database at all; with DEMO_MODE on, the original smart-reseed
behavior is preserved. They also pin the fatality contract (C5 collapse): a
failed rebuild is fatal, a generic seeding failure stays best-effort.

NOTE: After C3 Task 5, _auto_seed_demo_data and its dependencies live in
backend.bootstrap.lifecycle (not backend.main). Tests updated accordingly.
"""

from collections import namedtuple

import pytest

import backend.config
from backend.bootstrap import lifecycle
from backend.bootstrap.lifecycle import run_best_effort_unless
from backend.db.migrate import SchemaRebuildError

_Row = namedtuple("_Row", "client_id")

_DEMO_CLIENTS = ["ACME-MFG", "TEXTILE-PRO", "FASHION-WORKS", "QUALITY-STITCH", "GLOBAL-APPAREL"]


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
    """Stub the DB session factory and destructive rebuild; return (session_calls, rebuild_calls).

    lifecycle._auto_seed_demo_data imports SessionLocal + rebuild_schema lazily,
    so patch them where they are looked up: backend.database.SessionLocal and
    backend.db.migrate.rebuild_schema. Patching rebuild_schema also proves the
    reseed never touches a real database during the suite (an earlier version of
    this test left the module-level engine unstubbed and mutated the developer's
    default database/kpi_platform.db on every run — Run 7 C-1 follow-up).
    """
    import backend.database
    import backend.db.migrate as migrate_mod

    session_calls = []
    rebuild_calls = []

    def _session_factory():
        session_calls.append(1)
        return _FakeSession(rows)

    monkeypatch.setattr(backend.database, "SessionLocal", _session_factory)
    monkeypatch.setattr(migrate_mod, "rebuild_schema", lambda *a, **kw: rebuild_calls.append(1))
    return session_calls, rebuild_calls


def test_auto_seed_skipped_when_demo_mode_off(monkeypatch):
    """DEMO_MODE=False must return before any database access."""
    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", False)
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    session_calls, rebuild_calls = _install_recorders(monkeypatch, [_Row("REAL-CLIENT")])

    lifecycle._auto_seed_demo_data()

    assert session_calls == []
    assert rebuild_calls == []


def test_force_reseed_does_not_bypass_demo_gate(monkeypatch):
    """FORCE_RESEED is a demo-mode tool; it must not rebuild when DEMO_MODE is off."""
    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", False)
    monkeypatch.setenv("FORCE_RESEED", "true")
    session_calls, rebuild_calls = _install_recorders(monkeypatch, [_Row("REAL-CLIENT")])

    lifecycle._auto_seed_demo_data()

    assert session_calls == []
    assert rebuild_calls == []


def test_demo_mode_with_complete_data_does_not_drop(monkeypatch):
    """DEMO_MODE=True with all expected demo clients present must not reseed."""
    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", True)
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    rows = [_Row(c) for c in _DEMO_CLIENTS]
    session_calls, rebuild_calls = _install_recorders(monkeypatch, rows)

    lifecycle._auto_seed_demo_data()

    assert session_calls, "demo mode should inspect the database"
    assert rebuild_calls == []


def test_demo_mode_incomplete_data_reseeds(monkeypatch):
    """DEMO_MODE=True with stale/incomplete data preserves the smart-reseed behavior.

    Post-C5, the reseed rebuilds the schema via the shared rebuild_schema helper
    (drop_all + drop alembic_version + upgrade_to_head, all internal to the
    helper), then runs init_database. Pin that rebuild_schema runs exactly once,
    strictly before the seed — the load-bearing rebuild order.
    """
    import backend.db.migrate as migrate_mod
    import backend.scripts.init_demo_database as seeder_mod

    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", True)
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    session_calls, _ = _install_recorders(monkeypatch, [_Row("STALE-CLIENT")])

    sequence = []
    monkeypatch.setattr(migrate_mod, "rebuild_schema", lambda *a, **kw: sequence.append("rebuild_schema"))

    seed_calls = []

    def _seed():
        sequence.append("init_database")
        seed_calls.append(1)

    monkeypatch.setattr(seeder_mod, "init_database", _seed)

    lifecycle._auto_seed_demo_data()

    assert session_calls
    assert seed_calls == [1]
    assert sequence == ["rebuild_schema", "init_database"]


def test_schema_rebuild_error_is_fatal_out_of_lifespan_seed(monkeypatch):
    """A SchemaRebuildError from the reseed must propagate out of the lifespan
    seed step exactly as the lifespan invokes it (run_best_effort_unless), so a
    half-rebuilt database crashes the boot instead of serving 500s."""
    import backend.db.migrate as migrate_mod

    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", True)
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    _install_recorders(monkeypatch, [_Row("STALE-CLIENT")])

    def _boom(*a, **kw):
        raise SchemaRebuildError("half-rebuilt")

    monkeypatch.setattr(migrate_mod, "rebuild_schema", _boom)

    with pytest.raises(SchemaRebuildError):
        run_best_effort_unless("demo data seed", lifecycle._auto_seed_demo_data, SchemaRebuildError)


def test_generic_seed_failure_is_swallowed(monkeypatch):
    """A non-rebuild seeding Exception is logged and swallowed (best-effort),
    invoked exactly as the lifespan does."""
    import backend.scripts.init_demo_database as seeder_mod

    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", True)
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    # Empty DB (no rows) → no rebuild path; init_database runs and blows up.
    _install_recorders(monkeypatch, [])

    def _boom():
        raise RuntimeError("seed exploded")

    monkeypatch.setattr(seeder_mod, "init_database", _boom)

    # Must NOT raise — generic failures stay best-effort.
    run_best_effort_unless("demo data seed", lifecycle._auto_seed_demo_data, SchemaRebuildError)
