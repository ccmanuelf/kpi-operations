"""Scenario + seed -> ordered event stream. Pure: no database, no clock, no
module-level randomness.

Determinism is the contract. The same (scenarios, profile, seed, as_of)
produces a byte-identical stream, which is what lets the seeded dataset be
asserted against rather than merely eyeballed.

The engine is four modules, and the import edges only ever point one way:

    generator -> emitters_{master,operations} -> narrative -> scenarios

This module owns the stream as a whole -- seq assignment, the global sort, the
as_of clamp -- plus the platform layer and the per-client orchestration. The
emitters own what a band contains; narrative.py owns which distribution a day
draws from.
"""

import hashlib
import random
from dataclasses import fields, replace
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Iterable, List, Sequence, Type

from backend.seed.emitters_capacity import emit_capacity
from backend.seed.emitters_master import emit_setup
from backend.seed.emitters_operations import emit_shifts, emit_work_orders
from backend.seed.events import PLATFORM_CLIENT_ID, ClientAccessGranted, Event, UserCreated
from backend.seed.profiles import Profile
from backend.seed.scenarios import DEMO_PASSWORD, USERS, ClientScenario


def generate(
    scenarios: Sequence[ClientScenario],
    profile: Profile,
    seed: int,
    as_of: date,
) -> List[Event]:
    rng = random.Random(seed)
    start = as_of - timedelta(days=profile.days)
    events: List[Event] = []
    seq = 0

    def emit(cls: Type[Event], at: datetime, client_id: str, **kw: Any) -> None:
        nonlocal seq
        seq += 1
        events.append(cls(at=at, seq=seq, client_id=client_id, **kw))

    known_client_ids = {s.client_id for s in scenarios}
    _generate_platform(emit, start, known_client_ids)

    for scenario in scenarios:
        _generate_client(emit, rng, scenario, profile, start, as_of)

    events.sort(key=lambda e: e.order_key)
    # Clamp to the seeded window: a dataset generated "as of" a date must not
    # contain events after it, or a materialized "current status" taken from
    # the newest transition would report a closure or resume that has not
    # happened yet. Truncation is the realistic outcome anyway -- an order
    # received recently is genuinely mid-flow at as_of, which is exactly how
    # orders end up spread across every status. Clamp AFTER the sort and
    # BEFORE seq renumbering, so seq stays contiguous from 1.
    events = [e for e in events if e.at.date() <= as_of]
    # Re-number so seq reflects final stream position: the materializer relies
    # on insertion order, and active_as_of tie-breaks on it within a second.
    return [replace(e, seq=i + 1) for i, e in enumerate(events)]


def stream_digest(events: Iterable[Event]) -> str:
    """Stable hash of a stream, for asserting determinism without comparing
    thousands of objects.

    Uses dataclasses.fields() rather than vars(e): the latter raises
    TypeError the moment any Event gains slots=True.
    """
    h = hashlib.sha256()
    for e in events:
        h.update(f"{type(e).__name__}|{e.at.isoformat()}|{e.seq}|{e.client_id}".encode())
        for f in sorted(fields(e), key=lambda f: f.name):
            if f.name not in ("at", "seq", "client_id"):
                # repr() escapes special characters to prevent separator-injection
                # collisions where | or = in a field value could imitate a boundary.
                value = repr(getattr(e, f.name))
                h.update(f"|{f.name}={value}".encode())
        h.update(b"\n")  # Record terminator to separate events
    return h.hexdigest()


def _generate_platform(emit: Callable[..., None], start: date, known_client_ids: set[str]) -> None:
    """Users are global. They are emitted BEFORE the per-client loop and
    stamped a day earlier than the earliest client's setup, so every
    ClientAccessGranted and every `entered_by` reference resolves to a user
    already in the stream.

    The grants themselves cannot share that day. A grant names a user AND a
    client, and no client exists until the setup band opens at 06:00 on
    `start` -- stamping them beside the users would put a
    USER_CLIENT_ASSIGNMENT ahead of its own CLIENT row and the materializer,
    inserting in stream order, would hit the FK. So they are stamped one
    minute INTO that band: after every ClientCreated (all clients share the
    06:00 instant), before anything that could depend on a user's scope.

    Grants are also filtered to `known_client_ids` -- the clients THIS
    generate() call is actually producing. The declarative roster grants the
    leader all three DEMO-* clients unconditionally; without this filter, a
    caller asking for a strict subset (a single-client CLI run, say) would
    still get a grant naming a client that was never created, and the
    materializer's insert would hit a foreign key it cannot satisfy --
    reproduced directly against a fresh Alembic-built database before this
    filter existed. Filtering here (rather than only downstream, in a
    particular caller) keeps generate()'s own contract -- a self-consistent
    stream for the scenarios it was given -- true for every caller. No RNG
    draw happens anywhere in this function, so the filter cannot perturb the
    stream; the determinism/digest tests always pass the full scenario list,
    where this filter is a no-op, and stay unchanged.
    """
    platform_at = datetime.combine(start - timedelta(days=1), time(6, 0))
    for i, spec in enumerate(USERS):
        emit(
            UserCreated,
            platform_at + timedelta(minutes=i),
            PLATFORM_CLIENT_ID,
            user_id=spec.user_id,
            username=spec.username,
            role=spec.role,
            email=f"{spec.username}@example.invalid",
            full_name=spec.full_name,
            password=DEMO_PASSWORD,
        )
    grant_at = datetime.combine(start, time(6, 0))
    grant_cursor = 1
    for spec in USERS:
        for cid in spec.client_ids:
            if cid not in known_client_ids:
                continue
            emit(
                ClientAccessGranted,
                grant_at + timedelta(minutes=grant_cursor),
                cid,
                user_id=spec.user_id,
                is_primary=cid == spec.client_ids[0],
            )
            grant_cursor += 1


def _generate_client(
    emit: Callable[..., None],
    rng: random.Random,
    scenario: ClientScenario,
    profile: Profile,
    start: date,
    as_of: date,
) -> None:
    """One client's three bands, in the order the stream needs them.

    Work orders are generated BEFORE the daily shift loop, which is the reverse
    of the original order: a QualityInspected names the work order it inspected
    and a ProductionRecorded names the same one, so the shift loop needs the
    receipts to already exist. Nothing moves in time -- both bands anchor on the
    setup band's activity_start, and generate() sorts the whole stream on
    order_key and renumbers seq afterwards.
    """
    setup = emit_setup(emit, scenario, profile, start, as_of)
    # After setup (it needs the styles and the activity window emit_setup
    # computes) and before operations, so the workbook's master data exists in
    # the stream before anything references it.
    emit_capacity(emit, scenario, profile, setup, as_of)
    received = emit_work_orders(emit, rng, scenario, profile, setup, as_of)
    emit_shifts(emit, rng, scenario, profile, setup, received, as_of)
