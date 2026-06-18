"""
Regression tests for the DEMO_MODE gate on the startup auto-seeder (Run 7 C-1).

The lifespan auto-seeder can execute Base.metadata.drop_all() when it decides
demo data is missing or incomplete. Before Run 7 that path was reachable on
ANY database — pointing DATABASE_URL at a populated production database would
erase it on first boot. These tests pin the contract: with DEMO_MODE off, the
seeder must return before touching the database at all; with DEMO_MODE on,
the original smart-reseed behavior is preserved.

NOTE: After C3 Task 5, _auto_seed_demo_data and its dependencies live in
backend.bootstrap.lifecycle (not backend.main). Tests updated accordingly.
"""

from collections import namedtuple

import backend.config
from backend.bootstrap import lifecycle

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
    """Stub out the DB layer; return (session_calls, drop_calls, create_calls)."""
    import backend.database

    session_calls = []
    drop_calls = []
    create_calls = []

    def _session_factory():
        session_calls.append(1)
        return _FakeSession(rows)

    monkeypatch.setattr(backend.database, "SessionLocal", _session_factory)
    monkeypatch.setattr(lifecycle.Base.metadata, "drop_all", lambda **kw: drop_calls.append(kw))
    monkeypatch.setattr(lifecycle.Base.metadata, "create_all", lambda **kw: create_calls.append(kw))
    return session_calls, drop_calls, create_calls


def test_auto_seed_skipped_when_demo_mode_off(monkeypatch):
    """DEMO_MODE=False must return before any database access."""
    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", False)
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    session_calls, drop_calls, _ = _install_recorders(monkeypatch, [_Row("REAL-CLIENT")])

    lifecycle._auto_seed_demo_data()

    assert session_calls == []
    assert drop_calls == []


def test_force_reseed_does_not_bypass_demo_gate(monkeypatch):
    """FORCE_RESEED is a demo-mode tool; it must not drop tables when DEMO_MODE is off."""
    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", False)
    monkeypatch.setenv("FORCE_RESEED", "true")
    session_calls, drop_calls, _ = _install_recorders(monkeypatch, [_Row("REAL-CLIENT")])

    lifecycle._auto_seed_demo_data()

    assert session_calls == []
    assert drop_calls == []


def test_demo_mode_with_complete_data_does_not_drop(monkeypatch):
    """DEMO_MODE=True with all expected demo clients present must not reseed."""
    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", True)
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    rows = [_Row(c) for c in _DEMO_CLIENTS]
    session_calls, drop_calls, _ = _install_recorders(monkeypatch, rows)

    lifecycle._auto_seed_demo_data()

    assert session_calls, "demo mode should inspect the database"
    assert drop_calls == []


def test_demo_mode_incomplete_data_reseeds(monkeypatch):
    """DEMO_MODE=True with stale/incomplete data preserves the smart-reseed behavior."""
    import backend.scripts.init_demo_database as seeder_mod

    monkeypatch.setattr(backend.config.settings, "DEMO_MODE", True)
    monkeypatch.delenv("FORCE_RESEED", raising=False)
    session_calls, drop_calls, create_calls = _install_recorders(monkeypatch, [_Row("STALE-CLIENT")])

    seed_calls = []
    monkeypatch.setattr(seeder_mod, "init_database", lambda: seed_calls.append(1))

    lifecycle._auto_seed_demo_data()

    assert session_calls
    assert len(drop_calls) == 1
    assert len(create_calls) == 1
    assert seed_calls == [1]
