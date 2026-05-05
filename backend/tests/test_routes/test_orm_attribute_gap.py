"""
Static gap scanner — fails the test suite if backend code references
ORM column / relationship names that don't exist on the actual model.

Backs Run-6 finding R6-B-001 (D2-class schema-drift bug). The previous
defense-in-depth was the runtime smoke test (`test_smoke_paramless_get`)
that catches drift in routes the user can hit. This static scanner
catches drift in code paths that may never be hit by an automated test
(background tasks, helpers, schedulers).

Together they form:
    - smoke test: catches drift on the request path
    - static scan (this): catches drift in helpers/tasks/scripts

Cost: ~3-4s per run. Runs in CI on every PR.

To extend: add the ORM class to `_TRACKED_ORMS` below. The scanner
already excludes `.venv/` / `__pycache__` / tests / 3rd-party noise.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Set, Tuple

import pytest
from sqlalchemy import inspect

from backend.orm.production_entry import ProductionEntry
from backend.orm.quality_entry import QualityEntry
from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.work_order import WorkOrder
from backend.orm.user import User
from backend.orm.job import Job
from backend.schemas.alert import Alert, AlertConfig, AlertHistory


_TRACKED_ORMS = {
    "ProductionEntry": ProductionEntry,
    "QualityEntry": QualityEntry,
    "DowntimeEntry": DowntimeEntry,
    "AttendanceEntry": AttendanceEntry,
    "WorkOrder": WorkOrder,
    "User": User,
    "Job": Job,
    "Alert": Alert,
    "AlertConfig": AlertConfig,
    "AlertHistory": AlertHistory,
}

# SQLAlchemy session/query API surface — these are method names that
# legitimately appear as `Class.method` (e.g. `User.query.filter(...)`).
# Excluding them avoids false positives.
_SQL_KEYWORDS = {
    "query",
    "metadata",
    "registry",
    "table",
    "c",
    "update",
    "insert",
    "delete",
    "where",
    "order_by",
    "filter",
    "filter_by",
    "limit",
    "offset",
    "select",
    "options",
    "group_by",
    "having",
    "distinct",
    "join",
    "outerjoin",
    "from_self",
    "first",
    "one",
    "one_or_none",
    "all",
    "count",
    "exists",
    "scalar",
    "scalars",
    "add",
    "add_all",
    "flush",
    "commit",
    "rollback",
    "close",
    "expire",
    "refresh",
    "merge",
    "expunge",
    "expunge_all",
    "no_autoflush",
    "autoflush",
    "with_polymorphic",
    "with_entities",
    "load_only",
    "contains_eager",
    "joinedload",
    "selectinload",
    "subqueryload",
    "lazyload",
    "noload",
    "raiseload",
    "defer",
    "undefer",
}

# Project root — anchor for the scan path.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_BACKEND_ROOT = os.path.join(_PROJECT_ROOT, "backend")

# Subdirectories to skip when walking source files.
_SKIP_DIRS = {"__pycache__", ".venv", "venv", ".mypy_cache", "node_modules", "tests"}


def _build_known_attrs() -> Dict[str, Set[str]]:
    """For each tracked ORM, build the set of columns + relationship names.

    The scanner accepts ANY of these as legitimate attribute access. A
    reference to anything not in this set is flagged.
    """
    out: Dict[str, Set[str]] = {}
    for name, cls in _TRACKED_ORMS.items():
        cols = {c.name for c in cls.__table__.columns}
        rels = {r.key for r in inspect(cls).relationships}
        out[name] = cols | rels
    return out


def _scan_one_file(path: str, known: Dict[str, Set[str]]) -> List[Tuple[int, str, str]]:
    """Return a list of (line_no, class_name, attribute) for any reference
    that doesn't match the ORM's known attributes."""
    try:
        with open(path, encoding="utf-8") as f:
            txt = f.read()
    except (OSError, UnicodeDecodeError):
        return []

    findings: List[Tuple[int, str, str]] = []
    for cls_name, attrs in known.items():
        # Match `ClassName.attribute` where attribute starts with a
        # lowercase letter (constants and helper methods often start
        # with uppercase or underscore).
        pattern = re.compile(rf"\b{cls_name}\.([a-z][a-z0-9_]+)\b")
        for m in pattern.finditer(txt):
            attr = m.group(1)
            if attr in _SQL_KEYWORDS:
                continue
            if attr in attrs:
                continue
            line_no = txt[: m.start()].count("\n") + 1
            findings.append((line_no, cls_name, attr))
    return findings


def test_no_orm_attribute_drift() -> None:
    """
    Walk all `.py` files under backend/ (excluding tests + caches) and
    assert that every `ORMClass.attribute` reference targets an
    attribute that actually exists on the model.

    The bug this prevents (Run-6 finding R6-B-001):
    `daily_reports.py:149 → User.client_id` — column doesn't exist
    (it's `client_id_assigned`). The query silently returned [] because
    SQLAlchemy resolved `User.client_id` lazily and the broken filter
    just matched nothing.
    """
    known = _build_known_attrs()
    all_findings: List[str] = []

    for root, dirs, files in os.walk(_BACKEND_ROOT):
        # Prune skipped directories in-place so os.walk doesn't recurse.
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for fname in files:
            if not fname.endswith(".py"):
                continue
            path = os.path.join(root, fname)
            for line_no, cls, attr in _scan_one_file(path, known):
                rel = os.path.relpath(path, _PROJECT_ROOT)
                all_findings.append(f"{rel}:{line_no}  {cls}.{attr}")

    # Allowlist for false positives that the static scanner can't yet
    # disambiguate (e.g. dynamic attribute setting, `getattr(Cls, name)`
    # patterns). Add entries here with a comment explaining why each
    # is safe — a future contributor should be able to read it and
    # verify rather than just trust it.
    allowed_substrings: Set[str] = set()  # currently empty; populate as needed

    real_findings = [f for f in all_findings if not any(skip in f for skip in allowed_substrings)]

    assert not real_findings, (
        f"{len(real_findings)} ORM attribute reference(s) point at columns "
        f"or relationships that don't exist on the model. Either fix the "
        f"reference or update the ORM:\n\n" + "\n".join(real_findings)
    )


def test_scanner_is_actually_scanning() -> None:
    """Sanity check: the scanner walks a non-trivial number of files.

    Guards against an environmental misconfiguration silently making
    the gap scanner pass with zero findings (which would defeat its
    regression-guard purpose).
    """
    file_count = 0
    for root, dirs, files in os.walk(_BACKEND_ROOT):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for fname in files:
            if fname.endswith(".py"):
                file_count += 1
    assert file_count >= 100, (
        f"Scanner only saw {file_count} .py files under backend/ — expected "
        ">=100. Path constants are likely wrong or the directory layout "
        "changed; the gap scanner will under-cover the codebase."
    )


@pytest.mark.parametrize(
    "code, should_fail",
    [
        # Real ORM column reference (passes)
        ("WorkOrder.work_order_id", False),
        ("ProductionEntry.shift_date", False),
        # Drift cases (the scanner should flag these)
        ("WorkOrder.nonexistent_column", True),
        ("User.client_id", True),  # actual is client_id_assigned
        # Method calls (excluded; legitimate)
        ("WorkOrder.query.filter", False),
    ],
)
def test_scanner_classifies_correctly(code: str, should_fail: bool, tmp_path) -> None:
    """Sanity: the regex classifier flags the right cases on a synthetic file."""
    test_file = tmp_path / "synth.py"
    test_file.write_text(f"x = {code}\n")
    findings = _scan_one_file(str(test_file), _build_known_attrs())
    if should_fail:
        assert findings, f"Expected scanner to flag drift on `{code}`"
    else:
        assert not findings, f"Scanner false-positive on `{code}`: {findings}"
