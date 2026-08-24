"""Structural guards over derived table sets: the client-scope FK derivation,
the reset-sweep completeness guard, and the bare-column / nullable-tenant /
cascade-children pins.

Split out of test_cli.py: test_cli.py keeps the CLI surface and contract
tests; test_cli_reset.py covers what --reset deletes and preserves.
"""

import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table

from backend.database import Base
from backend.seed.cli import (
    CLIENT_SCOPED_TABLES,
    DEPENDENT_SWEEPS,
    AmbiguousClientScope,
    _derive_client_scoped_tables,
)


def _foreign_keys_into(scoped: set, swept: set) -> list:
    """Every (table.column -> parent) FK held by a table OUTSIDE `swept` that
    points at a table INSIDE `scoped`. Each one is a row --reset would orphan
    or be RESTRICTed by."""
    offenders = []
    for table in Base.metadata.sorted_tables:
        if table.name in swept:
            continue
        for column in table.columns:
            for fk in column.foreign_keys:
                if fk.column.table.name in scoped:
                    offenders.append(f"{table.name}.{column.name} -> {fk.column.table.name}")
    return sorted(offenders)


def test_no_table_outside_the_reset_sweep_holds_a_foreign_key_into_it():
    """The anti-rot guard, and the reason C-2 cannot come back.

    A table added later with a ForeignKey to CLIENT is picked up by
    _derive_client_scoped_tables automatically. A GRANDCHILD -- a table whose
    only link is an FK into a client-scoped table, the ALERT_HISTORY shape --
    is not derivable and must be declared in DEPENDENT_SWEEPS. This asserts
    the declaration is complete against live metadata, so the next one fails
    the build instead of failing --reset on a customer's VM.

    TARGETS ARE `swept`, NOT `scoped`, and the difference is the whole guard.
    The first version skipped tables in `swept` as SOURCES but only counted
    tables in `scoped` as TARGETS, and the three DEPENDENT_SWEEPS children are
    in `swept` and not in `scoped` -- so a future table holding an FK into
    ALERT_HISTORY / ASSUMPTION_CHANGE / ATTENDANCE_HOUR_ALLOCATION was
    invisible to it, while its docstring claimed "no table outside the sweep
    holds a ForeignKey into it". Since _reset deletes those three parents by
    subquery, such a table would RESTRICT --reset on a customer's VM: C-2 back
    through a side door. Injecting a synthetic table with an FK into
    ALERT_HISTORY passed the old form and is named by this one, and the
    stricter form costs nothing against the live schema today.
    """
    scoped = set(CLIENT_SCOPED_TABLES)
    swept = scoped | {child for child, _, _, _ in DEPENDENT_SWEEPS}

    assert _foreign_keys_into(swept, swept) == []


def test_the_reset_sweep_completeness_guard_is_not_vacuous():
    """A guard that cannot fail proves nothing. Withdraw ALERT_HISTORY from
    the swept set and the scan must name exactly the FK that C-2's fourth
    repro case exercises. Target set matches the guard above (`swept`), so the
    two cannot drift into asserting different things."""
    scoped = set(CLIENT_SCOPED_TABLES)
    swept = scoped | {child for child, _, _, _ in DEPENDENT_SWEEPS}

    assert _foreign_keys_into(swept, swept - {"ALERT_HISTORY"}) == ["ALERT_HISTORY.alert_id -> ALERT"]


#: The three column names this schema uses to scope a row to a tenant. Salvaged
#: from seed_sample_client.py (removed in S1c), which was the only place all
#: three were ever written down together.
CLIENT_SCOPE_COLUMN_NAMES = {"client_id", "client_id_fk", "client_id_assigned"}

#: Tenant-NAMED string columns that scope nothing -- CLIENT's own descriptive
#: fields. Pinned so the derivation below can assert on a closed set without
#: having to guess which side of the line a new `client_*` column falls on.
CLIENT_DESCRIPTIVE_COLUMN_NAMES = {"client_contact", "client_email", "client_name", "client_phone", "client_type"}


def _tenant_named_string_columns() -> set:
    """Every string column in the schema whose name mentions a tenant.

    The CANDIDATE set, derived from live metadata. CLIENT_SCOPE_COLUMN_NAMES
    above is a closed 3-name literal, so the bare-column guard below pins the
    TABLES those three spellings happen to find and never pins the SPELLINGS
    themselves -- while this schema is itself the proof that spelling drift is
    live, carrying three of them already (client_id, client_id_fk,
    client_id_assigned). A table scoping its rows by a fourth spelling would
    be invisible to BOTH client-column guards and would sit outside the
    --reset sweep entirely, which is the cross-reset tenant-data leak the
    bare-column guard exists to prevent.

    Restricted to string columns because a tenant scope in this schema is
    always a client-id string; an integer column called `client_count` is not
    a scope and should not have to be argued about.
    """
    return {
        column.name
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if isinstance(column.type, String) and ("client" in column.name.lower() or "tenant" in column.name.lower())
    }


def test_no_table_has_an_ambiguous_client_scope():
    """A table with TWO ForeignKeys to CLIENT has no derivable tenant column.

    Raised by the DeepSeek cross-model review of this branch, and worth acting
    on even though the schema is clean today: the original loop assigned inside
    the column walk, so a second ForeignKey would silently win by column order.
    --reset would then filter that table by the wrong column -- deleting rows
    belonging to a client nobody asked for, or leaving the requested client's
    behind to collide on the next re-seed. Neither failure names its cause, and
    both are cross-tenant.

    Two assertions, because either alone is weak. The first pins the live
    schema, which is what makes the guard meaningful now. The second proves the
    derivation REFUSES an ambiguous schema rather than guessing -- without it
    this test would still pass if _derive_client_scoped_tables went back to
    picking whichever ForeignKey came last.
    """
    ambiguous = {}
    for table in Base.metadata.sorted_tables:
        scopes = sorted(c.name for c in table.columns for fk in c.foreign_keys if fk.column.table.name == "CLIENT")
        if len(scopes) > 1:
            ambiguous[table.name] = scopes

    assert ambiguous == {}

    metadata = MetaData()
    Table("CLIENT", metadata, Column("client_id", String(50), primary_key=True))
    Table(
        "TWO_SCOPES",
        metadata,
        Column("row_id", Integer, primary_key=True),
        Column("client_id", String(50), ForeignKey("CLIENT.client_id")),
        Column("owner_client_id", String(50), ForeignKey("CLIENT.client_id")),
    )

    with pytest.raises(AmbiguousClientScope) as exc:
        _derive_client_scoped_tables(metadata)

    assert "TWO_SCOPES" in str(exc.value)

    # The escape hatch the message names must actually work. It did not at
    # first: the raise happens inside the table loop while the override map is
    # applied after it, so naming the table changed nothing and the
    # instruction was a dead end -- caught by the cross-model review of the
    # very commit that added it. Asserting the remedy resolves the error is
    # what keeps that from coming back.
    from backend.seed import cli as cli_module

    original = cli_module._UNDERIVABLE_CLIENT_SCOPE_COLUMNS
    cli_module._UNDERIVABLE_CLIENT_SCOPE_COLUMNS = {**original, "TWO_SCOPES": "owner_client_id"}
    try:
        resolved = _derive_client_scoped_tables(metadata)
    finally:
        cli_module._UNDERIVABLE_CLIENT_SCOPE_COLUMNS = original

    assert resolved["TWO_SCOPES"] == "owner_client_id"


def test_every_bare_client_column_is_a_deliberate_include_or_exclude():
    """The OTHER half of the anti-rot guard: a tenant column with NO
    ForeignKey.

    _derive_client_scoped_tables finds a table by following ForeignKeys to
    CLIENT.client_id, so a table that scopes rows with a bare column is
    invisible to it -- and that is not hypothetical, it is the shape that
    already bit once: EMPLOYEE.client_id_assigned carries no FK, the pure
    derivation silently dropped it, and only the explicit
    _UNDERIVABLE_CLIENT_SCOPE_COLUMNS entry keeps EMPLOYEE in the sweep.

    Pinning the set exactly means a FIFTH such table fails the build and
    forces a deliberate include-or-exclude decision. Silently excluded, it
    would keep a reset tenant's rows alive under a client id that has just
    been handed back -- a cross-reset tenant-data leak, not a tidiness issue.

    CLIENT is filtered out: CLIENT.client_id is the primary key every one of
    those ForeignKeys points AT, not a bare scope column. The four that remain
    are each argued in cli.py -- EMPLOYEE included via
    _UNDERIVABLE_CLIENT_SCOPE_COLUMNS, USER excluded as user state rather than
    client fixture data (Ruling 17), AUDIT_ENTRY and EVENT_STORE excluded as
    append-only ledgers this seeder writes zero rows to.
    """
    # The SPELLINGS first, derived, then the TABLES they find. Without this
    # line the assertion below is conditional on a closed literal nobody
    # rechecks: a fifth spelling (`client_ref`, `tenant_id`, ...) introduced
    # by a new table simply would not appear in `bare`, and both this guard
    # and _derive_client_scoped_tables would report clean while that table
    # kept a reset tenant's rows alive. Deriving the candidates makes such a
    # column fail the build BY NAME instead.
    assert _tenant_named_string_columns() == CLIENT_SCOPE_COLUMN_NAMES | CLIENT_DESCRIPTIVE_COLUMN_NAMES

    bare = {
        table.name
        for table in Base.metadata.sorted_tables
        for column in table.columns
        if column.name in CLIENT_SCOPE_COLUMN_NAMES and not column.foreign_keys
    } - {"CLIENT"}

    assert bare == {"EMPLOYEE", "USER", "AUDIT_ENTRY", "EVENT_STORE"}


def test_the_reset_sweep_covers_client_scoped_tables_the_seeder_never_writes():
    """Pins the two halves of the derivation that a reader would otherwise
    have to take on trust: the FK-derived set really does reach the blockers
    the review named, and the three bare-column tables are handled by
    deliberate decision rather than by accident."""
    from backend.seed.coverage import SEEDED

    for name in (
        "ALERT",
        "ALERT_CONFIG",
        "JOB",
        "EQUIPMENT",
        "BREAK_TIME",
        "FLOATING_POOL",
        "COVERAGE_ENTRY",
        "shift_coverage",
        "SIMULATION_SCENARIO",
        "CALCULATION_ASSUMPTION",
        "METRIC_CALCULATION_RESULT",
        "PART_OPPORTUNITIES",
        "capacity_calendar",
    ):
        assert name not in SEEDED, f"{name} is seeded after all -- rewrite this test, it proves nothing"
        assert name in CLIENT_SCOPED_TABLES, f"{name} would survive --reset and RESTRICT the CLIENT delete"

    assert len([n for n in CLIENT_SCOPED_TABLES if n.startswith("capacity_")]) == 13

    # EMPLOYEE.client_id_assigned is a bare column with no ForeignKey, so no
    # derivation can find it: only the explicit entry keeps it in the sweep.
    assert CLIENT_SCOPED_TABLES["EMPLOYEE"] == "client_id_assigned"

    # The three other bare client columns, each excluded on purpose. USER is
    # user state, not client fixture data (Ruling 17); AUDIT_ENTRY and
    # EVENT_STORE are append-only ledgers this seeder writes zero rows to.
    assert "USER" not in CLIENT_SCOPED_TABLES
    assert "AUDIT_ENTRY" not in CLIENT_SCOPED_TABLES
    assert "EVENT_STORE" not in CLIENT_SCOPED_TABLES


def test_the_nullable_tenant_sweep_set_is_exactly_the_known_two():
    """Pinned so a third such edge fails the build instead of silently
    stranding a tenant's rows or RESTRICTing a reset on a customer VM."""
    from backend.seed.cli import NULLABLE_TENANT_SWEEPS

    assert NULLABLE_TENANT_SWEEPS == (
        ("ALERT", "work_order_id", "client_id", "WORK_ORDER", "work_order_id"),
        ("FLOATING_POOL", "employee_id", "client_id", "EMPLOYEE", "employee_id"),
    )


def test_the_employee_cascade_children_are_exactly_the_known_two():
    """A third cascade child of EMPLOYEE must fail the build: it would be a new
    way for a reset to silently delete a real tenant's rows."""
    from backend.seed.cli import CASCADE_CHILDREN_OF_EMPLOYEE

    assert CASCADE_CHILDREN_OF_EMPLOYEE == ("EMPLOYEE_CLIENT_ASSIGNMENT", "EMPLOYEE_LINE_ASSIGNMENT")


def test_the_widened_reset_parents_are_exactly_the_known_one():
    """The tables sitting on BOTH sides of --reset: a PARENT in
    DEPENDENT_SWEEPS and a CHILD in NULLABLE_TENANT_SWEEPS.

    That intersection is where the two passes have to agree about which parent
    rows the reset deletes, and it is where they did not: pass 1 selected
    ALERT rows by `client_id IN client_ids` while pass 2 went on to delete
    NULL-tenant ALERT rows pointing at an in-scope WORK_ORDER, so those rows'
    ALERT_HISTORY children were never visited -- orphaned with foreign keys
    off (main()'s bare engine), IntegrityError with them on (InnoDB), which
    run_best_effort turns into a silent warning on the DEMO_MODE boot path.

    Derived from the two sweep tuples rather than naming ALERT, matching the
    four other derived sets in this module. The widening is generic --
    _rows_deleted_by_reset walks NULLABLE_TENANT_SWEEPS, so a second member
    would be handled without a code change -- so this pin is not what makes
    the next one correct; it is what makes the next one VISIBLE. Each member
    is a shape whose two passes must be re-argued (a NOT NULL tenant column,
    a self-reference, or a grandchild with children of its own would each need
    a different answer), and a set that grows silently is exactly how this
    bug got in.
    """
    from backend.seed.cli import WIDENED_RESET_PARENTS

    assert WIDENED_RESET_PARENTS == ("ALERT",)
