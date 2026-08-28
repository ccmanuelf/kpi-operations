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
    AUTO_FILTERED_WITHOUT_DELETE_ENDPOINT,
    CASCADE_KINDS,
    CHILD_CLASSIFICATION,
    ChildKind,
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


#: The two ways a CRUD module can soft-delete. The service is the one that
#: blocks, hides AND attributes; the bare helper only hides.
_SERVICE_IMPORT = "from backend.db.soft_delete_service import"
_BARE_IMPORT = "from backend.utils.soft_delete import"


def _crud_modules_importing_soft_delete() -> set:
    found = set()
    for path in sorted((BACKEND_ROOT / "crud").rglob("*.py")):
        text = path.read_text()
        if _SERVICE_IMPORT in text or _BARE_IMPORT in text:
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


def test_no_table_recorded_broken_has_quietly_started_working():
    """The signal that has been missing: when one gets fixed, say so.

    A stale entry here means a DELETE endpoint quietly started working and the
    registry still claims it is broken — the same silent drift in reverse. This
    is how the original four left the list: fixing them flipped this guard,
    which is what forced the registry, the migration and the cap to be updated
    together instead of one of them being forgotten.

    Not parametrized: the dict is empty now, and an empty parametrize silently
    reports a skip rather than a pass, which is a vacuous guard.
    """
    resurrected = sorted(
        table
        for table in SOFT_DELETE_WITHOUT_COLUMN
        if (model := _model_for(table)) is not None and hasattr(model, "is_active")
    )
    assert resurrected == [], (
        "These now have an is_active column, so their DELETE endpoints may already "
        "work. Remove each from SOFT_DELETE_WITHOUT_COLUMN, lower the cap, and add "
        "it to AUTO_FILTERED_TABLES or AD_HOC_FILTERED_TABLES: " + ", ".join(resurrected)
    )


def test_every_table_recorded_broken_maps_to_a_real_model():
    unmapped = sorted(t for t in SOFT_DELETE_WITHOUT_COLUMN if _model_for(t) is None)
    assert unmapped == [], f"SOFT_DELETE_WITHOUT_COLUMN names tables that map to nothing: {unmapped}"


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


# ---------------------------------------------------------------------------
# Auto-filtered deletes must go through the one entry point that blocks,
# hides and attributes — not the bare helper, which only hides.
# ---------------------------------------------------------------------------

AUTO_FILTERED_CRUD_MODULES = sorted(
    module for module, table in SOFT_DELETE_CRUD_TARGETS.items() if table in AUTO_FILTERED_TABLES
)


def test_every_auto_filtered_table_has_a_crud_module_or_a_declared_reason_not_to():
    """Anti-vacuity for the two guards below, and the reverse side of the
    exemption: ALERT is soft-deletable only so a cascade can hide it, and that
    has to be stated rather than inferred from the absence of a module."""
    tabled = set(SOFT_DELETE_CRUD_TARGETS.values()) & set(AUTO_FILTERED_TABLES)
    exempt = set(AUTO_FILTERED_WITHOUT_DELETE_ENDPOINT)
    assert tabled | exempt == set(AUTO_FILTERED_TABLES)
    assert tabled & exempt == set()
    assert len(AUTO_FILTERED_CRUD_MODULES) == 11


def test_every_delete_endpoint_exemption_states_a_reason():
    thin = sorted(t for t, why in AUTO_FILTERED_WITHOUT_DELETE_ENDPOINT.items() if len(why.strip()) < 40)
    assert thin == [], f"Exemptions need a real reason: {thin}"


@pytest.mark.parametrize("module", AUTO_FILTERED_CRUD_MODULES)
def test_every_auto_filtered_delete_goes_through_the_service(module):
    """soft_delete_record blocks on visible children and records who/when.

    Reaching for backend.utils.soft_delete directly skips both, which is a
    delete that neither refuses nor attributes — read off the filesystem so
    it cannot be forgotten rather than declared.
    """
    text = (BACKEND_ROOT / module).read_text()
    assert _SERVICE_IMPORT in text, (
        f"{module} soft-deletes an auto-filtered table but does not import "
        f"soft_delete_record from backend.db.soft_delete_service"
    )


@pytest.mark.parametrize("module", AUTO_FILTERED_CRUD_MODULES)
def test_no_auto_filtered_crud_module_still_reaches_the_bare_helper(module):
    """The reverse: importing both would let a later edit quietly bypass the
    service while this file's forward guard stayed green."""
    text = (BACKEND_ROOT / module).read_text()
    assert _BARE_IMPORT not in text, (
        f"{module} still imports the bare soft_delete helper; an auto-filtered "
        f"delete must go through soft_delete_record only"
    )


# ---------------------------------------------------------------------------
# The three-way child classification: encoded where it can be, declared with a
# reason where it cannot, and gated either way.
# ---------------------------------------------------------------------------


def _fks_into_auto_filtered(child_table: str):
    """(fk column, parent table) for every FK this child has into the set."""
    table = Base.metadata.tables.get(child_table)
    if table is None:
        return []
    return sorted(
        (fk.parent.name, fk.column.table.name)
        for fk in table.foreign_keys
        if fk.column.table.name in AUTO_FILTERED_TABLES
    )


def test_every_classified_child_really_is_a_child_of_an_auto_filtered_table():
    """A stale entry would silently exempt nothing, or worse, exempt a rename."""
    orphans = sorted(t for t in CHILD_CLASSIFICATION if not _fks_into_auto_filtered(t))
    assert orphans == [], f"CHILD_CLASSIFICATION names tables with no FK into an auto-filtered table: {orphans}"


def test_every_classified_child_has_exactly_one_auto_filtered_parent():
    """The classification is keyed by child table, which is only unambiguous
    while each classified child has one such parent. A second one is a real
    decision (owned by which?) and must not be silently inherited."""
    ambiguous = sorted(t for t in CHILD_CLASSIFICATION if len(_fks_into_auto_filtered(t)) != 1)
    assert ambiguous == [], (
        "These have more than one auto-filtered parent, so a table-level kind is "
        "ambiguous; classify per parent instead: " + ", ".join(ambiguous)
    )


@pytest.mark.parametrize("child", sorted(t for t, (kind, _) in CHILD_CLASSIFICATION.items() if kind is ChildKind.OWNED))
def test_every_owned_child_cannot_exist_without_its_parent(child):
    """The encodable half of "owned": a NOT NULL FK. Mislabelling a nullable
    child as owned would cascade-hide rows that can outlive their parent."""
    fk_column, parent_table = _fks_into_auto_filtered(child)[0]
    column = Base.metadata.tables[child].c[fk_column]
    assert column.nullable is False, (
        f"{child}.{fk_column} is nullable, so a {child} row CAN exist without its "
        f"{parent_table}; it is not owned composition and must not be cascaded"
    )


@pytest.mark.parametrize(
    "child", sorted(t for t, (kind, _) in CHILD_CLASSIFICATION.items() if kind is ChildKind.DERIVED)
)
def test_every_derived_child_is_optional_and_regenerable_and_hideable(child):
    """DERIVED needs all three: the child already exists without a parent (its
    FK is nullable), it can be regenerated, and it CAN be hidden — a derived
    child that cannot be hidden would be left dangling, which is the exact
    thing cascading it is supposed to prevent."""
    fk_column, _parent_table = _fks_into_auto_filtered(child)[0]
    assert Base.metadata.tables[child].c[fk_column].nullable is True
    assert "/api/" in CHILD_CLASSIFICATION[child][1], "a derived child must name how it is regenerated"
    assert child in AUTO_FILTERED_TABLES, f"{child} is cascaded but has no way to be hidden"


def test_every_classification_states_a_reason():
    thin = sorted(t for t, (_, why) in CHILD_CLASSIFICATION.items() if len(why.strip()) < 40)
    assert thin == [], f"Classifications need a real reason, not a placeholder: {thin}"


def test_independent_is_the_default_for_anything_unclassified():
    """The safe default: refuse rather than remove. Checked against a table that
    really is a child and really is unlisted, so it cannot pass vacuously."""
    from backend.db.soft_delete_cascade import kind_of

    assert "PRODUCTION_ENTRY" not in CHILD_CLASSIFICATION
    assert _fks_into_auto_filtered("PRODUCTION_ENTRY") != []
    assert kind_of("PRODUCTION_ENTRY") is ChildKind.INDEPENDENT
    assert kind_of("A_TABLE_THAT_DOES_NOT_EXIST") is ChildKind.INDEPENDENT


def test_cascade_and_blocking_sets_partition_every_dependent():
    """No child is both cascaded and blocking, and none is neither."""
    from backend.db.soft_delete_cascade import blocking_dependents, cascade_dependents

    for parent in sorted(AUTO_FILTERED_TABLES):
        blocking = {d[0] for d in blocking_dependents(parent)}
        cascading = {d[0] for d in cascade_dependents(parent)}
        assert blocking & cascading == set(), f"{parent}: {blocking & cascading} classified as both"
        every = {t.name for t in Base.metadata.sorted_tables for fk in t.foreign_keys if fk.column.table.name == parent}
        assert blocking | cascading == every, f"{parent}: unclassified dependents {every - blocking - cascading}"


def test_the_cascade_kinds_are_exactly_owned_and_derived():
    assert CASCADE_KINDS == frozenset({ChildKind.OWNED, ChildKind.DERIVED})
