"""Equipment and part-opportunity events -> rows.

EQUIPMENT carries an autoincrement key and so draws from an allocator;
PART_OPPORTUNITIES is keyed by the part number itself, which the emitter
already holds, so it needs no allocator and no IdMap entry.

`line_id` arrives as a seed key and is resolved here -- the emitter cannot
know the autoincrement id, and a shared machine carries None rather than a
key, which must stay NULL rather than become a resolve() miss.
"""

from __future__ import annotations

from typing import Callable, Dict, Type

from sqlalchemy.engine import Connection

from backend.database import Base
from backend.seed import events as ev
from backend.seed.identity import IdMap, IntPkAllocator
from backend.seed.materialize import RowSink

INT_PK_TABLES = ("EQUIPMENT",)


def build_allocators(conn: Connection) -> Dict[str, IntPkAllocator]:
    return {name: IntPkAllocator(conn, Base.metadata.tables[name]) for name in INT_PK_TABLES}


def handle(event: ev.Event, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> bool:
    handler = _HANDLERS.get(type(event))
    if handler is None:
        return False
    handler(event, sink, ids, allocators)
    return True


def _equipment_registered(
    e: ev.EquipmentRegistered, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    equipment_id = allocators["EQUIPMENT"].next()
    ids.assign("EQUIPMENT", e.equipment_key, equipment_id)
    sink.add(
        "EQUIPMENT",
        {
            "equipment_id": equipment_id,
            "client_id": e.client_id,
            # None stays NULL: a shared machine hangs off no line, and
            # resolve() on a None key would be a lookup miss, not a NULL.
            "line_id": (ids.resolve("PRODUCTION_LINE", e.line_key) if e.line_key is not None else None),
            "equipment_code": e.equipment_code,
            "equipment_name": e.equipment_name,
            "equipment_type": e.equipment_type,
            "is_shared": e.is_shared,
            "status": e.status,
            "last_maintenance_date": e.last_maintenance_date,
            "next_maintenance_date": e.next_maintenance_date,
            "notes": e.notes,
            "is_active": e.is_active,
            "created_at": e.at,
        },
    )


def _part_opportunity_defined(
    e: ev.PartOpportunityDefined, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "PART_OPPORTUNITIES",
        {
            "part_number": e.part_number,
            "client_id_fk": e.client_id,
            "opportunities_per_unit": e.opportunities_per_unit,
            "part_description": e.part_description,
            "part_category": e.part_category,
            "notes": None,
            "is_active": True,
            # No created_at/updated_at on this table -- it carries soft-delete
            # columns (deleted_at/deleted_by) and no timestamps.
        },
    )


_HANDLERS: Dict[Type[ev.Event], Callable] = {
    ev.EquipmentRegistered: _equipment_registered,
    ev.PartOpportunityDefined: _part_opportunity_defined,
}
