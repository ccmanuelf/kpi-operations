"""Master-data emitters: the setup band each client opens with.

Named for the writers that consume it (writers_master.py) -- one module per
side of the same boundary, so a reader looking for "who produces PRODUCT rows"
finds the pair together.

Everything here lands on the client's first calendar day, minutes apart. The
band returns what the operations emitters need to reference: the entity ids it
minted, the stagger steps sized to this client's line and shift counts, and the
day activity may begin on.
"""

from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Dict, List, NamedTuple, Tuple, Type

from backend.seed.events import (
    ClientConfigured,
    ClientCreated,
    DefectTypeDefined,
    EmployeeHired,
    Event,
    HoldReasonDefined,
    HoldStatusDefined,
    LineCommissioned,
    ProductDefined,
    ShiftDefined,
    ThresholdSet,
)
from backend.seed.profiles import Profile
from backend.seed.scenarios import (
    DEFECT_CATALOG,
    HOLD_REASONS,
    HOLD_STATUSES,
    LINE_TYPE,
    THRESHOLDS,
    UNIT_OF_MEASURE,
    ClientScenario,
    ProductSpec,
)

#: CLIENT_CONFIG.otd_mode. STANDARD is the application's own default
#: (backend/schemas/client_config.py), so a seeded config says exactly what the
#: app would have written for itself rather than a mode nothing else picks.
OTD_MODE = "STANDARD"

#: Declared shift length, used to derive SHIFT.end_hour from start_hour and to
#: fill ATTENDANCE_ENTRY.scheduled_hours.
SHIFT_LENGTH_HOURS = 8


class ClientSetup(NamedTuple):
    """What the setup band minted, for the emitters that reference it.

    Returned as one value rather than nine loose ones so a caller cannot pair
    a client's lines with another client's stagger steps: the steps are sized
    to THIS client's line and shift counts (see where they are computed), and
    that sizing is what keeps distinct lines and shifts off the same instant.
    """

    lines: List[str]
    shifts: List[str]
    products: List[str]
    products_by_id: Dict[str, ProductSpec]
    employees: List[Tuple[str, str]]
    line_minute_step: int
    shift_hour_step: int
    activity_start: date
    activity_days: int


def emit_setup(
    emit: Callable[..., None],
    scenario: ClientScenario,
    profile: Profile,
    start: date,
    as_of: date,
    is_first: bool,
) -> ClientSetup:
    cid = scenario.client_id

    # --- setup, all on the first day, minutes apart so order is unambiguous.
    # A running cursor rather than hardcoded band starts (2 / 10 / 20 / 30):
    # those silently interleaved once a count exceeded its band width (e.g.
    # ShiftDefined's 10 + i colliding with ProductDefined's 20 + i once
    # shifts_per_client > 10). A cursor can't collide regardless of profile
    # size; only the relative order (catalogs, lines, shifts, products,
    # employees) matters, not the exact minute offsets. `setup()` owns both
    # the stamp and the increment so no emission can forget to advance it.
    day0 = datetime.combine(start, time(6, 0))
    emit(
        ClientCreated,
        day0,
        cid,
        name=scenario.name,
        pay_model=scenario.pay_model,
        client_type=scenario.client_type,
    )
    minute_cursor = 1

    def setup(cls: Type[Event], **kw: Any) -> None:
        nonlocal minute_cursor
        emit(cls, day0 + timedelta(minutes=minute_cursor), cid, **kw)
        minute_cursor += 1

    setup(ClientConfigured, otd_mode=OTD_MODE)

    # Catalogs before the entities that quote them: a hold reason, a hold
    # status and a defect code are all foreign keys in the target schema, so a
    # HoldOpened or a DefectsFound must never be the first mention of one.
    for reason_code, reason_name, reason_default in HOLD_REASONS:
        setup(HoldReasonDefined, reason_code=reason_code, display_name=reason_name, is_default=reason_default)
    for status_code, status_name, status_default in HOLD_STATUSES:
        setup(HoldStatusDefined, status_code=status_code, display_name=status_name, is_default=status_default)
    for defect_code, defect_name, defect_category, defect_severity in DEFECT_CATALOG:
        setup(
            DefectTypeDefined,
            defect_type_id=f"{cid}-DT-{defect_code}",
            defect_code=defect_code,
            defect_name=defect_name,
            category=defect_category,
            severity=defect_severity,
        )

    lines = [f"{cid}-LINE-{i:02d}" for i in range(1, profile.lines_per_client + 1)]
    for i, line_id in enumerate(lines):
        setup(
            LineCommissioned,
            line_id=line_id,
            name=f"Line {i + 1}",
            line_code=f"LINE-{i + 1:02d}",
            line_type=LINE_TYPE,
        )
    # Per-line minute stagger for the shift events below, sized to the actual
    # line count rather than a fixed +1: a fixed step aliases once
    # lines_per_client exceeds the modulus (line 1 and line 61 both landed on
    # :31 under the old `(30 + li) % 60`). Floor division keeps every
    # li * line_minute_step strictly below 60, so distinct lines can never land
    # on the same minute for any lines_per_client a Profile could express.
    line_minute_step = max(1, 60 // len(lines))

    shifts = [f"{cid}-SHIFT-{i:02d}" for i in range(1, profile.shifts_per_client + 1)]
    # Same reasoning as line_minute_step above, for hours: the old fixed
    # `si * 8` step aliased shift 1 with shift 4 (both landed on hour 6) once
    # shifts_per_client reached 4. Sizing the step to the actual shift count
    # keeps every si * shift_hour_step strictly below 24.
    shift_hour_step = max(1, 24 // len(shifts))
    for i, shift_id in enumerate(shifts):
        # Same formula the shift-activity hour below uses (si there == i here,
        # both index the same shifts list): the declared start_hour must not
        # diverge from the hour events are actually stamped at.
        start_hour = (6 + i * shift_hour_step) % 24
        setup(
            ShiftDefined,
            shift_id=shift_id,
            name=f"Shift {i + 1}",
            start_hour=start_hour,
            end_hour=(start_hour + SHIFT_LENGTH_HOURS) % 24,
        )

    products = [f"{cid}-PROD-{i:02d}" for i in range(1, len(scenario.products) + 1)]
    # Retained, not just emitted: WorkOrderReceived.style_model is the ordered
    # product's own style, so the loop below has to be able to look the spec
    # back up from the id it stamps on the order.
    products_by_id: Dict[str, ProductSpec] = dict(zip(products, scenario.products))
    for product_id, product in zip(products, scenario.products):
        setup(
            ProductDefined,
            product_id=product_id,
            style=product.style,
            product_code=product.code,
            product_name=product.name,
            unit_of_measure=UNIT_OF_MEASURE,
        )

    # Retained for the same kind of reason: attendance is one row per employee
    # ON THIS LINE, so the shift loop needs the roster, not just the count.
    employees: List[Tuple[str, str]] = []
    for i in range(profile.employees_per_client):
        employee_id = f"{cid}-EMP-{i + 1:03d}"
        employee_line = lines[i % len(lines)]
        employees.append((employee_id, employee_line))
        setup(
            EmployeeHired,
            employee_id=employee_id,
            line_id=employee_line,
            # EMPLOYEE.employee_code is unique across the whole table, not per
            # client, so the code carries the client prefix.
            employee_code=employee_id,
            employee_name=f"Operator {i + 1}",
            is_floating_pool=False,
        )

    if is_first:
        for kpi_key, target_value in THRESHOLDS:
            setup(
                ThresholdSet,
                threshold_id=f"THR-{kpi_key.upper()}",
                kpi_key=kpi_key,
                target_value=target_value,
            )

    # --- Setup is finished. Everything the operations emitters produce
    # references entities created above, so all of it must be stamped
    # strictly later than ALL of them.
    #
    # Hour/minute arithmetic alone cannot guarantee that: the shift-hour and
    # line-minute steps are modular, so some (line, shift) index always wraps
    # back toward 00:00 -- at 2 lines `(30 + 1*30) % 60` is minute 0, and at 4
    # shifts `(6 + 3*6) % 24` is hour 0, both of which land BEFORE the 06:00
    # setup block on the same calendar day. The setup cursor can also grow past
    # 07:00 (and past midnight) once a profile declares enough entities,
    # colliding with the fixed 07:00 WorkOrderReceived instant.
    #
    # Bands, not arithmetic, are the fix: setup owns whole calendar days, and
    # all activity starts on the day AFTER the last setup instant. No
    # (lines, shifts, employees, products) a Profile can express can then place
    # an activity event before the entity it references, because the day
    # boundary dominates every hour and minute offset.
    setup_end = day0 + timedelta(minutes=minute_cursor - 1)
    activity_start = setup_end.date() + timedelta(days=1)
    activity_days = (as_of - activity_start).days

    return ClientSetup(
        lines=lines,
        shifts=shifts,
        products=products,
        products_by_id=products_by_id,
        employees=employees,
        line_minute_step=line_minute_step,
        shift_hour_step=shift_hour_step,
        activity_start=activity_start,
        activity_days=activity_days,
    )
