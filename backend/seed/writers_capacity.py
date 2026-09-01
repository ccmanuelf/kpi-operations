"""Capacity workbook events -> rows.

Same contract as `writers_master`: one handler per event type, rows pushed at
a `RowSink`, integer PKs drawn from an allocator that starts above the table's
current maximum so a prod-safe INSERT-only seed cannot collide with rows a
real client already owns.

EVERY TABLE HERE SETS `updated_at` EXPLICITLY. All twelve capacity tables
declare `server_default=func.now()` on that column, so omitting it stamps the
row with the wall clock and a back-dated seed ends up containing rows edited
in the future. `test_created_at_is_back_dated_on_every_seeded_table` catches
it, but only after the fact -- setting it here is the fix, not the guard.
"""

from __future__ import annotations

from typing import Callable, Dict, Type

from sqlalchemy.engine import Connection

from backend.database import Base
from backend.seed import events as ev
from backend.seed.identity import IdMap, IntPkAllocator
from backend.seed.materialize import RowSink

#: Capacity tables whose PK is an autoincrement integer the stream does not
#: carry. `capacity_scenario` is allocated in writers_master, where its event
#: lives, so it is deliberately absent here.
INT_PK_TABLES = (
    "capacity_production_lines",
    "capacity_calendar",
    "capacity_orders",
    "capacity_production_standards",
    "capacity_bom_header",
    "capacity_bom_detail",
    "capacity_stock_snapshot",
)


def build_allocators(conn: Connection) -> Dict[str, IntPkAllocator]:
    return {name: IntPkAllocator(conn, Base.metadata.tables[name]) for name in INT_PK_TABLES}


def handle(event: ev.Event, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> bool:
    handler = _HANDLERS.get(type(event))
    if handler is None:
        return False
    handler(event, sink, ids, allocators)
    return True


def _line_defined(e: ev.CapacityLineDefined, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> None:
    line_id = allocators["capacity_production_lines"].next()
    ids.assign("capacity_production_lines", e.line_key, line_id)
    sink.add(
        "capacity_production_lines",
        {
            "id": line_id,
            "client_id": e.client_id,
            "line_code": e.line_code,
            "line_name": e.line_name,
            "department": e.department,
            "standard_capacity_units_per_hour": e.units_per_hour,
            "max_operators": e.max_operators,
            "efficiency_factor": e.efficiency_factor,
            "absenteeism_factor": e.absenteeism_factor,
            "is_active": True,
            "notes": None,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _calendar_day(
    e: ev.CapacityCalendarDayDeclared, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "capacity_calendar",
        {
            "id": allocators["capacity_calendar"].next(),
            "client_id": e.client_id,
            "calendar_date": e.calendar_date,
            "is_working_day": e.is_working_day,
            "shifts_available": e.shifts_available,
            "shift1_hours": e.shift1_hours,
            "shift2_hours": e.shift2_hours,
            "shift3_hours": "0.00",
            "holiday_name": e.holiday_name,
            "notes": None,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _order_placed(e: ev.CapacityOrderPlaced, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> None:
    order_id = allocators["capacity_orders"].next()
    ids.assign("capacity_orders", e.order_ref, order_id)
    sink.add(
        "capacity_orders",
        {
            "id": order_id,
            "client_id": e.client_id,
            "order_number": e.order_number,
            "customer_name": e.customer_name,
            "style_model": e.style_model,
            "style_description": e.style_description,
            "order_quantity": e.order_quantity,
            "completed_quantity": e.completed_quantity,
            "order_date": e.order_date,
            "required_date": e.required_date,
            "planned_start_date": e.planned_start_date,
            "planned_end_date": e.planned_end_date,
            "priority": e.priority,
            "status": e.status,
            "order_sam_minutes": e.order_sam_minutes,
            "notes": None,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _standard_defined(
    e: ev.CapacityStandardDefined, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "capacity_production_standards",
        {
            "id": allocators["capacity_production_standards"].next(),
            "client_id": e.client_id,
            "style_model": e.style_model,
            "operation_code": e.operation_code,
            "operation_name": e.operation_name,
            "department": e.department,
            "sam_minutes": e.sam_minutes,
            "setup_time_minutes": e.setup_time_minutes,
            "machine_time_minutes": e.machine_time_minutes,
            "manual_time_minutes": e.manual_time_minutes,
            "notes": None,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _bom_defined(e: ev.CapacityBomDefined, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> None:
    header_id = allocators["capacity_bom_header"].next()
    ids.assign("capacity_bom_header", e.bom_key, header_id)
    sink.add(
        "capacity_bom_header",
        {
            "id": header_id,
            "client_id": e.client_id,
            "parent_item_code": e.parent_item_code,
            "parent_item_description": e.parent_item_description,
            "style_model": e.style_model,
            "revision": e.revision,
            "is_active": True,
            "notes": None,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _bom_line_defined(
    e: ev.CapacityBomLineDefined, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "capacity_bom_detail",
        {
            "id": allocators["capacity_bom_detail"].next(),
            # resolve(), not a lookup that can return None: an unknown key
            # names the ordering bug instead of writing a NULL FK.
            "header_id": ids.resolve("capacity_bom_header", e.bom_key),
            "client_id": e.client_id,
            "component_item_code": e.component_item_code,
            "component_description": e.component_description,
            "quantity_per": e.quantity_per,
            "unit_of_measure": e.unit_of_measure,
            "waste_percentage": e.waste_percentage,
            "component_type": e.component_type,
            "notes": None,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _stock_counted(
    e: ev.CapacityStockCounted, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "capacity_stock_snapshot",
        {
            "id": allocators["capacity_stock_snapshot"].next(),
            "client_id": e.client_id,
            "snapshot_date": e.snapshot_date,
            "item_code": e.item_code,
            "item_description": e.item_description,
            "on_hand_quantity": e.on_hand_quantity,
            "allocated_quantity": e.allocated_quantity,
            "on_order_quantity": e.on_order_quantity,
            "available_quantity": e.available_quantity,
            "unit_of_measure": e.unit_of_measure,
            "location": e.location,
            "notes": None,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


_HANDLERS: Dict[Type[ev.Event], Callable] = {
    ev.CapacityLineDefined: _line_defined,
    ev.CapacityCalendarDayDeclared: _calendar_day,
    ev.CapacityOrderPlaced: _order_placed,
    ev.CapacityStandardDefined: _standard_defined,
    ev.CapacityBomDefined: _bom_defined,
    ev.CapacityBomLineDefined: _bom_line_defined,
    ev.CapacityStockCounted: _stock_counted,
}
