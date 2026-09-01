"""Workforce events -> rows: breaks, the floating pool, and coverage.

Four tables split across two shapes. BREAK_TIME, FLOATING_POOL and
shift_coverage carry autoincrement integer keys the stream does not know, so
they draw from allocators. COVERAGE_ENTRY carries a string key the emitter
mints, because coverage is identified by (client, day, shift, employee) and a
generated integer would make the same coverage un-recognisable between runs.

Every one of these resolves EMPLOYEE and SHIFT through the IdMap rather than
recomputing a business id, so a coverage row cannot name an employee the
stream never hired.
"""

from __future__ import annotations

from typing import Callable, Dict, Type

from sqlalchemy.engine import Connection

from backend.database import Base
from backend.seed import events as ev
from backend.seed.identity import IdMap, IntPkAllocator
from backend.seed.materialize import RowSink

INT_PK_TABLES = ("BREAK_TIME", "FLOATING_POOL", "shift_coverage")


def build_allocators(conn: Connection) -> Dict[str, IntPkAllocator]:
    return {name: IntPkAllocator(conn, Base.metadata.tables[name]) for name in INT_PK_TABLES}


def handle(event: ev.Event, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> bool:
    handler = _HANDLERS.get(type(event))
    if handler is None:
        return False
    handler(event, sink, ids, allocators)
    return True


def _break_defined(e: ev.BreakTimeDefined, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> None:
    sink.add(
        "BREAK_TIME",
        {
            "break_id": allocators["BREAK_TIME"].next(),
            "shift_id": ids.resolve("SHIFT", e.shift_id),
            "client_id": e.client_id,
            "break_name": e.break_name,
            "start_offset_minutes": e.start_offset_minutes,
            "duration_minutes": e.duration_minutes,
            "applies_to": e.applies_to,
            "is_active": True,
            "created_at": e.at,
        },
    )


def _pool_member_added(
    e: ev.FloatingPoolMemberAdded, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "FLOATING_POOL",
        {
            "pool_id": allocators["FLOATING_POOL"].next(),
            "client_id": e.client_id,
            "employee_id": ids.resolve("EMPLOYEE", e.employee_id),
            "available_from": e.available_from,
            "available_to": e.available_to,
            "current_assignment": e.current_assignment,
            "is_active": True,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _absence_covered(e: ev.AbsenceCovered, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> None:
    sink.add(
        "COVERAGE_ENTRY",
        {
            "coverage_entry_id": e.coverage_key,
            "client_id": e.client_id,
            "floating_employee_id": ids.resolve("EMPLOYEE", e.floating_employee_id),
            "covered_employee_id": ids.resolve("EMPLOYEE", e.covered_employee_id),
            "shift_date": e.shift_date,
            "shift_id": ids.resolve("SHIFT", e.shift_id),
            "coverage_hours": e.coverage_hours,
            "coverage_reason": e.coverage_reason,
            "assigned_by": e.assigned_by,
            "created_at": e.at,
            # Explicit, like every other table here: the column carries a
            # server_default, so omitting it stamps the wall clock inside a
            # back-dated seed. Caught by
            # test_created_at_is_back_dated_on_every_seeded_table.
            "updated_at": e.at,
        },
    )


def _shift_coverage_recorded(
    e: ev.ShiftCoverageRecorded, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "shift_coverage",
        {
            "coverage_id": allocators["shift_coverage"].next(),
            "client_id": e.client_id,
            "shift_id": ids.resolve("SHIFT", e.shift_id),
            "coverage_date": e.coverage_date,
            "required_employees": e.required_employees,
            "actual_employees": e.actual_employees,
            "coverage_percentage": e.coverage_percentage,
            "entered_by": e.entered_by,
            "is_active": True,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


_HANDLERS: Dict[Type[ev.Event], Callable] = {
    ev.BreakTimeDefined: _break_defined,
    ev.FloatingPoolMemberAdded: _pool_member_added,
    ev.AbsenceCovered: _absence_covered,
    ev.ShiftCoverageRecorded: _shift_coverage_recorded,
}
