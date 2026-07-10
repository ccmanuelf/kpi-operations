"""Guard: the SQLite-only `julianday` function must never reappear in route handlers.

It compiles on the SQLite test suite but 500s on MariaDB (errno 1305), so a
green suite cannot catch its reintroduction — this static check does.
Use backend.db.sql_functions.date_diff_days instead. `func.date()` is portable
(DATE() exists in both dialects) and is intentionally NOT restricted.
"""

import pathlib


def test_routes_do_not_use_sqlite_only_julianday():
    routes_dir = pathlib.Path(__file__).resolve().parents[2] / "routes"
    offenders = []
    for py in routes_dir.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if "julianday" in text:
            offenders.append(str(py.relative_to(routes_dir.parents[1])))
    assert offenders == []
