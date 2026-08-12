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
    """Pinned to the spec's 14 tables so scope changes are deliberate."""
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
            "USER_CLIENT_ASSIGNMENT",
            "DEFECT_TYPE_CATALOG",
            "ALERT_CONFIG",
        }
    )


def test_no_audited_table_exposes_an_unredacted_secret():
    """Redaction completeness: a FUTURE sensitive column must fail CI.

    Checks BOTH `column.name` (the DB column) and `column.key` (the mapped
    attribute). They are identical for all 14 audited tables today, but
    capture.py's `_mask` keys off `column.key` while this guard originally
    keyed off `column.name` alone: a future
    `mapped_column("password_hash")` bound to an attribute named something
    else -- or the reverse -- would let the guard pass while the mask misses,
    writing the secret into AUDIT_ENTRY.changes. Requiring both names to be
    listed closes that gap in whichever direction the alias points.
    """
    leaks = []
    for table_name in AUDITED_TABLES:
        table = Base.metadata.tables.get(table_name)
        if table is None:
            continue
        for column in table.columns:
            for identifier in {column.name, column.key}:
                lowered = identifier.lower()
                if any(p in lowered for p in SENSITIVE_PATTERN) and identifier not in REDACTED_FIELDS:
                    leaks.append(f"{table_name}.{identifier}")
    assert sorted(set(leaks)) == [], (
        "These columns look sensitive but are not in REDACTED_FIELDS, so their "
        "values would be written into AUDIT_ENTRY.changes: " + ", ".join(sorted(set(leaks)))
    )


def test_redaction_covers_both_column_name_and_attribute_key():
    """`_mask` masks on `column.key`; REDACTED_FIELDS must therefore list the
    attribute key of every redacted column, not only its DB column name.

    Non-vacuous check: it resolves each redacted field back to a real audited
    column and asserts the *key* is what is listed. If someone renames the
    attribute (`password_hash: Mapped[str] = mapped_column("password_hash")`
    under a different Python name) and updates only the DB-name side of the
    registry, this fails.
    """
    from backend.audit.capture import _mask

    for field in REDACTED_FIELDS:
        owners = [
            t
            for t in AUDITED_TABLES
            if (table := Base.metadata.tables.get(t)) is not None and any(c.key == field for c in table.columns)
        ]
        assert owners, f"REDACTED_FIELDS names {field!r}, which is not the attribute key of any audited column"
        assert _mask(field, "super-secret-value") == "[redacted]"


def test_every_audited_table_has_a_single_column_pk():
    """`capture._require_pk` takes `identity[0]` -- the single-column-PK
    assumption the whole `record_pk` design rests on (spec section 4).

    A composite PK added to an audited table would silently record only its
    first component, aliasing every row that shares that component into one
    apparent entity history. This turns that into a CI failure instead.
    """
    composite = []
    for table_name in sorted(AUDITED_TABLES):
        table = Base.metadata.tables.get(table_name)
        if table is None:
            continue
        pk_columns = list(table.primary_key.columns)
        if len(pk_columns) != 1:
            composite.append(f"{table_name} ({', '.join(c.name for c in pk_columns)})")
    assert composite == [], (
        "AUDIT_ENTRY.record_pk stores ONE stringified PK value "
        "(backend/audit/capture.py::_require_pk takes identity[0]). These audited "
        "tables no longer have a single-column PK, so every row sharing the first "
        "component would collapse into one entity history: " + "; ".join(composite)
    )


def test_is_audited_reflects_the_allow_list():
    assert is_audited("HOLD_ENTRY") is True
    assert is_audited("METRIC_CALCULATION_RESULT") is False
    assert is_audited("NOT_A_TABLE") is False
