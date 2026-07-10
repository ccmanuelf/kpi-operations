"""Both dialect branches of the portable date_diff_days expression (PR: holds MariaDB fix).

Compile-only: no database needed. Renders the expression under the SQLite and
MySQL (== MariaDB) dialects and asserts each emits the correct function form.
"""

from sqlalchemy import Float, column, func, select
from sqlalchemy.dialects import mysql, sqlite

from backend.db.sql_functions import date_diff_days


def _compiled(dialect):
    expr = date_diff_days(func.now(), column("hold_date"))
    return str(select(expr).compile(dialect=dialect, compile_kwargs={"literal_binds": False}))


def test_sqlite_uses_julianday_subtraction():
    sql = _compiled(sqlite.dialect())
    assert "julianday" in sql


def test_mysql_uses_fractional_timestampdiff_seconds():
    sql = _compiled(mysql.dialect())
    assert "TIMESTAMPDIFF(SECOND" in sql
    assert "86400.0" in sql


def test_mysql_does_not_use_integer_day_diff():
    sql = _compiled(mysql.dialect())
    assert "TIMESTAMPDIFF(DAY" not in sql


def test_result_type_is_float():
    expr = date_diff_days(func.now(), column("hold_date"))
    assert isinstance(expr.type, Float)


def test_argument_order_end_minus_start_sqlite():
    # end is func.now(), start is the column: julianday(now) appears before julianday(hold_date)
    sql = _compiled(sqlite.dialect())
    now_idx = sql.index("julianday(CURRENT_TIMESTAMP")
    col_idx = sql.index("julianday(hold_date")
    assert now_idx < col_idx
