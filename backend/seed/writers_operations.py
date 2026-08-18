"""Operations writers: work-order chains, holds, and daily shift activity.

Paired with emitters_operations.py the same way writers_master.py is paired
with emitters_master.py. Every row's created_at/transitioned_at comes from
its event's instant -- the columns carry a server_default, and letting them
fall through is the exact defect this rebuild exists to remove: it is what
collapsed all 40 existing WORKFLOW_TRANSITION_LOG chains into a single
instant and made "what status was this on date D" unanswerable.
"""

from typing import Callable, Dict, Type

from backend.orm.work_order import WorkOrderStatus
from backend.seed import events as ev
from backend.seed.identity import IdMap
from backend.seed.materialize import RowSink
from backend.seed.profiles import Profile
from backend.seed.scenarios import ATTRIBUTION_USER_ID, HOLD_STATUSES

#: The catalog's own default opening status (HOLD_STATUSES' is_default=True
#: entry), used to seed HOLD_ENTRY.hold_status before any HoldStatusChanged
#: arrives. Not a duplicated literal: it is read off the same catalog data
#: that HOLD_STATUS_CATALOG itself is built from.
_DEFAULT_HOLD_STATUS = next(code for code, _name, is_default in HOLD_STATUSES if is_default)


def handle(event: ev.Event, sink: RowSink, ids: IdMap, profile: Profile) -> bool:
    handler = _HANDLERS.get(type(event))
    if handler is None:
        return False
    handler(event, sink, ids)
    return True


#: Rows already handed to the sink that a later event still amends. The sink
#: holds the SAME dict object, so mutating it here is what the final flush
#: writes. This is the only place in the materializer where a row changes
#: after being added -- a Core insert() cannot UPDATE an accumulated row, and
#: emitting a second WORK_ORDER (or HOLD_ENTRY) row per status change would
#: duplicate the order (or hold). Keyed by business id, cleared by reset(),
#: which materialize() calls at the start of every run -- without it, a
#: second seed in the same process would carry the previous run's stale
#: entries forward (see test_materializing_twice_in_one_process_resets_...).
_open_rows: Dict[str, dict] = {}


def reset() -> None:
    _open_rows.clear()


def _work_order_received(e: ev.WorkOrderReceived, sink: RowSink, ids: IdMap) -> None:
    row = {
        "work_order_id": e.work_order_id,
        "client_id": e.client_id,
        "style_model": e.style_model,
        "planned_quantity": e.planned_quantity,
        "received_date": e.at,
        "required_date": e.required_date,
        # planned_ship_date is OTD's highest-confidence signal (backend/
        # calculations/otd.py:43) -- omitting it drops every seeded order to
        # the 0.8-confidence required_date fallback instead of 1.0.
        "planned_ship_date": e.required_date,
        "priority": e.priority,
        "origin": e.origin,
        "status": WorkOrderStatus.RECEIVED,
        # previous_status/shipped_date/actual_delivery_date/closure_date are
        # only set once the order's chain reaches ON_HOLD/SHIPPED/CLOSED
        # (_work_order_status_changed mutates this same dict in place). All
        # four are declared here, defaulted to None, so every WORK_ORDER row
        # in the executemany batch carries the SAME key set regardless of how
        # far its own chain travels -- Core's insert() compiles one statement
        # for the whole batch, so a row missing a key another row supplies
        # raises "a value is required for bind parameter", not a silent NULL.
        "previous_status": None,
        "shipped_date": None,
        "actual_delivery_date": None,
        "closure_date": None,
        "created_at": e.at,
        "updated_at": e.at,
    }
    _open_rows[f"WO:{e.work_order_id}"] = row
    sink.add("WORK_ORDER", row)


def _work_order_status_changed(e: ev.WorkOrderStatusChanged, sink: RowSink, ids: IdMap) -> None:
    # transitioned_at supplied EXPLICITLY. This column carries a server
    # default; letting it fall through is exactly what stamped all 40 existing
    # chains at one instant and made "what status was this on date D"
    # unanswerable -- the premise of PR-C.
    sink.add(
        "WORKFLOW_TRANSITION_LOG",
        {
            "work_order_id": e.work_order_id,
            "client_id": e.client_id,
            "from_status": e.from_status,
            "to_status": e.to_status,
            "transitioned_by": ATTRIBUTION_USER_ID,
            "transitioned_at": e.at,
            "trigger_source": "SEED",
        },
    )
    order = _open_rows[f"WO:{e.work_order_id}"]
    order["status"] = WorkOrderStatus(e.to_status)
    order["previous_status"] = e.from_status
    order["updated_at"] = e.at
    # OTD reads actual_delivery_date and infers the planned date from
    # planned_ship_date -> required_date -> calculated (backend/calculations/
    # otd.py:43). Without a delivery date the order is excluded from the
    # denominator entirely and OTD renders as "no data" rather than a number.
    if e.to_status == "SHIPPED":
        order["shipped_date"] = e.at
        order["actual_delivery_date"] = e.at
    elif e.to_status == "CLOSED":
        order["closure_date"] = e.at


def _hold_opened(e: ev.HoldOpened, sink: RowSink, ids: IdMap) -> None:
    row = {
        "hold_entry_id": e.hold_entry_id,
        "client_id": e.client_id,
        "work_order_id": e.work_order_id,
        "hold_date": e.at,
        "hold_reason_category": e.reason_category,
        # hold_status is NOT NULL, so (unlike the datetime fields above) it
        # cannot default to None -- start it at the catalog's own opening
        # status. _hold_status_changed overwrites this with e.to_status the
        # moment the first HoldStatusChanged arrives, which is almost always
        # this same value; it only survives here in the rare case where the
        # window bound cuts a hold's chain off before any step is emitted.
        "hold_status": _DEFAULT_HOLD_STATUS,
        # resume_date is only set once a hold reaches RESUMED
        # (_hold_status_changed mutates this same dict in place). Declared
        # here as None so every HOLD_ENTRY row in the executemany batch
        # carries the same key set -- see the identical note in
        # _work_order_received.
        "resume_date": None,
        "created_at": e.at,
        "updated_at": e.at,
    }
    _open_rows[f"HOLD:{e.hold_entry_id}"] = row
    sink.add("HOLD_ENTRY", row)


def _hold_status_changed(e: ev.HoldStatusChanged, sink: RowSink, ids: IdMap) -> None:
    # from_status is None on the opening row, and that is load-bearing:
    # active_as_of's pre-history resolution reads the earliest transition and
    # treats a NULL from_status as "this hold began here" (PR-C1b).
    sink.add(
        "HOLD_STATUS_TRANSITION",
        {
            "hold_entry_id": e.hold_entry_id,
            "client_id": e.client_id,
            "from_status": e.from_status,
            "to_status": e.to_status,
            "transitioned_by": ATTRIBUTION_USER_ID,
            "transitioned_at": e.at,
        },
    )
    hold = _open_rows[f"HOLD:{e.hold_entry_id}"]
    hold["hold_status"] = e.to_status
    hold["updated_at"] = e.at
    if e.to_status == "RESUMED":
        hold["resume_date"] = e.at


def _attendance_recorded(e: ev.AttendanceRecorded, sink: RowSink, ids: IdMap) -> None:
    sink.add(
        "ATTENDANCE_ENTRY",
        {
            # One row per employee per shift per day -- the natural key.
            "attendance_entry_id": f"{e.client_id}-AE-{e.shift_date:%Y%m%d}-{e.shift_id}-{e.employee_id}",
            "client_id": e.client_id,
            "line_id": ids.resolve("PRODUCTION_LINE", e.line_id),
            "employee_id": ids.resolve("EMPLOYEE", e.employee_id),
            "shift_date": e.shift_date,
            "shift_id": ids.resolve("SHIFT", e.shift_id),
            "scheduled_hours": e.scheduled_hours,
            "actual_hours": e.hours_worked,
            "is_absent": int(e.is_absent),
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _production_recorded(e: ev.ProductionRecorded, sink: RowSink, ids: IdMap) -> None:
    sink.add(
        "PRODUCTION_ENTRY",
        {
            "production_entry_id": e.production_entry_id,
            "client_id": e.client_id,
            "line_id": ids.resolve("PRODUCTION_LINE", e.line_id),
            "product_id": ids.resolve("PRODUCT", e.product_id),
            "shift_id": ids.resolve("SHIFT", e.shift_id),
            "work_order_id": e.work_order_id,
            # PRODUCTION_ENTRY carries both columns; the app's own schema
            # (backend/schemas/production.py) treats shift_date as defaulting
            # to production_date when not given separately, so the event's
            # single shift_date fills both.
            "production_date": e.shift_date,
            "shift_date": e.shift_date,
            "units_produced": e.units_produced,
            "run_time_hours": e.run_time_hours,
            "scrap_count": e.scrap_count,
            "employees_assigned": e.employees_assigned,
            "entered_by": e.entered_by,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _quality_inspected(e: ev.QualityInspected, sink: RowSink, ids: IdMap) -> None:
    sink.add(
        "QUALITY_ENTRY",
        {
            "quality_entry_id": e.quality_entry_id,
            "client_id": e.client_id,
            "work_order_id": e.work_order_id,
            "shift_date": e.shift_date,
            "units_inspected": e.units_inspected,
            "units_passed": e.units_passed,
            "units_defective": e.units_defective,
            "total_defects_count": e.total_defects_count,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


def _defects_found(e: ev.DefectsFound, sink: RowSink, ids: IdMap) -> None:
    sink.add(
        "DEFECT_DETAIL",
        {
            # The generator emits each code at most once per inspection, so no
            # counter is needed -- if that ever stops holding, this PK
            # collides loudly on insert rather than silently overwriting.
            "defect_detail_id": f"{e.quality_entry_id}-{e.defect_code}",
            "quality_entry_id": e.quality_entry_id,
            "client_id_fk": e.client_id,
            # defect_type stores the CATALOG CODE (joins to
            # DEFECT_TYPE_CATALOG.defect_code), not a display name -- storing
            # the display name is the defect that left all 80 live rows
            # saying "Stitching", a name in no catalog.
            "defect_type": e.defect_code,
            "defect_count": e.defect_count,
            "created_at": e.at,
        },
    )


def _downtime_logged(e: ev.DowntimeLogged, sink: RowSink, ids: IdMap) -> None:
    sink.add(
        "DOWNTIME_ENTRY",
        {
            "downtime_entry_id": f"{e.client_id}-DT-{e.shift_date:%Y%m%d}-{e.line_id}-{e.shift_id}",
            "client_id": e.client_id,
            "line_id": ids.resolve("PRODUCTION_LINE", e.line_id),
            "shift_date": e.shift_date,
            "downtime_reason": e.downtime_reason,
            "downtime_duration_minutes": e.downtime_minutes,
            # Q2 and the Q4 correlation block slice by this column.
            "root_cause_category": e.root_cause_category,
            "created_at": e.at,
            "updated_at": e.at,
        },
    )


_HANDLERS: Dict[Type[ev.Event], Callable] = {
    ev.WorkOrderReceived: _work_order_received,
    ev.WorkOrderStatusChanged: _work_order_status_changed,
    ev.HoldOpened: _hold_opened,
    ev.HoldStatusChanged: _hold_status_changed,
    ev.AttendanceRecorded: _attendance_recorded,
    ev.ProductionRecorded: _production_recorded,
    ev.QualityInspected: _quality_inspected,
    ev.DefectsFound: _defects_found,
    ev.DowntimeLogged: _downtime_logged,
}
