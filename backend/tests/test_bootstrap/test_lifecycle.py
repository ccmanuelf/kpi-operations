# backend/tests/test_bootstrap/test_lifecycle.py
import logging
import pytest
from backend.bootstrap import lifecycle


def test_run_best_effort_swallows_and_warns(caplog):
    def boom():
        raise RuntimeError("nope")

    with caplog.at_level(logging.WARNING):
        lifecycle.run_best_effort("step x", boom)  # must NOT raise
    assert any("step x failed" in r.message for r in caplog.records)


def test_run_best_effort_runs_fn():
    calls = []
    lifecycle.run_best_effort("ok", lambda: calls.append(1))
    assert calls == [1]


def test_init_schema_is_fatal_on_error(monkeypatch):
    def boom(bind):
        raise RuntimeError("db down")

    monkeypatch.setattr(lifecycle.Base.metadata, "create_all", boom)
    with pytest.raises(RuntimeError):
        lifecycle.init_schema()


def test_start_schedulers_noop_when_none(monkeypatch):
    monkeypatch.setattr(lifecycle, "report_scheduler", None)
    monkeypatch.setattr(lifecycle, "dual_view_scheduler", None)
    lifecycle.start_schedulers()  # must not raise
    lifecycle.stop_schedulers()
