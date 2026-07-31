"""Regression test for ISSUE-001 (e2e-sweep): GET /api/kpi/oee/trend 500 on
MariaDB.

Root cause: QualityEntry.units_passed/units_inspected are Integer columns.
MariaDB's SUM() over an exact-value (integer) column is promoted to
decimal.Decimal by the DBAPI driver; SQLite's SUM() over the same column
stays int. `get_oee_trend()` built `qual_results` from the raw (uncoerced)
query rows, so on MariaDB `quality` stayed a Decimal while `performance`
(explicitly float()-coerced a few lines above) stayed a float. The OEE
formula `(availability/100) * (performance/100) * (quality/100) * 100` then
mixed float and Decimal operands, which Python's Decimal type rejects:
`TypeError: unsupported operand type(s) for *: 'float' and 'decimal.Decimal'`.

SQLite can't reproduce this natively (its SUM() never promotes to Decimal),
so this test drives `get_oee_trend()` directly with a fake `db`/`scope` that
returns Decimal-typed aggregate rows -- exactly what the MariaDB driver
would hand back -- to force the boundary condition deterministically.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Iterator, List

import pytest

from backend.auth.jwt import ClientScope
from backend.routes.kpi.trends import get_oee_trend


class _Row:
    """Minimal stand-in for a SQLAlchemy Row: arbitrary named attributes."""

    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class _FakeQuery:
    """Chainable stand-in for a SQLAlchemy Query that just returns fixed rows."""

    def __init__(self, rows: List[_Row]) -> None:
        self._rows = rows

    def filter(self, *args: Any, **kwargs: Any) -> "_FakeQuery":
        return self

    def group_by(self, *args: Any, **kwargs: Any) -> "_FakeQuery":
        return self

    def order_by(self, *args: Any, **kwargs: Any) -> "_FakeQuery":
        return self

    def all(self) -> List[_Row]:
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDB:
    """Stand-in Session whose .query() yields pre-built FakeQuery objects in
    the exact order get_oee_trend() issues them: performance, quality,
    downtime."""

    def __init__(self, query_sequence: List[_FakeQuery]) -> None:
        self._seq: Iterator[_FakeQuery] = iter(query_sequence)

    def query(self, *args: Any, **kwargs: Any) -> _FakeQuery:
        return next(self._seq)


ALL_CLIENTS_SCOPE = ClientScope(client_ids=None)


def _mariadb_style_rows(day: str):
    """One day of data shaped exactly like what the MariaDB driver returns:
    Integer-column SUM()s arrive as decimal.Decimal."""
    perf_query = _FakeQuery([_Row(date=day, performance=Decimal("92.5000"), entries=3)])
    qual_query = _FakeQuery([_Row(date=day, passed=Decimal("950"), inspected=Decimal("1000"))])
    dt_query = _FakeQuery([_Row(date=day, downtime_mins=Decimal("30"))])
    return [perf_query, qual_query, dt_query]


def test_oee_trend_crashes_pre_fix_reasoning():
    """Documents the exact TypeError the fix eliminates (not a live assertion
    against production code -- see the module docstring and #145-style class
    sweep: this is the boundary condition, reproduced directly)."""
    performance = 92.5  # float, as perf_results coerces via float()
    quality = Decimal("950") / Decimal("1000") * 100  # uncoerced MariaDB SUM() ratio
    availability = 87.5
    with pytest.raises(TypeError):
        (availability / 100) * (performance / 100) * (quality / 100) * 100  # noqa: B018


def test_get_oee_trend_handles_decimal_quality_from_mariadb():
    """The actual regression: get_oee_trend() must not crash when the DB
    driver hands back Decimal for the quality (units_passed/units_inspected)
    aggregate, even though performance/availability are floats."""
    day = "2026-06-15"
    db = _FakeDB(_mariadb_style_rows(day))

    result = get_oee_trend(
        start_date=date(2026, 6, 15),
        end_date=date(2026, 6, 15),
        client_id=None,
        db=db,
        current_user=None,
        scope=ALL_CLIENTS_SCOPE,
    )

    assert len(result) == 1
    assert result[0]["date"] == day
    # availability = (24 - 0.5) / 24 * 100 = 97.9166...; performance = 92.5;
    # quality = 950/1000*100 = 95.0
    # oee = 0.979166.. * 0.925 * 0.95 * 100 = 86.04 (rounded)
    assert result[0]["value"] == pytest.approx(86.04, abs=0.01)


def test_get_oee_trend_handles_missing_quality_data():
    """No quality rows at all -> falls back to the 97 default (int); must not
    crash when combined with Decimal-shaped performance/downtime rows either."""
    day = "2026-06-16"
    perf_query = _FakeQuery([_Row(date=day, performance=Decimal("100.0000"), entries=1)])
    qual_query = _FakeQuery([])  # no quality entries that day
    dt_query = _FakeQuery([_Row(date=day, downtime_mins=Decimal("0"))])
    db = _FakeDB([perf_query, qual_query, dt_query])

    result = get_oee_trend(
        start_date=date(2026, 6, 16),
        end_date=date(2026, 6, 16),
        client_id=None,
        db=db,
        current_user=None,
        scope=ALL_CLIENTS_SCOPE,
    )

    assert len(result) == 1
    assert result[0]["date"] == day
    # availability = 100, performance = 100, quality defaults to 97 -> oee = 97.0
    assert result[0]["value"] == pytest.approx(97.0, abs=0.01)
