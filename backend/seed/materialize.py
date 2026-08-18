"""Event stream -> database rows.

Mechanical. Every value written here comes from an event; this module invents
nothing, and contains no clock -- no datetime.now(), no func.now(), and no
column left to its server_default. That last one is not a style preference:
created_at carries a server default on every seeded table and
WORKFLOW_TRANSITION_LOG.transitioned_at does too, and letting them fall
through is precisely what collapsed all 40 existing transition chains into a
single instant.

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

#: Rows per executemany chunk. Bounded so a 32-column table cannot build a
#: statement past MariaDB's max_allowed_packet on the FULL profile.
BATCH_SIZE = 500

#: FK-safe insert order, derived from the metadata's topological sort. Never
#: hand-maintain this: a hand-written list rots the first time a table is added
#: and the failure is an IntegrityError far from the edit that caused it.
INSERT_ORDER = [t.name for t in Base.metadata.sorted_tables]

#: Which column scopes each table to a tenant. Salvaged from the retiring
#: seed_sample_client._reset_table_order(), which is the only place three
#: different names (client_id / client_id_fk / client_id_assigned) were ever
#: written down. --reset filters on this; a missing entry means a client's rows
#: survive a reset and collide on re-seed.
CLIENT_SCOPE_COLUMN = {
    "CLIENT": "client_id",
    "CLIENT_CONFIG": "client_id",
    "KPI_THRESHOLD": None,  # global; not client-scoped
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
    "HOLD_ENTRY": "client_id",
    "HOLD_STATUS_TRANSITION": "client_id",
    "ATTENDANCE_ENTRY": "client_id",
    "PRODUCTION_ENTRY": "client_id",
    "QUALITY_ENTRY": "client_id",
    "DEFECT_DETAIL": "client_id_fk",
    "DOWNTIME_ENTRY": "client_id",
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
    # Note also what NOT to check: INSERT_ORDER covers every table in the
    # metadata, so `set(sink.tables()) - set(INSERT_ORDER)` is empty by
    # construction and could never fire.
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
    import backend.seed.writers_master as writers_master
    import backend.seed.writers_operations as writers_operations

    sink = RowSink()
    ids = IdMap()
    allocators = writers_master.build_allocators(conn)

    for event in events:
        if writers_master.handle(event, sink, ids, allocators):
            continue
        if writers_operations.handle(event, sink, ids, profile):
            continue
        raise RuntimeError(f"no writer handles {type(event).__name__}")

    return flush(conn, sink)
