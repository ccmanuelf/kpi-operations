"""The freeze_today test helper must deterministically pin date.today() in a
named production module to FROZEN_TODAY (dependency-free clock freeze)."""

from datetime import date

from backend.tests._time import FROZEN_TODAY, freeze_today


def test_frozen_today_is_the_fixed_date():
    assert FROZEN_TODAY == date(2026, 6, 15)


def test_freeze_today_pins_a_module_date_today(monkeypatch):
    import backend.crud.employee_line_assignment as mod

    # After freezing, the module's date.today() returns exactly FROZEN_TODAY
    # regardless of the wall clock — that pinning is what this test verifies.
    returned = freeze_today(monkeypatch, "backend.crud.employee_line_assignment")
    assert returned == FROZEN_TODAY
    assert mod.date.today() == FROZEN_TODAY


def test_frozen_date_still_constructs_and_compares(monkeypatch):
    import backend.crud.employee_line_assignment as mod

    freeze_today(monkeypatch, "backend.crud.employee_line_assignment")
    # date(...) construction and isinstance still behave (subclass of date).
    explicit = mod.date(2026, 1, 1)
    assert explicit == date(2026, 1, 1)
    assert isinstance(mod.date.today(), date)
