"""Portable SQL expressions for cross-dialect date arithmetic (SQLite ↔ MariaDB).

`func.julianday()` is SQLite-only and 500s on MariaDB (errno 1305). This module
provides an ORM-level, dialect-compiled replacement so route handlers can build
date-difference expressions without hardcoding a dialect-specific function.

SQLAlchemy reports MariaDB (pymysql) as dialect "mysql", so the "mysql" compiler
covers MariaDB; the default compiler mirrors it for any other backend.
"""

from typing import Any

from sqlalchemy import Float
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import FunctionElement


class date_diff_days(FunctionElement):  # noqa: N801 — SQLAlchemy expression convention is lowercase
    """Difference between two datetime expressions, in FRACTIONAL days (end - start).

    Usage: date_diff_days(end_expr, start_expr). Compose it anywhere a column
    expression is valid (SELECT, WHERE, ORDER BY, func.avg(...)).
    """

    name = "date_diff_days"
    type = Float()
    inherit_cache = True


@compiles(date_diff_days, "sqlite")
def _date_diff_days_sqlite(element: Any, compiler: Any, **kw: Any) -> str:
    end, start = list(element.clauses)
    return f"julianday({compiler.process(end, **kw)}) - julianday({compiler.process(start, **kw)})"


@compiles(date_diff_days, "mysql")
def _date_diff_days_mysql(element: Any, compiler: Any, **kw: Any) -> str:
    # MariaDB is reported as "mysql". TIMESTAMPDIFF(unit, a, b) = b - a, so pass
    # (start, end) to get end - start. SECOND / 86400.0 preserves SQLite's
    # fractional-day result (integer TIMESTAMPDIFF(DAY) would truncate).
    end, start = list(element.clauses)
    return f"TIMESTAMPDIFF(SECOND, {compiler.process(start, **kw)}, {compiler.process(end, **kw)}) / 86400.0"


@compiles(date_diff_days)
def _date_diff_days_default(element: Any, compiler: Any, **kw: Any) -> str:
    end, start = list(element.clauses)
    return f"TIMESTAMPDIFF(SECOND, {compiler.process(start, **kw)}, {compiler.process(end, **kw)}) / 86400.0"
