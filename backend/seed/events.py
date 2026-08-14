"""Typed, immutable events — the interface between the generator and the
materializer.

Every event carries the instant it happened and a monotonic `seq` assigned by
the generator. Ordering is a property of the data, not of a sort's stability:
MariaDB DATETIME stores whole seconds, so two events can share `at`, and the
materializer must insert them in the order they occurred (spec section 12).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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
        if self.at.microsecond != 0:
            raise ValueError(
                f"{type(self).__name__}.at carries microsecond={self.at.microsecond}; "
                "MariaDB DATETIME rounds fractional seconds and would move this event "
                "across a day boundary"
            )
        if self.at.tzinfo is not None:
            raise ValueError(f"{type(self).__name__}.at must be naive UTC, got tzinfo={self.at.tzinfo}")

    @property
    def order_key(self) -> tuple:
        return (self.at, self.seq)


@dataclass(frozen=True)
class ClientCreated(Event):
    name: str
    pay_model: str


@dataclass(frozen=True)
class UserCreated(Event):
    user_id: str
    username: str
    role: str


@dataclass(frozen=True)
class EmployeeHired(Event):
    employee_id: str
    line_id: Optional[str]


@dataclass(frozen=True)
class LineCommissioned(Event):
    line_id: str
    name: str


@dataclass(frozen=True)
class ShiftDefined(Event):
    shift_id: str
    name: str
    start_hour: int


@dataclass(frozen=True)
class ProductDefined(Event):
    product_id: str
    style: str


@dataclass(frozen=True)
class WorkOrderReceived(Event):
    work_order_id: str
    product_id: str
    planned_quantity: int


@dataclass(frozen=True)
class WorkOrderStatusChanged(Event):
    work_order_id: str
    from_status: Optional[str]
    to_status: str


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
class ShiftWorked(Event):
    line_id: str
    shift_id: str
    units_produced: int
    units_defective: int
    downtime_minutes: int
    attendance_headcount: int


EVENT_TYPES = (
    ClientCreated,
    UserCreated,
    EmployeeHired,
    LineCommissioned,
    ShiftDefined,
    ProductDefined,
    WorkOrderReceived,
    WorkOrderStatusChanged,
    HoldOpened,
    HoldStatusChanged,
    ShiftWorked,
)
