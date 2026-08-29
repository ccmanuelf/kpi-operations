"""Typed, immutable events — the interface between the generator and the
materializer.

Every event carries the instant it happened and a monotonic `seq` assigned by
the generator. Ordering is a property of the data, not of a sort's stability:
MariaDB DATETIME stores whole seconds, so two events can share `at`, and the
materializer must insert them in the order they occurred (spec section 12).

Events carry every NOT NULL column of the table(s) they describe -- a
materializer that had to invent a value (an absence, a defect type, a root
cause) would be generating data in the write layer, outside the AST purity
guard and untested by the narrative suite.
"""

from dataclasses import dataclass, fields
from datetime import datetime
from typing import Optional

#: Events not scoped to a tenant (platform users, global thresholds) carry this
#: as `client_id`. It is a stream-level sentinel and must never reach a database
#: client_id column — guarded in tests/test_seed/test_seed_gates.py.
PLATFORM_CLIENT_ID = "__PLATFORM__"


@dataclass(frozen=True)
class Event:
    at: datetime
    seq: int
    client_id: str

    def __post_init__(self) -> None:
        # `date` is not a `datetime`, but `datetime` IS a `date` -- check the
        # narrow type first or every datetime would be rejected.
        if not isinstance(self.at, datetime):
            raise TypeError(f"{type(self).__name__}.at must be a datetime, got {type(self.at).__name__}")
        # Every datetime-valued field, not just `at`: the widened events carry
        # shift_date and required_date, and MariaDB DATETIME rounds a
        # fractional second on any of them across a day boundary.
        for f in fields(self):
            value = getattr(self, f.name)
            if not isinstance(value, datetime):
                continue
            if value.microsecond != 0:
                raise ValueError(
                    f"{type(self).__name__}.{f.name} carries microsecond={value.microsecond}; "
                    "MariaDB DATETIME rounds fractional seconds and would move this event "
                    "across a day boundary"
                )
            if value.tzinfo is not None:
                raise ValueError(f"{type(self).__name__}.{f.name} must be naive UTC, got tzinfo={value.tzinfo}")

    @property
    def order_key(self) -> tuple:
        return (self.at, self.seq)

    def microsecond_free(self) -> bool:
        return all(
            v.microsecond == 0 and v.tzinfo is None
            for v in (getattr(self, f.name) for f in fields(self))
            if isinstance(v, datetime)
        )


# --- Master data -----------------------------------------------------------


@dataclass(frozen=True)
class ClientCreated(Event):
    name: str
    pay_model: str
    client_type: str  # "Piece Rate" | "Hourly Rate" | "Hybrid"


@dataclass(frozen=True)
class UserCreated(Event):
    user_id: str
    username: str
    role: str
    email: str
    full_name: str
    password: str  # plaintext; hashed by the materializer, never stored as-is


@dataclass(frozen=True)
class ClientAccessGranted(Event):
    user_id: str
    is_primary: bool


@dataclass(frozen=True)
class EmployeeHired(Event):
    employee_id: str
    line_id: Optional[str]
    employee_code: str
    employee_name: str
    is_floating_pool: bool


@dataclass(frozen=True)
class LineCommissioned(Event):
    line_id: str
    name: str
    line_code: str
    line_type: str  # "DEDICATED"


@dataclass(frozen=True)
class ShiftDefined(Event):
    shift_id: str
    name: str
    start_hour: int
    end_hour: int


@dataclass(frozen=True)
class ProductDefined(Event):
    product_id: str
    style: str
    product_code: str
    product_name: str
    unit_of_measure: str  # "units"


@dataclass(frozen=True)
class DefectTypeDefined(Event):
    defect_type_id: str
    defect_code: str  # COLOR | FABRIC | MEASURE | STAIN | STITCH
    defect_name: str
    category: str  # VISUAL | MATERIAL | DIMENSIONAL
    severity: str  # MINOR | MAJOR


@dataclass(frozen=True)
class HoldReasonDefined(Event):
    reason_code: str
    display_name: str
    is_default: bool


@dataclass(frozen=True)
class HoldStatusDefined(Event):
    status_code: str
    display_name: str
    is_default: bool


@dataclass(frozen=True)
class ThresholdSet(Event):
    threshold_id: str
    kpi_key: str
    target_value: float


@dataclass(frozen=True)
class ClientConfigured(Event):
    otd_mode: str


# --- Operations --------------------------------------------------------------


@dataclass(frozen=True)
class WorkOrderReceived(Event):
    work_order_id: str
    product_id: str
    planned_quantity: int
    style_model: str
    origin: str  # AD_HOC | CAPACITY_PLAN
    required_date: datetime
    priority: Optional[str]


@dataclass(frozen=True)
class WorkOrderStatusChanged(Event):
    work_order_id: str
    from_status: Optional[str]
    to_status: str
    # Populated only on the step that carries to_status="SHIPPED" -- the
    # generator's lateness draw resolved against required_date, never the
    # bare transition instant, which bears no relation to the customer's
    # commitment date. None on every other step.
    actual_delivery_date: Optional[datetime] = None


@dataclass(frozen=True)
class HoldOpened(Event):
    hold_entry_id: str
    work_order_id: str
    reason_category: str


@dataclass(frozen=True)
class HoldStatusChanged(Event):
    hold_entry_id: str
    from_status: Optional[str]
    to_status: str


@dataclass(frozen=True)
class AttendanceRecorded(Event):
    employee_id: str
    line_id: str
    shift_id: str
    shift_date: datetime
    scheduled_hours: float
    hours_worked: float
    is_absent: bool


@dataclass(frozen=True)
class ProductionRecorded(Event):
    production_entry_id: str
    line_id: str
    shift_id: str
    product_id: str
    work_order_id: Optional[str]
    # The routing step this shift's output is attributed to. Nullable on the
    # column and None here only while no work order has been received yet --
    # there is no job without an order. Load-bearing rather than decorative:
    # PRODUCTION_ENTRY.job_id is the ONLY join five of the six
    # GET /api/jobs/{job_id}/* routes make (they never traverse
    # work_order_id), so an entry that carries the order but not the job is
    # invisible to every one of them.
    job_id: Optional[str]
    shift_date: datetime
    units_produced: int
    run_time_hours: float
    scrap_count: int
    employees_assigned: int
    entered_by: str


@dataclass(frozen=True)
class QualityInspected(Event):
    quality_entry_id: str
    work_order_id: str
    #: Same routing step the shift's ProductionRecorded names -- /ppm, /dpmo
    #: and /kpi-summary read QUALITY_ENTRY by job_id alone.
    job_id: str
    shift_date: datetime
    units_inspected: int
    units_passed: int
    units_defective: int
    total_defects_count: int


@dataclass(frozen=True)
class DefectsFound(Event):
    quality_entry_id: str
    defect_code: str
    defect_count: int


@dataclass(frozen=True)
class JobDefined(Event):
    """One routing step of one work order, as it stands at as_of.

    Carries every NOT NULL column of JOB (work_order_id, client_id via the
    base, operation_name, sequence_number) plus the progress columns the
    /api/jobs/* routes read, for the same reason every other event does: a
    materializer that had to decide how many units an operation finished
    would be generating data in the write layer.

    A single event rather than a Defined/Completed pair: JOB stores a
    snapshot (completed_quantity, is_completed, completed_date), not a
    history -- there is no per-operation transition log to write a second
    event into, and emitting one would invent a sequencing nothing else in
    the dataset supports.
    """

    job_id: str
    work_order_id: str
    operation_code: str
    operation_name: str
    sequence_number: int
    part_number: str
    part_description: str
    planned_quantity: int
    planned_hours: float
    completed_quantity: int
    quantity_scrapped: int
    actual_hours: float
    is_completed: bool
    #: The instant this step finished; None while it has not. Never invented
    #: independently of the order's own chain -- see the emitter.
    completed_date: Optional[datetime]


@dataclass(frozen=True)
class DowntimeLogged(Event):
    line_id: str
    shift_id: str
    shift_date: datetime
    downtime_reason: str
    root_cause_category: str
    downtime_minutes: int


EVENT_TYPES = (
    ClientCreated,
    UserCreated,
    ClientAccessGranted,
    EmployeeHired,
    LineCommissioned,
    ShiftDefined,
    ProductDefined,
    DefectTypeDefined,
    HoldReasonDefined,
    HoldStatusDefined,
    ThresholdSet,
    ClientConfigured,
    WorkOrderReceived,
    WorkOrderStatusChanged,
    HoldOpened,
    HoldStatusChanged,
    AttendanceRecorded,
    ProductionRecorded,
    QualityInspected,
    DefectsFound,
    JobDefined,
    DowntimeLogged,
)
