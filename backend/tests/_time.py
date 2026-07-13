"""Deterministic clock freeze for date-boundary tests (dependency-free).

Some tests capture the current date at import time and compare it against
production code that computes `date.today()` at call time; across UTC midnight
those disagree and the test flakes. `freeze_today` patches the `date` symbol in
named production modules to a subclass whose `today()` returns a fixed date, so
both sides see the same day. Test-only; `monkeypatch` reverts after each test.
"""

import importlib
from datetime import date

import pytest

FROZEN_TODAY = date(2026, 6, 15)  # mid-month: no month/year-boundary arithmetic surprises


class _FrozenDate(date):
    """A date whose today() is pinned. Subclassing date keeps construction,
    arithmetic, ordering, and isinstance() working; only today() is overridden."""

    @classmethod
    def today(cls) -> "_FrozenDate":
        return FROZEN_TODAY  # type: ignore[return-value]


def freeze_today(monkeypatch: "pytest.MonkeyPatch", *module_names: str) -> date:
    """Patch `date` to `_FrozenDate` in each named production module so its
    `date.today()` returns FROZEN_TODAY. Returns FROZEN_TODAY for convenience.

    Each module must reference `date` as a module global (i.e. `from datetime
    import date`), which the target modules do.
    """
    for name in module_names:
        module = importlib.import_module(name)
        monkeypatch.setattr(module, "date", _FrozenDate)
    return FROZEN_TODAY
