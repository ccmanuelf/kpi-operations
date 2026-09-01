"""Event stream -> database rows.

Mechanical. Every value written here comes from an event; this module invents
nothing, and contains no clock: no datetime.now(), no func.now(), and no
column left to its server_default. That last one is not a style preference:
created_at carries a server default on every seeded table and
WORKFLOW_TRANSITION_LOG.transitioned_at does too, and letting them fall
through is precisely what collapsed all 40 existing transition chains into a
single instant.

ONE stated exception to "invents nothing": USER.password_hash. argon2id salts
randomly, so that single column differs between two runs at the same seed --
deliberate, argued at writers_master._user_created, and confined to that
column. Nothing else the write layer emits is non-deterministic.

Batching: rows accumulate per table and flush in Base.metadata.sorted_tables
order (FK-safe, derived rather than hand-maintained). Within a table the batch
keeps stream order and is never sorted -- active_as_of tie-breaks on ascending
transition_id, so insertion order is load-bearing (spec section 12).
"""

from typing import Iterable

from sqlalchemy import Connection, Table, insert

from backend.database import Base
from backend.seed.events import Event
from backend.seed.identity import IdMap
from backend.seed.profiles import Profile

# Base.metadata only carries the tables whose ORM classes have actually been
# imported somewhere in the process -- registration is a side effect of
# importing backend.orm, not of importing backend.database. Every test in
# this repo happens to trigger that import first (backend/tests/conftest.py
# does it), which hid this: import materialize.py as the FIRST thing in a
# fresh process (e.g. `python -m backend.seed.cli`) and Base.metadata is
# empty, so INSERT_ORDER below computes to [] and flush() silently writes
# nothing. Import backend.orm here, for its registration side effect, before
# reading sorted_tables.
import backend.orm  # noqa: F401  (import side effect: registers every ORM class on Base.metadata)

#: Rows per executemany chunk. Bounded so a 32-column table cannot build a
#: statement past MariaDB's max_allowed_packet on the FULL profile.
BATCH_SIZE = 500

#: FK-safe insert order, derived from the metadata's topological sort. Never
#: hand-maintain this: a hand-written list rots the first time a table is added
#: and the failure is an IntegrityError far from the edit that caused it.
INSERT_ORDER = [t.name for t in Base.metadata.sorted_tables]

#: Which column scopes each SEEDED table to a tenant. Salvaged from
#: seed_sample_client.py's (removed in S1c) _reset_table_order(), which was
#: the only place three different names (client_id / client_id_fk /
#: client_id_assigned) were ever written down.
#:
#: This is the WRITER-side contract: every row this materializer inserts must
#: carry a real client id in the column named here, never the platform
#: sentinel. --reset does NOT filter on it -- it derives its own, wider set
#: (cli.CLIENT_SCOPED_TABLES) covering every client-scoped table in the
#: schema, seeded or not, because what the seeder writes and what a reset must
#: clear are different sets.
CLIENT_SCOPE_COLUMN = {
    "CLIENT": "client_id",
    "CLIENT_CONFIG": "client_id",
    # Client-scoped, not global: KPI_THRESHOLD.client_id is nullable but real,
    # unique per (client_id, kpi_key), and seed_sample_client.py (removed in
    # S1c, the source this map was salvaged from) already lists it
    # client-scoped.
    "KPI_THRESHOLD": "client_id",
    "HOLD_REASON_CATALOG": "client_id",
    "HOLD_STATUS_CATALOG": "client_id",
    "DEFECT_TYPE_CATALOG": "client_id",
    "PRODUCTION_LINE": "client_id",
    "SHIFT": "client_id",
    "PRODUCT": "client_id",
    "EMPLOYEE": "client_id_assigned",
    "EMPLOYEE_CLIENT_ASSIGNMENT": "client_id",
    "EMPLOYEE_LINE_ASSIGNMENT": "client_id",
    "USER_CLIENT_ASSIGNMENT": "client_id",
    "WORK_ORDER": "client_id",
    "WORKFLOW_TRANSITION_LOG": "client_id",
    # `client_id_fk`, like DEFECT_DETAIL -- one of the three tenant spellings
    # this schema uses.
    "JOB": "client_id_fk",
    "HOLD_ENTRY": "client_id",
    "HOLD_STATUS_TRANSITION": "client_id",
    "ATTENDANCE_ENTRY": "client_id",
    "PRODUCTION_ENTRY": "client_id",
    "QUALITY_ENTRY": "client_id",
    "DEFECT_DETAIL": "client_id_fk",
    "DOWNTIME_ENTRY": "client_id",
    # The capacity workbook. Every one of these carries a plain `client_id`;
    # the three-spellings problem this map exists for is confined to the
    # operational tables above.
    "capacity_scenario": "client_id",
    "capacity_production_lines": "client_id",
    "capacity_calendar": "client_id",
    "capacity_orders": "client_id",
    "capacity_production_standards": "client_id",
    "capacity_bom_header": "client_id",
    "capacity_bom_detail": "client_id",
    "capacity_stock_snapshot": "client_id",
    "capacity_schedule": "client_id",
    "capacity_schedule_detail": "client_id",
    "capacity_analysis": "client_id",
    "capacity_component_check": "client_id",
    "capacity_kpi_commitment": "client_id",
    # The alert board. ALERT_HISTORY is deliberately absent: it carries no
    # client column at all -- it hangs off ALERT.alert_id -- so it is scoped
    # transitively, not directly.
    "ALERT": "client_id",
    "ALERT_CONFIG": "client_id",
    # The workforce tables. ATTENDANCE_HOUR_ALLOCATION is absent for the same
    # reason ALERT_HISTORY is: it carries no client column, hanging off
    # ATTENDANCE_ENTRY instead, so it is scoped transitively.
    "BREAK_TIME": "client_id",
    "FLOATING_POOL": "client_id",
    "COVERAGE_ENTRY": "client_id",
    "shift_coverage": "client_id",
    # Assumptions and saved simulations. ASSUMPTION_CHANGE is absent for the
    # same reason ALERT_HISTORY is: no client column of its own, scoped through
    # the assumption it records a change to.
    "CALCULATION_ASSUMPTION": "client_id",
    "SIMULATION_SCENARIO": "client_id",
}


class RowSink:
    """Accumulates rows per table, preserving the order they were added."""

    def __init__(self) -> None:
        self._rows: dict[str, list[dict]] = {}

    def add(self, table_name: str, row: dict) -> None:
        self._rows.setdefault(table_name, []).append(row)

    def rows(self, table_name: str) -> list[dict]:
        return self._rows.get(table_name, [])

    def tables(self) -> list[str]:
        return list(self._rows)


def bulk_insert(conn: Connection, table: Table, rows: list[dict]) -> None:
    if not rows:
        return
    for start in range(0, len(rows), BATCH_SIZE):
        conn.execute(insert(table), rows[start : start + BATCH_SIZE])


def flush(conn: Connection, sink: RowSink) -> dict[str, int]:
    # No "did the writers touch an undeclared table?" check here. It would have
    # to import backend.seed.coverage, which Task 8 creates -- a runtime import
    # from a module built three tasks later. The check belongs in a test and it
    # already has one: test_coverage.py's
    # test_the_materializer_writes_nothing_outside_the_contract asserts exactly
    # this against materialize()'s returned counts.
    #
    # Note also what this loop does NOT check: it walks INSERT_ORDER, not
    # sink.tables(), so a typo'd table name added to the sink (one that never
    # matches any key in INSERT_ORDER) is silently DROPPED here rather than
    # raising -- `set(sink.tables()) - set(INSERT_ORDER)` being non-empty
    # produces no error at this layer. Task 8's coverage check is what catches
    # that, by comparing materialize()'s returned counts against the writer
    # contract; it is not caught here.
    counts: dict[str, int] = {}
    for name in INSERT_ORDER:
        rows = sink.rows(name)
        if not rows:
            continue
        bulk_insert(conn, Base.metadata.tables[name], rows)
        counts[name] = len(rows)
    return counts


def materialize(conn: Connection, events: Iterable[Event], profile: Profile) -> dict[str, int]:
    # Tasks 6/7 create these; deliberately absent until then. `import x.y as y`
    # rather than `from x import y`: the latter resolves against backend.seed's
    # already-typechecked namespace and mypy reports attr-defined regardless of
    # ignore_missing_imports; the submodule-import form is what that flag
    # actually covers, so the whole-package mypy gate stays green without
    # stubbing the modules into existence.
    import backend.seed.writers_alerts as writers_alerts
    import backend.seed.writers_assumptions as writers_assumptions
    import backend.seed.writers_capacity as writers_capacity
    import backend.seed.writers_equipment as writers_equipment
    import backend.seed.writers_workforce as writers_workforce
    import backend.seed.writers_master as writers_master
    import backend.seed.writers_operations as writers_operations

    # writers_operations keeps module-level state (_open_rows) for the
    # in-place WORK_ORDER/HOLD_ENTRY mutation pattern -- a Core insert()
    # cannot UPDATE an accumulated row, so a later status-change event amends
    # the same dict object the opening event handed to the sink. Without this
    # reset, a second materialize() call in the same process would carry the
    # previous run's stale entries forward.
    writers_operations.reset()
    sink = RowSink()
    ids = IdMap()
    allocators = writers_master.build_allocators(conn)
    allocators.update(writers_capacity.build_allocators(conn))
    allocators.update(writers_workforce.build_allocators(conn))
    allocators.update(writers_assumptions.build_allocators(conn))
    allocators.update(writers_equipment.build_allocators(conn))

    for event in events:
        if writers_assumptions.handle(event, sink, ids, allocators):
            continue
        if writers_workforce.handle(event, sink, ids, allocators):
            continue
        if writers_alerts.handle(event, sink, ids, allocators):
            continue
        if writers_capacity.handle(event, sink, ids, allocators):
            continue
        if writers_equipment.handle(event, sink, ids, allocators):
            continue
        if writers_master.handle(event, sink, ids, allocators):
            continue
        if writers_operations.handle(event, sink, ids, profile):
            continue
        raise RuntimeError(f"no writer handles {type(event).__name__}")

    return flush(conn, sink)
