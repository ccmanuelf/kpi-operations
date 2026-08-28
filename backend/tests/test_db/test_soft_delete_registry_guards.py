"""Structural guards over the soft-delete registry.

An allow-list drifts: a new soft-deletable model gets added, nobody classifies
it, and it silently defaults to unfiltered. That is exactly how the nineteen
pre-existing ``is_active`` tables ended up mostly unfiltered, and how seven
DELETE endpoints spent months answering 404 for every valid id while looking
like a testing limitation.

So each declaration in ``backend/db/soft_delete_registry.py`` is gated from
both sides, with the side that nobody has to remember being structural:

* every table with an ``is_active`` column must be classified (auto-filtered or
  ad-hoc), read straight off ``Base.metadata``;
* every CRUD module that imports ``soft_delete`` must be declared, read
  straight off the filesystem;
* every table recorded as *broken* must still be broken, so the fix fires the
  gate instead of leaving a stale entry behind.
"""

import ast
import pathlib
import re
import subprocess
import sys

import pytest

from backend.database import Base
from backend.db.soft_delete_registry import (
    AD_HOC_FILTERED_TABLES,
    AUTO_FILTERED_TABLES,
    SOFT_DELETE_CRUD_TARGETS,
    SOFT_DELETE_WITHOUT_COLUMN,
    SOFT_DELETE_WITHOUT_COLUMN_CAP,
)
from backend.orm import register_all_models

register_all_models()

BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
RAW_SQL_MARKER = "# raw-sql-guard: allow"


def _tables_with_is_active() -> set:
    return {name for name, table in Base.metadata.tables.items() if "is_active" in table.c}


def _model_for(table: str):
    for mapper in Base.registry.mappers:
        if mapper.class_.__tablename__ == table:
            return mapper.class_
    return None


# ---------------------------------------------------------------------------
# Reverse side: every soft-deletable table is classified, exactly once.
# ---------------------------------------------------------------------------


def test_every_soft_deletable_table_is_classified():
    """No third state. A new is_active column must be classified or CI fails."""
    classified = set(AUTO_FILTERED_TABLES) | set(AD_HOC_FILTERED_TABLES)
    unclassified = sorted(_tables_with_is_active() - classified)
    assert unclassified == [], (
        "These tables have an is_active column but are neither auto-filtered nor "
        "recorded as ad-hoc-filtered. Add each to AUTO_FILTERED_TABLES (and to "
        "the migration + the forward-side suite), or to AD_HOC_FILTERED_TABLES "
        "with a reason: " + ", ".join(unclassified)
    )


def test_no_table_is_both_auto_filtered_and_ad_hoc():
    overlap = sorted(set(AUTO_FILTERED_TABLES) & set(AD_HOC_FILTERED_TABLES))
    assert overlap == [], f"Tables declared in both sets: {overlap}"


def test_registry_names_only_tables_that_are_actually_soft_deletable():
    """A renamed table, or one whose is_active column was dropped, must not linger."""
    stale = sorted((set(AUTO_FILTERED_TABLES) | set(AD_HOC_FILTERED_TABLES)) - _tables_with_is_active())
    assert stale == [], f"Registry names tables with no is_active column: {stale}"


def test_every_ad_hoc_entry_states_a_reason():
    thin = sorted(t for t, reason in AD_HOC_FILTERED_TABLES.items() if len(reason.strip()) < 15)
    assert thin == [], f"Ad-hoc entries need a real reason, not a placeholder: {thin}"


def test_auto_filtered_declaration_matches_the_migration():
    """The column and the filter must cover the same tables, or one is a lie."""
    spec = pathlib.Path(BACKEND_ROOT / "alembic/versions/0007_transaction_soft_delete.py")
    module = ast.parse(spec.read_text())
    tables = None
    for node in module.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "TABLES":
            tables = {ast.literal_eval(e) for e in node.value.elts}
    assert tables is not None, "migration 0007 no longer declares a TABLES tuple"
    assert tables == set(AUTO_FILTERED_TABLES)


# ---------------------------------------------------------------------------
# Structural side: every soft_delete() caller is declared, and every target
# either has the column or is recorded as broken.
# ---------------------------------------------------------------------------


def _crud_modules_importing_soft_delete() -> set:
    found = set()
    for path in sorted((BACKEND_ROOT / "crud").rglob("*.py")):
        if "from backend.utils.soft_delete import" in path.read_text():
            found.add(str(path.relative_to(BACKEND_ROOT)))
    return found


def test_every_crud_module_that_soft_deletes_is_declared():
    """Read off the filesystem, so wiring soft_delete into a new module fails
    the gate until someone writes down which table it deletes from."""
    on_disk = _crud_modules_importing_soft_delete()
    undeclared = sorted(on_disk - set(SOFT_DELETE_CRUD_TARGETS))
    assert undeclared == [], (
        "These CRUD modules call soft_delete() but are not in "
        "SOFT_DELETE_CRUD_TARGETS, so nothing checks that their model can "
        "actually be soft-deleted: " + ", ".join(undeclared)
    )


def test_no_declared_crud_module_has_stopped_soft_deleting():
    on_disk = _crud_modules_importing_soft_delete()
    stale = sorted(set(SOFT_DELETE_CRUD_TARGETS) - on_disk)
    assert stale == [], f"SOFT_DELETE_CRUD_TARGETS names modules that no longer soft-delete: {stale}"


@pytest.mark.parametrize("module,table", sorted(SOFT_DELETE_CRUD_TARGETS.items()))
def test_every_soft_delete_target_is_either_working_or_recorded_broken(module, table):
    """The S1 defect in one assertion: soft_delete() against a model with no
    is_active column returns False and the route answers 404 for every id."""
    model = _model_for(table)
    assert model is not None, f"{module} declares table {table}, which maps to nothing"
    if table in SOFT_DELETE_WITHOUT_COLUMN:
        pytest.skip(f"{table} is recorded broken; covered by the reverse-side test")
    assert hasattr(model, "is_active"), (
        f"{module} soft-deletes {table}, which has no is_active column: its DELETE "
        f"endpoint answers 404 for every id. Add the column, or record it in "
        f"SOFT_DELETE_WITHOUT_COLUMN and raise the cap deliberately."
    )


@pytest.mark.parametrize("table", sorted(SOFT_DELETE_WITHOUT_COLUMN))
def test_every_table_recorded_broken_is_still_broken(table):
    """The signal that has been missing: when one gets fixed, say so.

    A stale entry here means a DELETE endpoint quietly started working and the
    registry still claims it is broken — the same silent drift in reverse.
    """
    model = _model_for(table)
    assert model is not None, f"SOFT_DELETE_WITHOUT_COLUMN names {table}, which maps to nothing"
    assert not hasattr(model, "is_active"), (
        f"{table} now has an is_active column, so its DELETE endpoint may already "
        f"work. Remove it from SOFT_DELETE_WITHOUT_COLUMN, lower the cap, and add "
        f"it to AUTO_FILTERED_TABLES or AD_HOC_FILTERED_TABLES."
    )


def test_every_broken_target_is_declared():
    """Forward side of the ratchet: no undeclared broken soft-delete target."""
    broken = sorted(
        table
        for table in set(SOFT_DELETE_CRUD_TARGETS.values())
        if (model := _model_for(table)) is not None and not hasattr(model, "is_active")
    )
    assert broken == sorted(SOFT_DELETE_WITHOUT_COLUMN)


def test_broken_soft_delete_ratchet_has_no_slack():
    """The cap equals reality, so it cannot sit above it and absorb a new one."""
    assert len(SOFT_DELETE_WITHOUT_COLUMN) == SOFT_DELETE_WITHOUT_COLUMN_CAP


def test_every_broken_entry_names_the_endpoint_it_breaks():
    thin = sorted(t for t, note in SOFT_DELETE_WITHOUT_COLUMN.items() if "/api/" not in note)
    assert thin == [], f"Each broken entry must name the endpoint it breaks: {thin}"


# ---------------------------------------------------------------------------
# The one read shape the ORM filter cannot reach.
# ---------------------------------------------------------------------------


def _sql_string_literals(path: pathlib.Path):
    """Non-docstring string constants that look like a SELECT statement."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:  # pragma: no cover - defensive
        return
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            lowered = node.value.lower()
            if "select" in lowered and "from" in lowered:
                yield node


def test_no_raw_sql_reads_an_auto_filtered_table():
    """``with_loader_criteria`` cannot reach ``text()`` SQL — it never passes
    through the ORM. A raw SELECT against one of the seven would return
    soft-deleted rows straight into a KPI, so it is banned outright.

    Line-level exemption: ``# raw-sql-guard: allow`` on the offending line.
    """
    # _sql_string_literals has already narrowed to SELECT statements, so a bare
    # mention of the table name is enough — and keeps the SQL keyword out of the
    # pattern, which bandit's B608 heuristic would otherwise flag.
    pattern = re.compile(r"\b(" + "|".join(sorted(AUTO_FILTERED_TABLES)) + r")\b", re.IGNORECASE)
    offenders = []
    for path in sorted(BACKEND_ROOT.rglob("*.py")):
        rel = path.relative_to(BACKEND_ROOT)
        if rel.parts[0] in {".venv", "alembic", "tests", "htmlcov"}:
            continue
        lines = path.read_text().splitlines()
        for node in _sql_string_literals(path):
            match = pattern.search(node.value)
            if not match:
                continue
            line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
            if RAW_SQL_MARKER in line:
                continue
            offenders.append(f"{rel}:{node.lineno} raw SELECT over {match.group(1)}")
    assert (
        offenders == []
    ), "Raw SQL bypasses the automatic soft-delete filter, so these reads would " "return deleted rows: " + "; ".join(
        offenders
    )


# ---------------------------------------------------------------------------
# The filter cannot be bypassed by not importing it.
# ---------------------------------------------------------------------------


def test_importing_any_single_orm_model_installs_the_filter():
    """Installed from backend/orm/__init__.py, which Python runs before any
    ``backend.orm.<model>`` submodule — so a query cannot reach a model with
    the filter still uninstalled. Checked in a clean interpreter."""
    probe = (
        "from sqlalchemy import event\n"
        "from sqlalchemy.orm import Session\n"
        "import backend.orm.work_order\n"
        "from backend.db.soft_delete_filter import apply_active_row_filter, auto_filtered_models\n"
        "assert event.contains(Session, 'do_orm_execute', apply_active_row_filter)\n"
        "print(sorted(m.__tablename__ for m in auto_filtered_models()))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=str(BACKEND_ROOT.parent),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == str(sorted(AUTO_FILTERED_TABLES))
