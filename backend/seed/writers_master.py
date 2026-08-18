"""Master-data writers: the entities operational rows point at.

Every row's created_at/updated_at comes from its event's instant. These
columns carry a server_default; letting them fall through would stamp all
45,000 rows at the seed-run instant, which is the defect this rebuild exists
to remove.
"""

from datetime import time
from typing import Callable, Dict, Type

from sqlalchemy import Connection

from backend.auth.password import hash_password
from backend.database import Base
from backend.seed import events as ev
from backend.seed.identity import IdMap, IntPkAllocator
from backend.seed.materialize import RowSink
from backend.seed.scenarios import USERS

#: Tables whose PK is an autoincrement integer the stream does not carry.
INT_PK_TABLES = ("PRODUCTION_LINE", "SHIFT", "PRODUCT", "EMPLOYEE")

#: user_id -> the client list from the declarative roster. UserCreated does
#: not carry it (the assignment already travels as its own
#: ClientAccessGranted events); looking it up here rather than widening the
#: event means the two can never disagree.
_USER_CLIENT_IDS: Dict[str, tuple] = {u.user_id: u.client_ids for u in USERS}


def build_allocators(conn: Connection) -> Dict[str, IntPkAllocator]:
    return {name: IntPkAllocator(conn, Base.metadata.tables[name]) for name in INT_PK_TABLES}


def handle(event: ev.Event, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> bool:
    handler = _HANDLERS.get(type(event))
    if handler is None:
        return False
    handler(event, sink, ids, allocators)
    return True


def _client_created(e: ev.ClientCreated, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> None:
    sink.add(
        "CLIENT",
        {
            "client_id": e.client_id,
            "client_name": e.name,
            "client_type": e.client_type,
            "is_active": True,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _client_configured(
    e: ev.ClientConfigured, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "CLIENT_CONFIG",
        {
            "client_id": e.client_id,
            "otd_mode": e.otd_mode,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _user_created(e: ev.UserCreated, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> None:
    # e.client_id is the stream sentinel (PLATFORM_CLIENT_ID) for every
    # UserCreated -- users are emitted before any client exists -- so the
    # real, possibly-multi-client scope has to come from the declarative
    # roster, never from the event's own client_id.
    client_ids = _USER_CLIENT_IDS[e.user_id]
    sink.add(
        "USER",
        {
            "user_id": e.user_id,
            "username": e.username,
            "email": e.email,
            "password_hash": hash_password(e.password),
            "full_name": e.full_name,
            "role": e.role,
            "client_id_assigned": ",".join(client_ids) if client_ids else None,
            "is_active": True,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _client_access_granted(
    e: ev.ClientAccessGranted, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "USER_CLIENT_ASSIGNMENT",
        {
            "user_id": e.user_id,
            "client_id": e.client_id,
            "assigned_at": e.at,
            "is_primary": e.is_primary,
            "is_active": True,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _line_commissioned(
    e: ev.LineCommissioned, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    line_id = allocators["PRODUCTION_LINE"].next()
    ids.assign("PRODUCTION_LINE", e.line_id, line_id)
    sink.add(
        "PRODUCTION_LINE",
        {
            "line_id": line_id,
            "client_id": e.client_id,
            "line_code": e.line_code,
            "line_name": e.name,
            "line_type": e.line_type,
            "is_active": True,
            "created_at": e.at,
        },
    )


def _shift_defined(e: ev.ShiftDefined, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> None:
    shift_id = allocators["SHIFT"].next()
    ids.assign("SHIFT", e.shift_id, shift_id)
    sink.add(
        "SHIFT",
        {
            "shift_id": shift_id,
            "client_id": e.client_id,
            "shift_name": e.name,
            "start_time": time(e.start_hour),
            "end_time": time(e.end_hour),
            "is_active": True,
            "created_at": e.at,
        },
    )


def _product_defined(e: ev.ProductDefined, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> None:
    product_id = allocators["PRODUCT"].next()
    ids.assign("PRODUCT", e.product_id, product_id)
    sink.add(
        "PRODUCT",
        {
            "product_id": product_id,
            "client_id": e.client_id,
            "product_code": e.product_code,
            "product_name": e.product_name,
            "unit_of_measure": e.unit_of_measure,
            "is_active": True,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _employee_hired(e: ev.EmployeeHired, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> None:
    employee_id = allocators["EMPLOYEE"].next()
    ids.assign("EMPLOYEE", e.employee_id, employee_id)
    sink.add(
        "EMPLOYEE",
        {
            "employee_id": employee_id,
            "employee_code": e.employee_code,
            "employee_name": e.employee_name,
            "client_id_assigned": e.client_id,
            "is_floating_pool": int(e.is_floating_pool),
            "is_active": True,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )
    sink.add(
        "EMPLOYEE_CLIENT_ASSIGNMENT",
        {
            "employee_id": employee_id,
            "client_id": e.client_id,
            "assignment_type": "FLOATING" if e.is_floating_pool else "DEDICATED",
            "assigned_at": e.at,
            "is_active": True,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )
    if e.line_id is not None:
        sink.add(
            "EMPLOYEE_LINE_ASSIGNMENT",
            {
                "employee_id": employee_id,
                "line_id": ids.resolve("PRODUCTION_LINE", e.line_id),
                "client_id": e.client_id,
                "effective_date": e.at.date(),
                "created_at": e.at,
            },
        )


def _defect_type_defined(
    e: ev.DefectTypeDefined, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "DEFECT_TYPE_CATALOG",
        {
            "defect_type_id": e.defect_type_id,
            "client_id": e.client_id,
            "defect_code": e.defect_code,
            "defect_name": e.defect_name,
            "category": e.category,
            "severity_default": e.severity,
            "is_active": True,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _hold_reason_defined(
    e: ev.HoldReasonDefined, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "HOLD_REASON_CATALOG",
        {
            "client_id": e.client_id,
            "reason_code": e.reason_code,
            "display_name": e.display_name,
            "is_default": e.is_default,
            "is_active": True,
            "created_at": e.at,
        },
    )


def _hold_status_defined(
    e: ev.HoldStatusDefined, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "HOLD_STATUS_CATALOG",
        {
            "client_id": e.client_id,
            "status_code": e.status_code,
            "display_name": e.display_name,
            "is_default": e.is_default,
            "is_active": True,
            "created_at": e.at,
        },
    )


def _threshold_set(e: ev.ThresholdSet, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> None:
    sink.add(
        "KPI_THRESHOLD",
        {
            "threshold_id": e.threshold_id,
            "client_id": e.client_id,
            "kpi_key": e.kpi_key,
            "target_value": e.target_value,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


_HANDLERS: Dict[Type[ev.Event], Callable] = {
    ev.ClientCreated: _client_created,
    ev.ClientConfigured: _client_configured,
    ev.UserCreated: _user_created,
    ev.ClientAccessGranted: _client_access_granted,
    ev.LineCommissioned: _line_commissioned,
    ev.ShiftDefined: _shift_defined,
    ev.ProductDefined: _product_defined,
    ev.EmployeeHired: _employee_hired,
    ev.DefectTypeDefined: _defect_type_defined,
    ev.HoldReasonDefined: _hold_reason_defined,
    ev.HoldStatusDefined: _hold_status_defined,
    ev.ThresholdSet: _threshold_set,
}
