"""Assumption and simulation events -> rows.

CALCULATION_ASSUMPTION and SIMULATION_SCENARIO carry autoincrement integer
keys, so they draw from allocators; ASSUMPTION_CHANGE resolves its parent
through the IdMap rather than recomputing anything.

`value_json` columns are TEXT holding JSON, not JSON columns -- the emitter
encodes them and the writer passes the string through, so what lands in the
row is exactly what the dual-view services decode.
"""

from __future__ import annotations

from typing import Callable, Dict, Type

from sqlalchemy.engine import Connection

from backend.database import Base
from backend.seed import events as ev
from backend.seed.identity import IdMap, IntPkAllocator
from backend.seed.materialize import RowSink

INT_PK_TABLES = ("CALCULATION_ASSUMPTION", "ASSUMPTION_CHANGE", "SIMULATION_SCENARIO")


def build_allocators(conn: Connection) -> Dict[str, IntPkAllocator]:
    return {name: IntPkAllocator(conn, Base.metadata.tables[name]) for name in INT_PK_TABLES}


def handle(event: ev.Event, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> bool:
    handler = _HANDLERS.get(type(event))
    if handler is None:
        return False
    handler(event, sink, ids, allocators)
    return True


def _assumption_registered(
    e: ev.AssumptionRegistered, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    assumption_id = allocators["CALCULATION_ASSUMPTION"].next()
    ids.assign("CALCULATION_ASSUMPTION", e.assumption_key, assumption_id)
    sink.add(
        "CALCULATION_ASSUMPTION",
        {
            "assumption_id": assumption_id,
            "client_id": e.client_id,
            "assumption_name": e.assumption_name,
            "value_json": e.value_json,
            "rationale": e.rationale,
            "effective_date": e.effective_date,
            "expiration_date": None,
            "status": e.status,
            "proposed_by": e.proposed_by,
            "proposed_at": e.proposed_at,
            "approved_by": e.approved_by,
            "approved_at": e.approved_at,
            "is_active": True,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _assumption_changed(
    e: ev.AssumptionChanged, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "ASSUMPTION_CHANGE",
        {
            "change_id": allocators["ASSUMPTION_CHANGE"].next(),
            "assumption_id": ids.resolve("CALCULATION_ASSUMPTION", e.assumption_key),
            "changed_by": e.changed_by,
            "changed_at": e.at,
            "previous_value_json": e.previous_value_json,
            "new_value_json": e.new_value_json,
            "previous_status": e.previous_status,
            "new_status": e.new_status,
            "change_reason": e.change_reason,
        },
    )


def _simulation_saved(
    e: ev.SimulationScenarioSaved, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "SIMULATION_SCENARIO",
        {
            "id": allocators["SIMULATION_SCENARIO"].next(),
            "client_id": e.client_id,
            "name": e.name,
            "description": e.description,
            "config_json": dict(e.config),
            "last_run_summary": dict(e.last_run_summary) if e.last_run_summary else None,
            "last_run_at": e.last_run_at,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


_HANDLERS: Dict[Type[ev.Event], Callable] = {
    ev.AssumptionRegistered: _assumption_registered,
    ev.AssumptionChanged: _assumption_changed,
    ev.SimulationScenarioSaved: _simulation_saved,
}
