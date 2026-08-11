"""Structural guards over the audit registry.

These exist because an allow-list drifts: a new table gets added and nobody
classifies it, so it is silently unaudited. The guard turns that into a
failing build instead of a quiet gap.
"""

from backend.audit.registry import AUDITED_TABLES, EXCLUDED_TABLES, REDACTED_FIELDS, is_audited
from backend.database import Base

SENSITIVE_PATTERN = ("password", "token", "secret", "api_key", "hash")


def _all_orm_tables() -> set:
    return set(Base.metadata.tables.keys())


def test_every_orm_table_is_classified():
    """Every table is audited or excluded-with-a-reason. No third state."""
    classified = set(AUDITED_TABLES) | set(EXCLUDED_TABLES)
    unclassified = sorted(_all_orm_tables() - classified)
    assert unclassified == [], (
        "These ORM tables are neither audited nor excluded. Add each to "
        "AUDITED_TABLES, or to EXCLUDED_TABLES with a reason: " + ", ".join(unclassified)
    )


def test_no_table_is_both_audited_and_excluded():
    overlap = sorted(set(AUDITED_TABLES) & set(EXCLUDED_TABLES))
    assert overlap == [], f"Tables in both sets: {overlap}"


def test_registry_references_only_real_tables():
    """A renamed or dropped table must not linger in the registry."""
    real = _all_orm_tables()
    stale = sorted((set(AUDITED_TABLES) | set(EXCLUDED_TABLES)) - real)
    assert stale == [], f"Registry names tables that do not exist: {stale}"


def test_every_exclusion_states_a_reason():
    thin = sorted(t for t, reason in EXCLUDED_TABLES.items() if len(reason.strip()) < 15)
    assert thin == [], f"Exclusions need a real reason, not a placeholder: {thin}"


def test_audited_tables_matches_the_spec():
    """Pinned to the spec's 11 tables so scope changes are deliberate."""
    assert AUDITED_TABLES == frozenset(
        {
            "WORK_ORDER",
            "HOLD_ENTRY",
            "USER",
            "CLIENT",
            "CLIENT_CONFIG",
            "EMPLOYEE",
            "EMPLOYEE_CLIENT_ASSIGNMENT",
            "EMPLOYEE_LINE_ASSIGNMENT",
            "KPI_THRESHOLD",
            "HOLD_REASON_CATALOG",
            "HOLD_STATUS_CATALOG",
        }
    )


def test_no_audited_table_exposes_an_unredacted_secret():
    """Redaction completeness: a FUTURE sensitive column must fail CI."""
    leaks = []
    for table_name in AUDITED_TABLES:
        table = Base.metadata.tables.get(table_name)
        if table is None:
            continue
        for column in table.columns:
            lowered = column.name.lower()
            if any(p in lowered for p in SENSITIVE_PATTERN) and column.name not in REDACTED_FIELDS:
                leaks.append(f"{table_name}.{column.name}")
    assert sorted(leaks) == [], (
        "These columns look sensitive but are not in REDACTED_FIELDS, so their "
        "values would be written into AUDIT_ENTRY.changes: " + ", ".join(sorted(leaks))
    )


def test_is_audited_reflects_the_allow_list():
    assert is_audited("HOLD_ENTRY") is True
    assert is_audited("METRIC_CALCULATION_RESULT") is False
    assert is_audited("NOT_A_TABLE") is False
