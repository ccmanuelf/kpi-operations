"""The workforce side: break schedules and the floating pool.

Two tables the shift-configuration and coverage screens read and nothing
wrote. Both are MASTER data -- a break schedule and a pool roster are things a
plant configures once, not events that happen on a day -- so they are emitted
in the setup band alongside the lines and shifts they belong to.

The coverage RECORDS that draw on this pool are emitted from
`emitters_operations`, because only that module knows which employees were
actually absent. A coverage record invented here, against an employee the
attendance stream marked present, would contradict the data it is meant to
explain.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Callable, List, Type

from backend.seed.emitters_master import ClientSetup
from backend.seed.events import BreakTimeDefined, Event, FloatingPoolMemberAdded
from backend.seed.profiles import Profile
from backend.seed.scenarios import ClientScenario

#: Two breaks per shift, stored as offsets from the shift's own start. The
#: unpaid lunch is the longer one, which is what makes a break schedule worth
#: showing rather than a single decorative row.
BREAKS = (
    ("Morning break", 120, 15, "ALL"),
    ("Lunch", 240, 30, "ALL"),
)

#: How many of a client's employees sit in the floating pool. Small on
#: purpose: a pool holding most of the workforce is not a pool, and the
#: coverage screen's whole question is whether the few available people are
#: enough for the day's absences.
POOL_SIZE = 2


def emit_workforce(
    emit: Callable[..., None],
    scenario: ClientScenario,
    profile: Profile,
    setup: ClientSetup,
    as_of: date,
) -> List[str]:
    """Emits break schedules and pool members; returns the pool's employee ids.

    Returned rather than recomputed by the caller: the operations emitter
    needs exactly this list to assign coverage, and deriving "who is floating"
    twice is how the two halves come to disagree.
    """
    cid = scenario.client_id
    stamp = datetime.combine(setup.activity_start - timedelta(days=1), time(21, 0))
    minute = 0

    def declare(cls: Type[Event], **kw: Any) -> None:
        nonlocal minute
        emit(cls, stamp + timedelta(seconds=minute), cid, **kw)
        minute += 1

    for shift_id in setup.shifts:
        for break_name, offset, duration, applies_to in BREAKS:
            declare(
                BreakTimeDefined,
                shift_id=shift_id,
                break_name=break_name,
                start_offset_minutes=offset,
                duration_minutes=duration,
                applies_to=applies_to,
            )

    # The LAST employees of the roster, so the pool does not overlap the crews
    # the line assignments hand to the first ones -- a floater already tied to
    # a line cannot stand in for anyone.
    employee_ids = [employee_id for employee_id, _line in setup.employees]
    pool = employee_ids[-POOL_SIZE:] if len(employee_ids) > POOL_SIZE else employee_ids[:1]

    for employee_id in pool:
        declare(
            FloatingPoolMemberAdded,
            employee_id=employee_id,
            available_from=datetime.combine(setup.activity_start, time(6, 0)),
            # Availability runs past the seed's end so the pool is not
            # "expired" on the day anyone opens the demo.
            available_to=datetime.combine(as_of + timedelta(days=60), time(18, 0)),
            # NULL means available. One member is parked on an assignment so
            # the screen shows both states.
            current_assignment=None if employee_id != pool[0] else cid,
        )

    return list(pool)
