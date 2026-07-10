"""Guard: the SQLite-only `julianday` function must never appear in application code.

It compiles on the SQLite test suite but 500s on MariaDB (errno 1305), so a
green suite cannot catch its reintroduction — this static check does. Use
backend.db.sql_functions.date_diff_days instead. `func.date()` is portable
(DATE() exists in both dialects) and is intentionally NOT restricted.

Two files legitimately contain the token and are allow-listed:
  - backend/db/sql_functions.py  — the portable helper's SQLite compiler emits it
  - backend/db/dialects/sqlite.py — the SQLite dialect adapter's date-diff SQL
"""

import pathlib

# Paths (relative to the backend/ package root) where `julianday` is a correct,
# dialect-scoped emission rather than a portability bug.
_ALLOWLIST = {
    "db/sql_functions.py",
    "db/dialects/sqlite.py",
}


def test_application_code_has_no_sqlite_only_julianday():
    backend_root = pathlib.Path(__file__).resolve().parents[2]
    assert backend_root.is_dir(), f"backend root not found at {backend_root}"
    offenders = []
    for py in backend_root.rglob("*.py"):
        rel = py.relative_to(backend_root).as_posix()
        # Skip the test tree (this guard + fixtures reference the token in strings)
        # and the .venv, and the allow-listed legitimate emitters.
        if rel.startswith("tests/") or "/.venv/" in f"/{rel}" or rel.startswith(".venv/"):
            continue
        if rel in _ALLOWLIST:
            continue
        # Case-insensitive: SQLAlchemy's func preserves attribute case, so
        # func.JULIANDAY(...) emits literal JULIANDAY(...) — accepted by SQLite
        # (SQL functions are case-insensitive) but still absent on MariaDB.
        if "julianday" in py.read_text(encoding="utf-8").lower():
            offenders.append(rel)
    assert offenders == []
