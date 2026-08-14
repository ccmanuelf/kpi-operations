# Seeder Rebuild S1a — Event Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn declarative per-client scenarios into a deterministic, chronologically ordered stream of timestamped events covering twelve months — with no database access whatsoever.

**Architecture:** Four pure modules under `backend/seed/`. `events.py` defines frozen event dataclasses; `profiles.py` and `scenarios.py` hold declarative configuration; `generator.py` expands a scenario plus an RNG seed into an ordered event stream. The stream is the interface S1b's materializer consumes.

**Tech Stack:** Python 3.11 stdlib only — `dataclasses`, `datetime`, `random`, `enum`. No SQLAlchemy, no I/O.

**Spec:** `docs/superpowers/specs/2026-08-13-demo-seeder-rebuild-design.md`

## Global Constraints

- **No database access anywhere in S1a.** These four modules must not import SQLAlchemy, `backend.database`, `backend.orm`, or anything that touches I/O. A static guard test enforces this. The whole point of the split is that the engine is provable without a database.
- **Every timestamp is a `datetime`, never a `date`, and always has `microsecond == 0.`** MariaDB `DATETIME` carries no fractional precision and *rounds* on store, so a `23:59:59.5` event would move to the next day. One second is the finest resolution; nothing may rely on sub-second ordering. (Spec §12.)
- **Events carry an explicit monotonic `seq`.** Within a shared second the stream order is what the materializer preserves, and `active_as_of` tie-breaks on insertion order. Ordering must be a property of the data, not of a sort's stability.
- **Determinism:** the same `(scenario, seed, as_of)` produces a byte-identical stream. Never call `datetime.now()`, `date.today()`, `random.random()` (module-level), or `uuid4()` in these modules — every varying value derives from the seeded `random.Random` instance and the supplied `as_of`.
- **Referential integrity in time:** an event may only reference an entity created by an earlier event in the same stream. This is what lets S1b insert in stream order without FK violations.
- Files stay under 500 lines each.
- Permissive assertions are forbidden: never `assert x in [...]`; assert exactly one expected value.
- Backend tests run as `pytest tests/` from `backend/`. Run them in the FOREGROUND — the Bash tool defaults to a 120s timeout, so pass `timeout: 900000` explicitly for the full suite.
- A test counts as evidence only after you have watched it fail for the reason it exists.

---

### Task 1: Event model

**Files:**
- Create: `backend/seed/__init__.py` (empty)
- Create: `backend/seed/events.py`
- Test: `backend/tests/test_seed/__init__.py` (empty), `backend/tests/test_seed/test_events.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Event` base with fields `at: datetime`, `seq: int`, `client_id: str` and property `order_key -> tuple[datetime, int]`; subclasses `ClientCreated`, `UserCreated`, `EmployeeHired`, `LineCommissioned`, `ShiftDefined`, `ProductDefined`, `WorkOrderReceived`, `WorkOrderStatusChanged`, `HoldOpened`, `HoldStatusChanged`, `ShiftWorked`; and `EVENT_TYPES: tuple[type[Event], ...]`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_seed/test_events.py`:

```python
import dataclasses
from datetime import datetime

import pytest

from backend.seed.events import (
    EVENT_TYPES,
    Event,
    HoldOpened,
    ShiftWorked,
    WorkOrderReceived,
)


def _evt(**kw):
    base = dict(at=datetime(2026, 3, 1, 6, 0, 0), seq=1, client_id="DEMO-PIECE")
    base.update(kw)
    return base


def test_events_are_frozen():
    e = WorkOrderReceived(**_evt(), work_order_id="WO-1", product_id="P-1", planned_quantity=100)
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.seq = 2


def test_order_key_is_at_then_seq():
    a = WorkOrderReceived(**_evt(seq=1), work_order_id="WO-1", product_id="P-1", planned_quantity=1)
    b = WorkOrderReceived(**_evt(seq=2), work_order_id="WO-2", product_id="P-1", planned_quantity=1)

    assert a.order_key < b.order_key


def test_microsecond_bearing_timestamp_is_rejected():
    """MariaDB DATETIME rounds fractional seconds, which would move an event
    across a day boundary. The model refuses them rather than letting the
    materializer discover it."""
    with pytest.raises(ValueError) as exc:
        HoldOpened(
            at=datetime(2026, 3, 1, 23, 59, 59, 500000),
            seq=1,
            client_id="DEMO-PIECE",
            hold_entry_id="H-1",
            work_order_id="WO-1",
            reason_category="QUALITY",
        )

    assert "microsecond" in str(exc.value)


def test_date_instead_of_datetime_is_rejected():
    """PR-C1's recorder calls .replace(microsecond=0) and raises on a bare
    date; the seeder is the caller that can reach that path (spec section 12)."""
    from datetime import date

    with pytest.raises(TypeError):
        ShiftWorked(
            at=date(2026, 3, 1),
            seq=1,
            client_id="DEMO-PIECE",
            line_id="L-1",
            shift_id="S-1",
            units_produced=10,
            units_defective=0,
            downtime_minutes=0,
            attendance_headcount=8,
        )


def test_every_event_type_subclasses_event_and_is_registered():
    for t in EVENT_TYPES:
        assert issubclass(t, Event)
    assert len(EVENT_TYPES) == len(set(EVENT_TYPES))
```

- [ ] **Step 2: Run them and watch them fail**

Run: `pytest tests/test_seed/test_events.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.seed'`. Paste the output into your report.

- [ ] **Step 3: Write the event model**

`backend/seed/events.py`. Validation lives in `__post_init__` on the base so every subclass inherits it:

```python
"""Typed, immutable events — the interface between the generator and the
materializer.

Every event carries the instant it happened and a monotonic `seq` assigned by
the generator. Ordering is a property of the data, not of a sort's stability:
MariaDB DATETIME stores whole seconds, so two events can share `at`, and the
materializer must insert them in the order they occurred (spec section 12).
"""

from dataclasses import dataclass
from datetime import date, datetime
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
```

Note `date` is imported solely for the reader's benefit in the type check comment; if flake8 flags it as unused, remove the import and keep the comment.

- [ ] **Step 4: Verify they pass**

Run: `pytest tests/test_seed/test_events.py -v`
Expected: 5 passed.

- [ ] **Step 5: Prove the two rejection tests are not vacuous**

Delete the `microsecond` check, confirm `test_microsecond_bearing_timestamp_is_rejected` fails, restore. Then delete the `isinstance` check, confirm `test_date_instead_of_datetime_is_rejected` fails, restore. Paste both outputs.

Note the ordering trap: with the `isinstance` check removed, a `date` reaches `self.at.microsecond` and raises `AttributeError`, not the `TypeError` the test expects — so the test still fails, but read the failure and confirm it fails for a sane reason.

- [ ] **Step 6: Commit**

```bash
git add backend/seed/ backend/tests/test_seed/
git commit -m "feat(seed): typed immutable event model with whole-second validation"
```

---

### Task 2: Profiles and scenarios

**Files:**
- Create: `backend/seed/profiles.py`
- Create: `backend/seed/scenarios.py`
- Test: `backend/tests/test_seed/test_scenarios.py`

**Interfaces:**
- Consumes: nothing from Task 1 (pure configuration).
- Produces:
  - `Profile` frozen dataclass with `name: str`, `days: int`, `lines_per_client: int`, `shifts_per_client: int`, `employees_per_client: int`, `work_orders_per_client: int`.
  - `FULL: Profile` (365 days) and `SMOKE: Profile` (14 days), plus `PROFILES: dict[str, Profile]`.
  - `NarrativeWindow` frozen dataclass with `kind: str`, `start_month: int`, `end_month: int` (negative month offsets from `as_of`).
  - `ClientScenario` frozen dataclass with `client_id: str`, `name: str`, `pay_model: str`, `narrative: tuple[NarrativeWindow, ...]`.
  - `SCENARIOS: tuple[ClientScenario, ...]` — the four clients from spec §6.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_seed/test_scenarios.py`:

```python
from backend.seed.profiles import FULL, PROFILES, SMOKE
from backend.seed.scenarios import SCENARIOS, ClientScenario


def test_full_profile_covers_twelve_months():
    assert FULL.days == 365


def test_smoke_profile_is_short_enough_for_tests():
    assert SMOKE.days == 14


def test_profiles_are_registered_by_name():
    assert PROFILES["full"] is FULL
    assert PROFILES["smoke"] is SMOKE


def test_four_clients_matching_the_spec():
    assert len(SCENARIOS) == 4
    assert tuple(s.client_id for s in SCENARIOS) == (
        "DEMO-PIECE",
        "DEMO-HOURLY",
        "DEMO-HYBRID",
        "SAMPLE_REF",
    )


def test_pay_models_are_distinct_where_the_spec_says_so():
    by_id = {s.client_id: s for s in SCENARIOS}
    assert by_id["DEMO-PIECE"].pay_model == "piece"
    assert by_id["DEMO-HOURLY"].pay_model == "hourly"
    assert by_id["DEMO-HYBRID"].pay_model == "hybrid"


def test_sample_ref_is_the_healthy_control():
    """Without a client whose metrics stay in specification, every dashboard
    reads red and thresholds look broken rather than informative."""
    by_id = {s.client_id: s for s in SCENARIOS}
    assert by_id["SAMPLE_REF"].narrative == ()


def test_each_troubled_client_has_exactly_one_narrative_window():
    for scenario in SCENARIOS:
        if scenario.client_id == "SAMPLE_REF":
            continue
        assert len(scenario.narrative) == 1


def test_narrative_windows_are_ordered_and_in_the_past():
    for scenario in SCENARIOS:
        for w in scenario.narrative:
            assert w.start_month < 0
            assert w.start_month < w.end_month


def test_scenarios_are_immutable():
    import dataclasses
    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        SCENARIOS[0].client_id = "X"
```

- [ ] **Step 2: Run them and watch them fail**

Run: `pytest tests/test_seed/test_scenarios.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.seed.profiles'`.

- [ ] **Step 3: Write `profiles.py`**

```python
"""Dataset size presets. `full` is what the VM and Render seed; `smoke` is a
short window so tests exercise the same code path in seconds.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    days: int
    lines_per_client: int
    shifts_per_client: int
    employees_per_client: int
    work_orders_per_client: int


# 365 days x 4 clients x 2 lines x 2 shifts is the density the pivot layer
# needs for twelve genuine monthly buckets (spec sections 2 and 13).
FULL = Profile(
    name="full",
    days=365,
    lines_per_client=2,
    shifts_per_client=2,
    employees_per_client=8,
    work_orders_per_client=100,
)

SMOKE = Profile(
    name="smoke",
    days=14,
    lines_per_client=2,
    shifts_per_client=2,
    employees_per_client=4,
    work_orders_per_client=6,
)

PROFILES = {p.name: p for p in (FULL, SMOKE)}
```

- [ ] **Step 4: Write `scenarios.py`**

```python
"""Declarative per-client scenarios: who exists, and what story their data
tells. Pure configuration -- no generation logic, no database.

Four clients, each demonstrating a different failure mode, plus one healthy
control so the dashboards are not uniformly red (spec section 6).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NarrativeWindow:
    """A scripted episode. Months are negative offsets from the seed's as-of
    date: start_month=-8, end_month=-6 means "eight to six months ago"."""

    kind: str
    start_month: int
    end_month: int


@dataclass(frozen=True)
class ClientScenario:
    client_id: str
    name: str
    pay_model: str
    narrative: tuple


SCENARIOS = (
    ClientScenario(
        client_id="DEMO-PIECE",
        name="Piecework Apparel Co.",
        pay_model="piece",
        narrative=(NarrativeWindow(kind="supplier_quality_crisis", start_month=-8, end_month=-6),),
    ),
    ClientScenario(
        client_id="DEMO-HOURLY",
        name="Hourly Components Ltd.",
        pay_model="hourly",
        narrative=(NarrativeWindow(kind="equipment_reliability_decline", start_month=-5, end_month=-3),),
    ),
    ClientScenario(
        client_id="DEMO-HYBRID",
        name="Hybrid Assembly Group",
        pay_model="hybrid",
        narrative=(NarrativeWindow(kind="labor_disruption", start_month=-4, end_month=-2),),
    ),
    # The control. Every metric stays in specification for the full year, so a
    # demo can show a healthy client beside three troubled ones and the
    # thresholds read as informative rather than broken.
    ClientScenario(
        client_id="SAMPLE_REF",
        name="Reference Manufacturing",
        pay_model="hourly",
        narrative=(),
    ),
)
```

- [ ] **Step 5: Verify they pass**

Run: `pytest tests/test_seed/test_scenarios.py -v`
Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/seed/profiles.py backend/seed/scenarios.py backend/tests/test_seed/test_scenarios.py
git commit -m "feat(seed): profiles and four-client scenario declarations"
```

---

### Task 3: Generator — deterministic baseline stream

**Files:**
- Create: `backend/seed/generator.py`
- Modify: `backend/seed/events.py` (add the `microsecond_free()` helper below)
- Test: `backend/tests/test_seed/test_generator.py`

**Interfaces:**
- Consumes: `Event` subclasses (Task 1); `Profile`, `ClientScenario`, `SCENARIOS` (Task 2).
- Produces: `generate(scenarios, profile, seed: int, as_of: date) -> list[Event]`, and `stream_digest(events) -> str` (a stable hash used to assert determinism).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_seed/test_generator.py`:

```python
from datetime import date, datetime

from backend.seed.events import (
    ClientCreated,
    EmployeeHired,
    Event,
    HoldOpened,
    HoldStatusChanged,
    ShiftWorked,
    WorkOrderReceived,
    WorkOrderStatusChanged,
)
from backend.seed.generator import generate, stream_digest
from backend.seed.profiles import SMOKE
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 14)


def _gen(seed=1234):
    return generate(SCENARIOS, SMOKE, seed=seed, as_of=AS_OF)


def test_same_inputs_produce_an_identical_stream():
    assert stream_digest(_gen()) == stream_digest(_gen())


def test_a_different_seed_produces_a_different_stream():
    """Guards against a generator that ignores its seed and returns a
    constant, which would make the determinism test above vacuous."""
    assert stream_digest(_gen(seed=1234)) != stream_digest(_gen(seed=5678))


def test_stream_is_ordered_by_at_then_seq():
    events = _gen()
    assert events == sorted(events, key=lambda e: e.order_key)


def test_seq_is_strictly_increasing_across_the_whole_stream():
    """Ties within a second must be resolved by data, not by sort stability."""
    seqs = [e.seq for e in _gen()]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


def test_every_timestamp_is_whole_seconds_and_naive():
    for e in _gen():
        assert e.microsecond_free()


def test_no_event_precedes_its_client_creation():
    """Referential integrity in time: the materializer inserts in stream order
    and would hit an FK violation otherwise."""
    created_at = {}
    for e in _gen():
        if isinstance(e, ClientCreated):
            created_at[e.client_id] = e.order_key
        else:
            assert e.client_id in created_at
            assert created_at[e.client_id] < e.order_key


def test_work_order_events_follow_the_work_order_receipt():
    seen = set()
    for e in _gen():
        if isinstance(e, WorkOrderReceived):
            seen.add(e.work_order_id)
        elif isinstance(e, WorkOrderStatusChanged):
            assert e.work_order_id in seen
        elif isinstance(e, HoldOpened):
            assert e.work_order_id in seen


def test_every_work_order_gets_an_opening_status_row():
    """The gap that made the old seeder's transition log unusable: 60 of 100
    orders had no chain at all."""
    received = {e.work_order_id for e in _gen() if isinstance(e, WorkOrderReceived)}
    opened = {
        e.work_order_id
        for e in _gen()
        if isinstance(e, WorkOrderStatusChanged) and e.from_status is None
    }
    assert received == opened


def test_transition_timestamps_are_distinct_per_work_order():
    """The other half of that defect: all 40 chains shared one instant, so
    status intervals were zero-length and unanswerable."""
    per_order = {}
    for e in _gen():
        if isinstance(e, WorkOrderStatusChanged):
            per_order.setdefault(e.work_order_id, []).append(e.at)
    multi = {k: v for k, v in per_order.items() if len(v) > 1}
    assert multi, "fixture produced no multi-transition orders; the assertion below would be vacuous"
    for wo, times in multi.items():
        assert len(set(times)) == len(times), f"{wo} has duplicate transition instants"


def test_hold_status_changes_follow_their_hold():
    opened = set()
    for e in _gen():
        if isinstance(e, HoldOpened):
            opened.add(e.hold_entry_id)
        elif isinstance(e, HoldStatusChanged):
            assert e.hold_entry_id in opened


def test_shift_events_cover_the_profile_window():
    days = {e.at.date() for e in _gen() if isinstance(e, ShiftWorked)}
    assert len(days) >= SMOKE.days - 4  # weekends excluded


def test_each_client_gets_its_declared_employee_count():
    per_client = {}
    for e in _gen():
        if isinstance(e, EmployeeHired):
            per_client[e.client_id] = per_client.get(e.client_id, 0) + 1
    for scenario in SCENARIOS:
        assert per_client[scenario.client_id] == SMOKE.employees_per_client
```

Add `microsecond_free()` to `Event` in `backend/seed/events.py` as part of this task — a one-line helper the test above reads better with:

```python
    def microsecond_free(self) -> bool:
        return self.at.microsecond == 0 and self.at.tzinfo is None
```

- [ ] **Step 2: Run them and watch them fail**

Run: `pytest tests/test_seed/test_generator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.seed.generator'`. Paste the output.

- [ ] **Step 3: Write the generator**

`backend/seed/generator.py`. The shape below is the contract; fill in the per-client body so the tests above pass. Key rules:

- One `random.Random(seed)` instance created at the top of `generate`, threaded through. Never the module-level `random` functions.
- A single `_seq` counter incremented on every emit, so `seq` is unique and monotonic across the whole stream.
- Build the list, then `sort(key=lambda e: e.order_key)` and re-assign `seq` in final order, so `seq` reflects stream position rather than emission order.
- Timestamps: `datetime.combine(day, time(hour, minute))` — never `datetime.now()`.

```python
"""Scenario + seed -> ordered event stream. Pure: no database, no clock, no
module-level randomness.

Determinism is the contract. The same (scenarios, profile, seed, as_of)
produces a byte-identical stream, which is what lets the seeded dataset be
asserted against rather than merely eyeballed.
"""

import hashlib
import random
from dataclasses import replace
from datetime import date, datetime, time, timedelta
from typing import Iterable, List, Sequence

from backend.seed.events import (
    ClientCreated,
    EmployeeHired,
    Event,
    HoldOpened,
    HoldStatusChanged,
    LineCommissioned,
    ProductDefined,
    ShiftDefined,
    ShiftWorked,
    UserCreated,
    WorkOrderReceived,
    WorkOrderStatusChanged,
)
from backend.seed.profiles import Profile
from backend.seed.scenarios import ClientScenario

# Mainline work-order lifecycle. Every order walks a prefix of this.
WORK_ORDER_FLOW = ("RECEIVED", "RELEASED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "CLOSED")

HOLD_FLOW = ("PENDING_HOLD_APPROVAL", "ON_HOLD", "PENDING_RESUME_APPROVAL", "RESUMED")


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

    def emit(cls, at: datetime, client_id: str, **kw) -> None:
        nonlocal seq
        seq += 1
        events.append(cls(at=at, seq=seq, client_id=client_id, **kw))

    for scenario in scenarios:
        _generate_client(emit, rng, scenario, profile, start, as_of)

    events.sort(key=lambda e: e.order_key)
    # Re-number so seq reflects final stream position: the materializer relies
    # on insertion order, and active_as_of tie-breaks on it within a second.
    return [replace(e, seq=i + 1) for i, e in enumerate(events)]


def stream_digest(events: Iterable[Event]) -> str:
    """Stable hash of a stream, for asserting determinism without comparing
    thousands of objects."""
    h = hashlib.sha256()
    for e in events:
        h.update(f"{type(e).__name__}|{e.at.isoformat()}|{e.seq}|{e.client_id}".encode())
        for field, value in sorted(vars(e).items()):
            if field not in ("at", "seq", "client_id"):
                h.update(f"|{field}={value}".encode())
    return h.hexdigest()
```

And `_generate_client` in full. Entity ids are deterministic (client + index), never `uuid4()`:

```python
def _generate_client(emit, rng, scenario, profile, start, as_of) -> None:
    cid = scenario.client_id

    # --- setup, all on the first day, minutes apart so order is unambiguous
    day0 = datetime.combine(start, time(6, 0))
    emit(ClientCreated, day0, cid, name=scenario.name, pay_model=scenario.pay_model)
    emit(UserCreated, day0 + timedelta(minutes=1), cid,
         user_id=f"{cid}-USR-001", username=f"{cid.lower()}_supervisor", role="supervisor")

    lines = [f"{cid}-LINE-{i:02d}" for i in range(1, profile.lines_per_client + 1)]
    for i, line_id in enumerate(lines):
        emit(LineCommissioned, day0 + timedelta(minutes=2 + i), cid,
             line_id=line_id, name=f"Line {i + 1}")

    shifts = [f"{cid}-SHIFT-{i:02d}" for i in range(1, profile.shifts_per_client + 1)]
    for i, shift_id in enumerate(shifts):
        emit(ShiftDefined, day0 + timedelta(minutes=10 + i), cid,
             shift_id=shift_id, name=f"Shift {i + 1}", start_hour=6 + i * 8)

    products = [f"{cid}-PROD-{i:02d}" for i in range(1, 4)]
    for i, product_id in enumerate(products):
        emit(ProductDefined, day0 + timedelta(minutes=20 + i), cid,
             product_id=product_id, style=f"STYLE-{i + 1}")

    for i in range(profile.employees_per_client):
        emit(EmployeeHired, day0 + timedelta(minutes=30 + i), cid,
             employee_id=f"{cid}-EMP-{i + 1:03d}", line_id=lines[i % len(lines)])

    # --- daily shift activity, Mon-Fri only
    for offset in range(profile.days):
        day = start + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        scale = _narrative_scale(scenario, day, as_of)
        for li, line_id in enumerate(lines):
            for si, shift_id in enumerate(shifts):
                produced = rng.randint(180, 260)
                defect_rate = rng.uniform(0.01, 0.03) * scale["defects"]
                emit(
                    ShiftWorked,
                    datetime.combine(day, time(6 + si * 8, 30 + li)),
                    cid,
                    line_id=line_id,
                    shift_id=shift_id,
                    units_produced=produced,
                    units_defective=int(produced * defect_rate),
                    downtime_minutes=int(rng.randint(5, 40) * scale["downtime"]),
                    attendance_headcount=max(
                        1, int(profile.employees_per_client / len(lines) * scale["attendance"])
                    ),
                )

    # --- work orders spread across the window, each with a real chain
    span = max(1, profile.days - 10)
    for i in range(profile.work_orders_per_client):
        wo = f"{cid}-WO-{i + 1:04d}"
        opened = start + timedelta(days=rng.randrange(span))
        emit(WorkOrderReceived, datetime.combine(opened, time(7, 0)), cid,
             work_order_id=wo, product_id=products[i % len(products)],
             planned_quantity=rng.choice([250, 500, 750, 1000]))

        # How far along the flow this order has travelled. Every order emits
        # the opening (from_status=None) row -- the gap that left 60 of 100
        # orders with no chain at all in the old seeder.
        depth = rng.randint(1, len(WORK_ORDER_FLOW))
        prev = None
        when = opened
        for step in WORK_ORDER_FLOW[:depth]:
            emit(WorkOrderStatusChanged, datetime.combine(when, time(8, 0)), cid,
                 work_order_id=wo, from_status=prev, to_status=step)
            prev = step
            # Distinct DAY per transition: same-day steps would collapse the
            # interval this whole project exists to make answerable.
            when = when + timedelta(days=rng.randint(1, 4))

        if rng.random() < _hold_rate(scenario, opened, as_of):
            hold_id = f"{cid}-HOLD-{i + 1:04d}"
            hold_day = opened + timedelta(days=rng.randint(1, 5))
            emit(HoldOpened, datetime.combine(hold_day, time(9, 0)), cid,
                 hold_entry_id=hold_id, work_order_id=wo,
                 reason_category=rng.choice(["QUALITY", "MATERIAL", "ENGINEERING"]))
            prev_h = None
            hwhen = hold_day
            for step in HOLD_FLOW[: rng.randint(1, len(HOLD_FLOW))]:
                emit(HoldStatusChanged, datetime.combine(hwhen, time(10, 0)), cid,
                     hold_entry_id=hold_id, from_status=prev_h, to_status=step)
                prev_h = step
                hwhen = hwhen + timedelta(days=rng.randint(2, 15))
```

`_narrative_scale` returns `{"defects": 1.0, "downtime": 1.0, "attendance": 1.0}` for now — Task 4 gives it real behaviour. `_hold_rate` returns a flat `0.15` for now, likewise raised inside a quality window in Task 4. Write both as stubs returning those constants so Task 3's tests pass, and note in a comment that Task 4 fills them in.

- [ ] **Step 4: Verify they pass**

Run: `pytest tests/test_seed/test_generator.py -v`
Expected: 12 passed.

- [ ] **Step 5: Prove determinism is not vacuous**

`test_a_different_seed_produces_a_different_stream` is the guard: a generator that ignored its seed would satisfy the determinism test trivially. Confirm it passes, then temporarily hard-code `rng = random.Random(0)`, watch that test fail, and restore. Paste the output.

- [ ] **Step 6: Commit**

```bash
git add backend/seed/generator.py backend/seed/events.py backend/tests/test_seed/test_generator.py
git commit -m "feat(seed): deterministic baseline event-stream generator"
```

---

### Task 4: Narrative injection and the purity guard

**Files:**
- Modify: `backend/seed/generator.py`
- Test: `backend/tests/test_seed/test_narrative.py`, `backend/tests/test_seed/test_purity.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `generate` additionally honours `ClientScenario.narrative`; no signature change.

- [ ] **Step 1: Write the narrative tests**

`backend/tests/test_seed/test_narrative.py`:

```python
from datetime import date, timedelta

import pytest

from backend.seed.events import HoldOpened, ShiftWorked
from backend.seed.generator import generate
from backend.seed.profiles import FULL
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 14)


@pytest.fixture(scope="module")
def events():
    """Module-scoped: the FULL profile is ~50k events and every test here
    needs the same stream. Regenerating per test would dominate the suite."""
    return generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF)


def _window(lo_months, hi_months):
    """Calendar bounds for a month-offset window. Offsets are negative, so the
    EARLIER bound comes from the LARGER absolute value -- getting this backwards
    yields an empty range that silently matches nothing and makes every
    assertion below vacuous."""
    earlier = AS_OF - timedelta(days=abs(lo_months) * 30)
    later = AS_OF - timedelta(days=abs(hi_months) * 30)
    assert earlier < later
    return earlier, later


def _shift_events(events, client_id, lo, hi):
    earlier, later = _window(lo, hi)
    rows = [
        e
        for e in events
        if isinstance(e, ShiftWorked) and e.client_id == client_id and earlier <= e.at.date() <= later
    ]
    assert rows, f"no ShiftWorked rows for {client_id} in [{earlier}, {later}] — assertion would be vacuous"
    return rows


def _defect_rate(events, client_id, lo, hi):
    rows = _shift_events(events, client_id, lo, hi)
    produced = sum(r.units_produced for r in rows)
    defective = sum(r.units_defective for r in rows)
    return defective / produced if produced else 0.0


def test_supplier_quality_crisis_lifts_demo_piece_defect_rate(events):
    """The scripted episode must be visible in the data, or the Q3 view has
    nothing to show and the DHU derivation cannot be demoed."""
    crisis = _defect_rate(events, "DEMO-PIECE", -8, -6)
    baseline = _defect_rate(events, "DEMO-PIECE", -3, -1)

    assert crisis > baseline * 1.5


def test_equipment_decline_lifts_demo_hourly_downtime(events):
    crisis = sum(r.downtime_minutes for r in _shift_events(events, "DEMO-HOURLY", -5, -3))
    baseline = sum(r.downtime_minutes for r in _shift_events(events, "DEMO-HOURLY", -2, -1))

    # Windows differ in length, so compare per-shift averages, not totals.
    crisis_avg = crisis / len(_shift_events(events, "DEMO-HOURLY", -5, -3))
    baseline_avg = baseline / len(_shift_events(events, "DEMO-HOURLY", -2, -1))
    assert crisis_avg > baseline_avg * 1.5


def test_labor_disruption_drops_demo_hybrid_attendance(events):
    def avg_headcount(lo, hi):
        rows = _shift_events(events, "DEMO-HYBRID", lo, hi)
        return sum(r.attendance_headcount for r in rows) / len(rows)

    assert avg_headcount(-4, -2) < avg_headcount(-2, -1)


def test_sample_ref_has_no_episode(events):
    """The control client must stay in specification all year, so a demo can
    show one healthy client beside three troubled ones."""
    early = _defect_rate(events, "SAMPLE_REF", -10, -8)
    late = _defect_rate(events, "SAMPLE_REF", -3, -1)

    assert abs(early - late) < 0.02


def test_demo_piece_accumulates_holds_in_its_window(events):
    earlier, later = _window(-8, -6)
    holds = [
        e
        for e in events
        if isinstance(e, HoldOpened) and e.client_id == "DEMO-PIECE" and earlier <= e.at.date() <= later
    ]
    assert len(holds) >= 3
```

- [ ] **Step 2: Write the purity guard**

`backend/tests/test_seed/test_purity.py`:

```python
import ast
import pathlib

FORBIDDEN_IMPORTS = ("sqlalchemy", "backend.database", "backend.orm", "backend.crud")
FORBIDDEN_CALLS = ("now", "today", "utcnow", "uuid4")

SEED_DIR = pathlib.Path(__file__).resolve().parents[2] / "seed"
ENGINE_MODULES = ("events.py", "scenarios.py", "profiles.py", "generator.py")


def _tree(name):
    return ast.parse((SEED_DIR / name).read_text())


def test_engine_modules_import_no_database_machinery():
    """S1a's whole premise is that the engine is provable without a database.
    An import here would silently make that false."""
    offenders = []
    for name in ENGINE_MODULES:
        for node in ast.walk(_tree(name)):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            for m in mods:
                if any(m == f or m.startswith(f + ".") for f in FORBIDDEN_IMPORTS):
                    offenders.append(f"{name}: {m}")
    assert offenders == []


def test_engine_modules_never_read_the_clock_or_generate_uuids():
    """Determinism is the contract: every varying value must derive from the
    seeded RNG and the supplied as_of, never from ambient state."""
    offenders = []
    for name in ENGINE_MODULES:
        for node in ast.walk(_tree(name)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in FORBIDDEN_CALLS:
                    offenders.append(f"{name}: {node.func.attr}()")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in FORBIDDEN_CALLS:
                    offenders.append(f"{name}: {node.func.id}()")
    assert offenders == []
```

- [ ] **Step 3: Run both and watch the narrative tests fail**

Run: `pytest tests/test_seed/test_narrative.py tests/test_seed/test_purity.py -v`
Expected: the purity tests PASS already (Task 3 wrote clean modules); the narrative tests FAIL on their assertions, because Task 3's generator produces a flat baseline with no episodes. Paste the narrative failures — an assertion failure here is the evidence; an import error is not.

- [ ] **Step 4: Implement narrative injection**

In `_generate_client`, before emitting each `ShiftWorked`, check whether the day falls inside any `NarrativeWindow` for that client and scale the drawn values accordingly:

- `supplier_quality_crisis` — multiply `units_defective` by roughly 3, and open additional `HoldOpened` events with `reason_category="QUALITY"` at a raised rate.
- `equipment_reliability_decline` — multiply `downtime_minutes` by roughly 3.
- `labor_disruption` — reduce `attendance_headcount` by roughly a third.

Keep the statistical baseline underneath: draw from the RNG as before and scale, so days inside a window still differ from each other. A window that sets a constant would make every day identical and read as synthetic.

Resolve a window's calendar bounds from `as_of` and the month offsets with `timedelta(days=abs(month) * 30)`, matching the tests.

- [ ] **Step 5: Verify everything passes**

Run: `pytest tests/test_seed/ -v`
Expected: all pass — events, scenarios, generator, narrative, purity.

- [ ] **Step 6: Prove the purity guard is not vacuous**

Temporarily add `from sqlalchemy import select` to `generator.py`; confirm `test_engine_modules_import_no_database_machinery` fails and names it. Then temporarily add `datetime.now()`; confirm the clock test fails. Restore both. Paste both outputs — a guard never observed failing is not a guard.

- [ ] **Step 7: Run the full suite**

Run: `pytest tests/` (foreground, explicit long timeout)
Expected: green, coverage ≥ 75%.

- [ ] **Step 8: Commit**

```bash
git add backend/seed/generator.py backend/tests/test_seed/
git commit -m "feat(seed): narrative injection + engine purity guards"
```

---

## Verification before opening the PR

- [ ] `pytest tests/` green from `backend/`, coverage ≥ 75%
- [ ] `pytest tests/test_seed/ -v` green
- [ ] `pre-commit run --files <changed files>` clean — note `pre-commit run --all-files` rewrites ~94 unrelated pre-existing files in this repo, so scope it
- [ ] No module under `backend/seed/` imports SQLAlchemy or reads the clock (asserted by `test_purity.py`)
- [ ] `/cross-review` run for the final HEAD — run `git checkout` as its **own** command before marking, never chained with `&&`
