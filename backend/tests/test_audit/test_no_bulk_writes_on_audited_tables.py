"""Structural guard: nothing may write an audited table behind the ORM's back.

Capture hangs off SQLAlchemy's *mapper-level* persistence events
(``after_insert`` / ``before_update`` / ``before_delete``), which fire only for
rows the ORM unit of work actually persists. Four common shapes bypass them
entirely and would silently punch a hole in the trail:

1. ``session.bulk_save_objects()`` / ``bulk_insert_mappings()`` /
   ``bulk_update_mappings()`` -- documented by SQLAlchemy as skipping the unit
   of work, and therefore the mapper events.
2. ``session.query(Model).delete()`` / ``.update({...})`` -- these compile
   straight to a single ``DELETE``/``UPDATE`` statement; no instances are
   loaded, so no per-row event fires.
3. ``session.execute(delete(Model))`` / ``update(...)`` / ``insert(...)``
   (Core DML, 2.0 style) -- same reason.
4. Raw SQL: ``text("DELETE FROM WORK_ORDER ...")`` and friends.

Case 1 is table-agnostic (the table isn't knowable statically from a mappings
call), so it is banned outright in application code. Cases 2-4 are flagged only
when the statement names one of the 14 audited tables -- bulk-updating
PRODUCTION_ENTRY is a legitimate performance choice and stays allowed.

This guard exists because the review found no test preventing a *future* bulk
write from being introduced. The existing behavioural tests all prove capture
works on the ORM path; none of them can notice a new code path that never
touches it.

Deliberately AST-based, not regex-based, for the structural cases: a regex for
``.delete()`` cannot tell ``db.query(WorkOrder).delete()`` (a bypass) from
``db.delete(work_order)`` (the captured path), and this repo has already been
bitten by a guard regex that a plain import alias evaded
(``test_mariadb_portability.py::test_cast_date_regex_catches_aliased_imports``).
"""

import ast
import pathlib
import re
from typing import Dict, List, Set

import pytest

from backend.audit.registry import AUDITED_TABLES
from backend.database import Base
from backend.orm import register_all_models

BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent

#: Directories under backend/ this guard does not scan, with why.
SKIPPED_DIRS = {
    "tests",  # the suite deliberately sets up and tears down rows in bulk
    "alembic",  # schema migrations are DDL/DML by definition and predate capture
    ".venv",
    "__pycache__",
    "htmlcov",
}

#: Deliberate, reviewed exceptions: "<path>:<symbol or SQL fragment>" -> reason.
#: Each entry is an admission that this code really does bypass the audit trail
#: and that it is acceptable there. Adding one is a decision, not a formality.
ALLOWED_BYPASSES: Dict[str, str] = {
    "scripts/seed_defect_types.py:DEFECT_TYPE_CATALOG": (
        "standalone re-seeding script, run by an operator against a fresh/reset database, not a user "
        "decision made through the app; it clears the whole catalog and rewrites it from a static list. "
        "It runs on its own raw Core connection with no ORM session, so capture could not observe it "
        "anyway, and the equivalent in-app seeders are already wrapped in audit_suppressed()."
    ),
}

BULK_METHODS = {"bulk_save_objects", "bulk_insert_mappings", "bulk_update_mappings"}
CORE_DML_FUNCS = {"insert", "update", "delete"}

#: Calls whose string arguments are executed as SQL. Raw-SQL scanning is scoped
#: to these deliberately: a first cut scanned EVERY string constant and matched
#: docstring prose ("Update attendance record ... SECURITY: verifies the user's
#: CLIENT access"), producing 40+ false positives. A guard nobody can keep green
#: gets deleted, so it only looks where SQL actually is.
SQL_EXECUTING_CALLS = {"text", "execute", "exec_driver_sql", "executescript"}

#: The table name must follow the DML keyword directly (optionally quoted), so
#: a sentence merely containing both a verb and a table name cannot match.
RAW_DML_RE = re.compile(
    r"(?:insert\s+into|delete\s+from|replace\s+into|truncate\s+table|update)\s+[\"'`\[]?(\w+)",
    re.IGNORECASE,
)


def _model_name_to_table() -> Dict[str, str]:
    """Map every ORM class name (and its __tablename__) to its table name."""
    register_all_models()
    mapping: Dict[str, str] = {}
    for mapper in Base.registry.mappers:
        table = mapper.local_table
        if table is None:
            continue
        mapping[mapper.class_.__name__] = table.name
        mapping[table.name] = table.name
    return mapping


MODEL_TO_TABLE = _model_name_to_table()


def _app_python_files() -> List[pathlib.Path]:
    files = []
    for py in BACKEND_ROOT.rglob("*.py"):
        if SKIPPED_DIRS & set(py.parts):
            continue
        files.append(py)
    return sorted(files)


def _named_audited_tables(node: ast.AST) -> Set[str]:
    """Audited table names referenced by any Name/Attribute inside `node`."""
    found: Set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            candidate = MODEL_TO_TABLE.get(sub.id)
        elif isinstance(sub, ast.Attribute):
            candidate = MODEL_TO_TABLE.get(sub.attr)
        else:
            continue
        if candidate in AUDITED_TABLES:
            found.add(candidate)
    return found


def _audited_tables_in_sql(node: ast.AST) -> Set[str]:
    """Audited tables targeted by DML in any SQL string inside `node`."""
    found: Set[str] = set()
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Constant) or not isinstance(sub.value, str):
            continue
        for target in RAW_DML_RE.findall(sub.value):
            for table in AUDITED_TABLES:
                if target.lower() == table.lower():
                    found.add(table)
    return found


def _query_target_tables(node: ast.AST) -> Set[str]:
    """Tables named by a ``.query(X)`` call anywhere in this attribute chain."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "query":
            tables: Set[str] = set()
            for arg in sub.args:
                tables |= _named_audited_tables(arg)
            return tables
    return set()


def _scan(path: pathlib.Path) -> List[str]:
    """Return "<relpath>:<line> <what>" for each audit bypass in this file."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    rel = path.relative_to(BACKEND_ROOT).as_posix()
    offenders: List[str] = []

    def report(line: int, table_or_symbol: str, what: str) -> None:
        if ALLOWED_BYPASSES.get(f"{rel}:{table_or_symbol}"):
            return
        offenders.append(f"{rel}:{line} {what}")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        # (4) raw SQL DML naming an audited table, inside a call that executes
        # SQL (text(...) / execute(...) / exec_driver_sql(...)).
        callee = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        if callee in SQL_EXECUTING_CALLS:
            for table in sorted(_audited_tables_in_sql(node)):
                report(node.lineno, table, f"raw SQL DML on audited table {table}")

        if not isinstance(node.func, ast.Attribute):
            continue

        method = node.func.attr

        # (1) bulk_* — table-agnostic, banned outright.
        if method in BULK_METHODS:
            report(node.lineno, method, f"{method}() bypasses the mapper events for every table it writes")
            continue

        # (2) query(Model).delete() / .update({...})
        if method in {"delete", "update"}:
            for table in sorted(_query_target_tables(node.func.value)):
                report(node.lineno, table, f"query-level .{method}() on audited table {table}")
            continue

        # (3) session.execute(insert/update/delete(...)) — Core DML. Walks into
        # the argument rather than only inspecting its outermost call, so a
        # chained `delete(Model).where(...)` (whose outer call is `.where`) is
        # still caught -- the shape real 2.0-style code actually takes.
        if method == "execute":
            for arg in node.args:
                for sub in ast.walk(arg):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id in CORE_DML_FUNCS:
                        for table in sorted(_named_audited_tables(sub)):
                            report(node.lineno, table, f"Core {sub.func.id}() on audited table {table}")

    return offenders


def test_no_application_code_writes_an_audited_table_outside_the_orm():
    """The whole trail rests on every write to these 14 tables going through
    the ORM unit of work. One bulk/Core/raw write is a permanent, invisible
    hole in it -- the row changes and no AUDIT_ENTRY row is ever created.
    """
    offenders: List[str] = []
    for path in _app_python_files():
        offenders.extend(_scan(path))

    assert offenders == [], (
        "These write an audited table without going through the ORM, so the audit "
        "mapper events never fire and the change is recorded nowhere:\n  "
        + "\n  ".join(offenders)
        + "\nUse ORM session.add()/session.delete() instead, or -- if the bypass is "
        "genuinely correct -- add it to ALLOWED_BYPASSES in this file with a reason."
    )


def test_the_known_seeder_bypass_is_still_allow_listed_and_still_real():
    """The one exception must stay honest.

    backend/scripts/seed_defect_types.py really does ``DELETE FROM
    DEFECT_TYPE_CATALOG`` on a raw connection. Pretending it doesn't exist
    would make the guard above a lie, so it is allow-listed explicitly -- and
    this test asserts the allow-list entry still corresponds to real code, so
    a stale exemption cannot quietly widen the hole after the code is fixed
    or removed.
    """
    seeder = BACKEND_ROOT / "scripts" / "seed_defect_types.py"
    assert seeder.exists(), "allow-listed file is gone; drop its ALLOWED_BYPASSES entry"
    assert "DELETE FROM DEFECT_TYPE_CATALOG" in seeder.read_text(encoding="utf-8"), (
        "backend/scripts/seed_defect_types.py no longer contains the raw DELETE this "
        "allow-list entry exists for. Remove the ALLOWED_BYPASSES entry so the guard "
        "goes back to blocking it."
    )
    key = "scripts/seed_defect_types.py:DEFECT_TYPE_CATALOG"
    assert key in ALLOWED_BYPASSES
    assert len(ALLOWED_BYPASSES[key]) > 60, "an exemption needs a real reason, not a placeholder"


@pytest.mark.parametrize(
    "snippet,expect_offense",
    [
        # The bypasses this guard exists to catch.
        ("db.query(WorkOrder).filter(WorkOrder.client_id == c).delete()", True),
        ("db.query(HoldEntry).update({'hold_status': 'RELEASED'})", True),
        ("db.bulk_save_objects(rows)", True),
        ("db.bulk_insert_mappings(User, rows)", True),
        ("db.execute(delete(UserClientAssignment).where(x))", True),
        ("db.execute(text('DELETE FROM WORK_ORDER WHERE client_id = :c'))", True),
        # The captured path, and unaudited tables, must NOT be flagged.
        ("db.delete(work_order)", False),
        ("db.query(ProductionEntry).delete()", False),
        ("db.execute(text('DELETE FROM PRODUCTION_ENTRY'))", False),
        ("db.execute(select(WorkOrder))", False),
        ("db.query(WorkOrder).filter(WorkOrder.client_id == c).all()", False),
    ],
)
def test_guard_detects_bypasses_and_not_the_legitimate_orm_path(snippet, expect_offense, tmp_path):
    """Self-test: proves the guard above is not vacuously green.

    Without this, a scanner that silently matched nothing (a typo'd method
    name, a wrong AST field) would report zero offenders forever and read as
    a passing gate.
    """
    probe = BACKEND_ROOT / "___guard_selftest_probe.py"
    probe.write_text(snippet + "\n", encoding="utf-8")
    try:
        offenders = _scan(probe)
    finally:
        probe.unlink()
    assert bool(offenders) is expect_offense, f"{snippet!r} -> {offenders}"
