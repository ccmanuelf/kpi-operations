# Seeder Rebuild S1b — Materializer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn S1a's event stream into a real database — widened events that can express every NOT NULL column of the tables they describe, and a materializer that writes them as SQLAlchemy Core bulk inserts with every timestamp taken from its event.

**Architecture:** The stream stays the interface. `events.py` widens (one `ShiftWorked` becomes five events, because one shift produces rows in five tables and *N* per-employee attendance rows it does not currently describe). `generator.py` emits the widened stream. `identity.py` maps stable event keys to database primary keys — four master tables use autoincrement integers while the stream uses string business keys, so the materializer allocates and remembers them. `materialize.py` walks the stream, hands rows to domain writers, and flushes them table-by-table in `Base.metadata.sorted_tables` order, preserving stream order within each table's batch. `coverage.py` declares what is seeded; `cli.py` is the entry point.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x Core (`insert()` executemany), pytest. No ORM `add()` on the write path.

**Spec:** `docs/superpowers/specs/2026-08-13-demo-seeder-rebuild-design.md`

**Predecessor:** `docs/superpowers/plans/2026-08-14-seeder-rebuild-s1a-engine.md` (merged as #202, `90ad9c5`)

---

## Scope decision: S1b builds, S1c cuts over

Spec §11 scopes "S1" as one PR: engine, materializer, boot repoint, and retirement of the old seeder. S1a already split the engine out. **This plan takes the second half and splits it again, at the cutover seam.**

- **S1b (this plan)** — everything additive. The new seeder is built, tested on both dialects, and runnable by hand. `backend/scripts/init_demo_database.py` still runs on boot; nothing in production, CI, or deploy changes behaviour. Verifiable on its own terms: it either produces monotonic transition chains and a catalog-valid defect taxonomy for every client, or it does not.
- **S1c (next plan, written after S1b merges)** — pure cutover: repoint `bootstrap/lifecycle.py`, `scripts/deploy.sh`, `.github/workflows/ci.yml`, `deploy/smoke/compose-smoke.sh`, and the e2e credentials; rewrite `test_demo_seed_gate.py` and `test_audit/test_suppression_sites.py` against the new entry point; delete 3,043 lines of old seeder.

**Why the seam is here.** The two halves fail in different ways. S1b's risk is *data* — a missing column, a collapsed timestamp, an unjoinable defect code — and it is caught by tests against a database. S1c's risk is *blast radius*: the demo client IDs change from `ACME-MFG / TEXTILE-PRO / FASHION-WORKS / QUALITY-STITCH / GLOBAL-APPAREL` to `DEMO-PIECE / DEMO-HOURLY / DEMO-HYBRID / SAMPLE_REF`, and the login credentials change with them. That single fact reaches `ci.yml`'s e2e smoke URLs, `compose-smoke.sh`'s `CLIENT_ID` default, four Playwright specs, and `lifecycle.py`'s `EXPECTED_CLIENTS` set — and if `EXPECTED_CLIENTS` is missed, every boot decides demo data is incomplete and calls the **destructive** `rebuild_schema()`, in a loop. Bundled together, a revert of the cutover would also revert the engine. Split, each PR reverts cleanly.

This is a recommendation, not a settled ruling. Merging the two plans back into one PR is a one-line decision — say so and the S1c tasks fold in as Tasks 11–14.

---

## Global Constraints

- **Every timestamp originates in its event.** `materialize.py` and the writer modules contain no `datetime.now()`, `datetime.utcnow()`, `date.today()`, or `func.now()`, and never let a column fall through to its `server_default`. This is enforced by an AST guard (Task 10) because it is exactly the defect that collapsed all 40 existing transition chains into a single instant. **Note `created_at` carries `server_default` on every one of these tables and `WORKFLOW_TRANSITION_LOG.transitioned_at` does too** — omitting them is the failure mode, not a safe default.
- **Every timestamp is a `datetime`, never a `date`, and always has `microsecond == 0`, `tzinfo is None`.** MariaDB `DATETIME` carries no fractional precision and *rounds* on store, so `23:59:59.5` moves to the next day. (Spec §12.)
- **Stream order is preserved inside each table's batch.** Spec §4 says batch per table in FK-safe order; §12 says do not reorder events. Both hold at once: cross-table order is irrelevant to the only tie-break that matters — ascending `transition_id` within `HOLD_STATUS_TRANSITION` and `WORKFLOW_TRANSITION_LOG`, both autoincrement PKs. So: **batch per table, append in stream order, never sort a batch.**
- **Core bulk inserts only.** `conn.execute(insert(table), rows)` with `rows` a list of dicts. No ORM `add()`, no `session.flush()` to discover PKs.
- **Prod-safety carries over unchanged** (spec §9): INSERT-only, refuses any client not on the allowlist, never creates or drops schema (Alembic is the single schema mechanism), `--reset` deletes only allowlisted clients' rows.
- **Determinism:** the same `(scenarios, profile, seed, as_of)` produces an identical event stream and identical per-table row counts. Password hashes are the documented exception — argon2id salts randomly, so `USER.password_hash` is excluded from any byte-identity assertion.
- Files stay under 500 lines each.
- **Permissive assertions are forbidden.** Never `assert x in [...]`; assert exactly one expected value.
- Backend tests run as `pytest tests/` from `backend/`. Run them in the FOREGROUND — the Bash tool defaults to a 120s timeout, so pass `timeout: 900000` explicitly for the full suite.
- A test counts as evidence only after you have watched it fail for the reason it exists.
- **Every `DEMO_PASSWORD` literal needs a trailing `# pragma: allowlist secret`.** The blocking `detect-secrets` pre-commit hook flags the string otherwise and the commit is refused. This applies in `scenarios.py` and in every test that asserts on it — it already bit this plan's own commit.
- **Nothing in this PR changes runtime behaviour.** `backend/seed/` must remain unreachable from `backend.main`'s import graph, exactly as S1a verified. Task 10 re-proves it.

### Real vocabulary — take these, do not invent

Read off the live VM (2026-08-17). Inventing a synonym here is how the current dataset ended up with a defect taxonomy nothing joins to.

| Field | Values |
|---|---|
| `CLIENT.client_type` | `Piece Rate`, `Hourly Rate`, `Hybrid` |
| `PRODUCTION_LINE.line_type` | `DEDICATED` |
| `PRODUCT.unit_of_measure` | `units` |
| `WORK_ORDER.origin` | `AD_HOC`, `CAPACITY_PLAN` |
| `DOWNTIME_ENTRY.downtime_reason` | `MAINTENANCE`, `MATERIAL_SHORTAGE`, `OPERATOR_UNAVAILABLE`, `QUALITY_HOLD`, `SETUP_CHANGEOVER` |
| `DOWNTIME_ENTRY.root_cause_category` | `attendance`, `machine`, `materials`, `other`, `scheduling` |
| `DEFECT_TYPE_CATALOG.defect_code` | `COLOR`, `FABRIC`, `MEASURE`, `STAIN`, `STITCH` (per client; category `VISUAL`/`MATERIAL`/`DIMENSIONAL`, severity `MINOR`/`MAJOR`) |

**Pre-existing defect this fixes:** all 80 live `DEFECT_DETAIL` rows carry `defect_type = "Stitching"` — a display name, in no catalog. The taxonomy every DHU and quality view slices by is unjoinable, and the `DEFECT_TYPE_CATALOG` admin screen describes a vocabulary nothing uses. S1b emits catalog codes and Task 10 asserts the join holds.

---

## File Structure

```
backend/seed/
  __init__.py            (unchanged, empty)
  events.py              MODIFY  — widened event model                     Task 1
  scenarios.py           MODIFY  — vocabulary, users/roles, catalogs       Task 2
  profiles.py            MODIFY  — one field added                         Task 2
  generator.py           MODIFY  — emits the widened stream                Task 3
  identity.py            CREATE  — event key -> DB primary key             Task 4
  materialize.py         CREATE  — orchestrator, bulk insert, flush order  Task 5
  writers_master.py      CREATE  — client, users, employees, lines, ...    Task 6
  writers_operations.py  CREATE  — work orders, holds, shift-level rows    Task 7
  coverage.py            CREATE  — SEEDED / NOT_SEEDED contract            Task 8
  cli.py                 CREATE  — argparse entry point + prod guards      Task 9

backend/tests/test_seed/
  test_events.py         MODIFY   test_scenarios.py    MODIFY
  test_generator.py      MODIFY   test_narrative.py    MODIFY
  test_purity.py         MODIFY   test_identity.py     CREATE
  test_materialize.py    CREATE   test_coverage.py     CREATE
  test_cli.py            CREATE   test_seed_gates.py   CREATE
```

**Deviation from spec §5, stated up front:** the spec names a single `materialize.py`. Twenty-three tables of column mapping does not fit in 500 lines, and the 500-line rule is the binding constraint (spec §2 goal 5). `materialize.py` keeps the orchestration, the bulk-insert primitive, and the flush order; the per-table column mapping lives in two writer modules split by lifecycle — master data written once per client, versus operational rows written per event.

---

### Task 1: Widen the event model

The stream cannot currently express what the target tables require. Measured against `Base.metadata`, `PRODUCTION_ENTRY` needs `product_id`, `run_time_hours`, `entered_by`; `QUALITY_ENTRY` needs `work_order_id`; `DEFECT_DETAIL` needs a `defect_type`; and `ATTENDANCE_ENTRY` needs one row **per employee** with `employee_id` and `scheduled_hours`, where `ShiftWorked` carries only a headcount.

A materializer that invented absences and defect types would be generating data — in the layer the spec defines as a mechanical write, outside the AST purity guard, untested by the narrative suite. So the model widens and `ShiftWorked` splits into five events.

**Files:**
- Modify: `backend/seed/events.py`
- Test: `backend/tests/test_seed/test_events.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `PLATFORM_CLIENT_ID: str`; widened `ClientCreated`, `UserCreated`, `EmployeeHired`, `LineCommissioned`, `ShiftDefined`, `ProductDefined`, `WorkOrderReceived`; new `ClientAccessGranted`, `DefectTypeDefined`, `HoldReasonDefined`, `HoldStatusDefined`, `ThresholdSet`, `ClientConfigured`, `AttendanceRecorded`, `ProductionRecorded`, `QualityInspected`, `DefectsFound`, `DowntimeLogged`; `ShiftWorked` **removed**; `EVENT_TYPES` updated.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_seed/test_events.py`:

```python
from datetime import datetime

import pytest

from backend.seed.events import (
    EVENT_TYPES,
    PLATFORM_CLIENT_ID,
    AttendanceRecorded,
    DefectsFound,
    DowntimeLogged,
    ProductionRecorded,
    QualityInspected,
    UserCreated,
)


def _base(**kw):
    b = dict(at=datetime(2026, 3, 2, 6, 30, 0), seq=1, client_id="DEMO-PIECE")
    b.update(kw)
    return b


def test_shift_worked_no_longer_exists():
    """One shift writes rows in five tables and N per-employee attendance rows.
    A single ShiftWorked forces the materializer to invent the ones it does not
    describe, which is generation in the write layer."""
    import backend.seed.events as events_mod

    assert not hasattr(events_mod, "ShiftWorked")


def test_attendance_is_per_employee():
    e = AttendanceRecorded(
        **_base(),
        employee_id="DEMO-PIECE-EMP-001",
        line_id="DEMO-PIECE-LINE-01",
        shift_id="DEMO-PIECE-SHIFT-01",
        shift_date=datetime(2026, 3, 2, 6, 0, 0),
        scheduled_hours=8.0,
        hours_worked=8.0,
        is_absent=False,
    )

    assert e.employee_id == "DEMO-PIECE-EMP-001"
    assert e.is_absent is False


def test_every_datetime_field_is_validated_not_just_at():
    """`at` was the only guarded field while it was the only datetime one. The
    widened events carry shift_date and required_date, and MariaDB rounds a
    fractional second on ANY of them across a day boundary."""
    with pytest.raises(ValueError) as exc:
        AttendanceRecorded(
            **_base(),
            employee_id="E1",
            line_id="L1",
            shift_id="S1",
            shift_date=datetime(2026, 3, 2, 23, 59, 59, 500000),
            scheduled_hours=8.0,
            hours_worked=8.0,
            is_absent=False,
        )

    assert "shift_date" in str(exc.value)


def test_downtime_carries_a_root_cause():
    """Spec section 6 wants DEMO-HOURLY to read as equipment reliability and the
    Q4 correlation block needs scheduling-category downtime. Without a root cause
    on the event, both render as undifferentiated totals."""
    e = DowntimeLogged(
        **_base(),
        line_id="DEMO-HOURLY-LINE-01",
        shift_id="DEMO-HOURLY-SHIFT-01",
        shift_date=datetime(2026, 3, 2, 6, 0, 0),
        downtime_reason="MAINTENANCE",
        root_cause_category="machine",
        downtime_minutes=45,
    )

    assert e.root_cause_category == "machine"


def test_defects_reference_a_catalog_code_not_a_display_name():
    e = DefectsFound(**_base(), quality_entry_id="QE-1", defect_code="STITCH", defect_count=3)

    assert e.defect_code == "STITCH"


def test_quality_names_the_work_order_it_inspected():
    e = QualityInspected(
        **_base(),
        quality_entry_id="QE-1",
        work_order_id="DEMO-PIECE-WO-0001",
        shift_date=datetime(2026, 3, 2, 6, 0, 0),
        units_inspected=200,
        units_passed=195,
        units_defective=5,
        total_defects_count=7,
    )

    assert e.work_order_id == "DEMO-PIECE-WO-0001"


def test_production_carries_the_columns_the_table_requires():
    e = ProductionRecorded(
        **_base(),
        production_entry_id="PE-1",
        line_id="L1",
        shift_id="S1",
        product_id="P1",
        work_order_id="DEMO-PIECE-WO-0001",
        shift_date=datetime(2026, 3, 2, 6, 0, 0),
        units_produced=200,
        run_time_hours=7.5,
        scrap_count=2,
        employees_assigned=4,
        entered_by="demo_supervisor",
    )

    assert e.run_time_hours == 7.5
    assert e.entered_by == "demo_supervisor"


def test_platform_users_carry_the_sentinel_client():
    """admin and poweruser belong to no tenant. The sentinel keeps client_id a
    required str on every event; the materializer must never write it to a
    client_id column (guarded in test_seed_gates.py)."""
    e = UserCreated(
        **_base(client_id=PLATFORM_CLIENT_ID),
        user_id="USR-ADMIN",
        username="demo_admin",
        role="admin",
        email="demo_admin@example.invalid",
        full_name="Demo Admin",
        password="DemoSeed#2026",  # pragma: allowlist secret
    )

    assert e.client_id == PLATFORM_CLIENT_ID


def test_event_types_is_exhaustive():
    """EVENT_TYPES drives the coverage and purity guards; a type missing from it
    is a type nothing checks."""
    import backend.seed.events as events_mod
    from backend.seed.events import Event

    declared = {
        obj
        for obj in vars(events_mod).values()
        if isinstance(obj, type) and issubclass(obj, Event) and obj is not Event
    }

    assert declared == set(EVENT_TYPES)
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `cd backend && pytest tests/test_seed/test_events.py -v`
Expected: FAIL — `ImportError: cannot import name 'AttendanceRecorded'`.

- [ ] **Step 3: Widen `events.py`**

Replace the `Event.__post_init__` validation so it covers every datetime-valued field, then rewrite the event set. Keep the existing module docstring and extend it.

```python
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
        # shift_date and required_date, and MariaDB DATETIME rounds a fractional
        # second on any of them across a day boundary.
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
```

Then the event set. Master data:

```python
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
```

Operations:

```python
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
class DowntimeLogged(Event):
    line_id: str
    shift_id: str
    shift_date: datetime
    downtime_reason: str
    root_cause_category: str
    downtime_minutes: int
```

Delete `ShiftWorked` entirely and rebuild `EVENT_TYPES` to list all 20 classes above.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `cd backend && pytest tests/test_seed/test_events.py -v`
Expected: PASS. `tests/test_seed/test_generator.py` and `test_narrative.py` now FAIL on `ShiftWorked` — that is Task 3.

- [ ] **Step 5: Commit**

```bash
git add backend/seed/events.py backend/tests/test_seed/test_events.py
git commit -m "feat(seed): widen the event model so events can express their tables

One ShiftWorked cannot describe five tables plus N per-employee attendance
rows; a materializer inventing them would be generating outside the purity
guard. Splits it into AttendanceRecorded/ProductionRecorded/QualityInspected/
DefectsFound/DowntimeLogged and adds the columns the tables require NOT NULL."
```

---

### Task 2: Scenario vocabulary, catalogs, and credentials

Scenarios grow the declarative data the widened events need: real vocabulary, the six-role credential set (spec §9), per-client catalogs, and the products/thresholds/config the master writers consume.

**Files:**
- Modify: `backend/seed/scenarios.py`, `backend/seed/profiles.py`
- Test: `backend/tests/test_seed/test_scenarios.py`

**Interfaces:**
- Consumes: nothing (declarative).
- Produces: `DEFECT_CODES`, `HOLD_REASONS`, `HOLD_STATUSES`, `DOWNTIME_REASONS`, `ROOT_CAUSES`, `DEMO_PASSWORD`, `USERS: tuple[UserSpec, ...]`, `ClientScenario` gaining `client_type: str` and `products: tuple[ProductSpec, ...]`, `Profile` gaining `defect_rows_per_inspection: int`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_seed/test_scenarios.py`:

```python
from backend.seed.scenarios import (
    CLIENT_TYPE_BY_PAY_MODEL,
    DEFECT_CODES,
    DEMO_PASSWORD,
    DOWNTIME_REASONS,
    ROOT_CAUSES,
    SCENARIOS,
    USERS,
)


def test_client_type_uses_the_live_vocabulary():
    """Read off the VM. A synonym here is how the current dataset ended up with
    a defect taxonomy nothing joins to."""
    assert set(CLIENT_TYPE_BY_PAY_MODEL.values()) == {"Piece Rate", "Hourly Rate", "Hybrid"}


def test_every_scenario_resolves_to_a_client_type():
    for s in SCENARIOS:
        assert s.client_type == CLIENT_TYPE_BY_PAY_MODEL[s.pay_model]


def test_defect_codes_are_catalog_codes_not_display_names():
    assert DEFECT_CODES == ("COLOR", "FABRIC", "MEASURE", "STAIN", "STITCH")


def test_downtime_and_root_cause_vocabularies_are_the_live_ones():
    assert DOWNTIME_REASONS == (
        "MAINTENANCE",
        "MATERIAL_SHORTAGE",
        "OPERATOR_UNAVAILABLE",
        "QUALITY_HOLD",
        "SETUP_CHANGEOVER",
    )
    assert ROOT_CAUSES == ("attendance", "machine", "materials", "other", "scheduling")


def test_all_six_roles_have_a_credential():
    """Spec section 9: the documented set covers all six roles, so the
    permission model is demonstrable rather than described."""
    assert {u.role for u in USERS} == {
        "admin",
        "poweruser",
        "leader",
        "supervisor",
        "operator",
        "viewer",
    }


def test_the_leader_reaches_several_clients_and_the_supervisor_one():
    leader = next(u for u in USERS if u.role == "leader")
    supervisor = next(u for u in USERS if u.role == "supervisor")

    assert len(leader.client_ids) == 3
    assert len(supervisor.client_ids) == 1


def test_platform_roles_are_scoped_to_no_client():
    for role in ("admin", "poweruser"):
        user = next(u for u in USERS if u.role == role)
        assert user.client_ids == ()


def test_every_user_client_id_is_a_real_scenario():
    known = {s.client_id for s in SCENARIOS}
    for u in USERS:
        for cid in u.client_ids:
            assert cid in known


def test_usernames_are_unique():
    names = [u.username for u in USERS]
    assert len(names) == len(set(names))


def test_password_is_a_single_documented_constant():
    """One constant, referenced by the runbook. Per-user passwords in a demo
    are a documentation burden with no security benefit."""
    assert DEMO_PASSWORD == "DemoSeed#2026"  # pragma: allowlist secret


def test_the_attribution_user_is_one_of_the_seeded_users():
    """entered_by is a foreign key to USER. A literal that resolves to no user
    leaves every 'who entered this' column pointing at nobody."""
    from backend.seed.scenarios import SUPERVISOR_USER_ID

    assert SUPERVISOR_USER_ID in {u.user_id for u in USERS}


def test_every_scenario_declares_products():
    for s in SCENARIOS:
        assert len(s.products) == 3
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `cd backend && pytest tests/test_seed/test_scenarios.py -v`
Expected: FAIL — `ImportError: cannot import name 'CLIENT_TYPE_BY_PAY_MODEL'`.

- [ ] **Step 3: Extend `scenarios.py`**

```python
from dataclasses import dataclass, field

#: Live VM vocabulary (2026-08-17). Do not invent synonyms.
CLIENT_TYPE_BY_PAY_MODEL = {
    "piece": "Piece Rate",
    "hourly": "Hourly Rate",
    "hybrid": "Hybrid",
}
LINE_TYPE = "DEDICATED"
UNIT_OF_MEASURE = "units"
WORK_ORDER_ORIGINS = ("AD_HOC", "CAPACITY_PLAN")
DOWNTIME_REASONS = (
    "MAINTENANCE",
    "MATERIAL_SHORTAGE",
    "OPERATOR_UNAVAILABLE",
    "QUALITY_HOLD",
    "SETUP_CHANGEOVER",
)
ROOT_CAUSES = ("attendance", "machine", "materials", "other", "scheduling")
DEFECT_CODES = ("COLOR", "FABRIC", "MEASURE", "STAIN", "STITCH")

#: (code, display name, category, severity) — the catalog every client gets.
DEFECT_CATALOG = (
    ("COLOR", "Color Variation", "VISUAL", "MINOR"),
    ("FABRIC", "Fabric Flaw", "MATERIAL", "MAJOR"),
    ("MEASURE", "Measurement Out of Tolerance", "DIMENSIONAL", "MAJOR"),
    ("STAIN", "Stain or Soil", "VISUAL", "MINOR"),
    ("STITCH", "Stitching Defect", "VISUAL", "MAJOR"),
)

#: Which downtime reason each root cause explains. The narrative biases the
#: ROOT CAUSE (spec section 6: DEMO-HOURLY must read as equipment reliability,
#: and the Q4 correlation block needs scheduling-category downtime); the reason
#: follows from it, so the two can never disagree.
REASON_BY_ROOT_CAUSE = {
    "attendance": "OPERATOR_UNAVAILABLE",
    "machine": "MAINTENANCE",
    "materials": "MATERIAL_SHORTAGE",
    "other": "QUALITY_HOLD",
    "scheduling": "SETUP_CHANGEOVER",
}

HOLD_REASONS = (
    ("QUALITY", "Quality Issue", True),
    ("MATERIAL", "Material Shortage", False),
    ("ENGINEERING", "Engineering Change", False),
)
HOLD_STATUSES = (
    ("PENDING_HOLD_APPROVAL", "Pending Hold Approval", True),
    ("ON_HOLD", "On Hold", False),
    ("PENDING_RESUME_APPROVAL", "Pending Resume Approval", False),
    ("RESUMED", "Resumed", False),
)

#: kpi_key -> target. Global (KPI_THRESHOLD has no NOT NULL client column).
THRESHOLDS = (
    ("efficiency", 85.0),
    ("otd", 95.0),
    ("fpy", 97.0),
    ("oee", 75.0),
)

#: One constant, documented in the deployment runbook.
DEMO_PASSWORD = "DemoSeed#2026"  # pragma: allowlist secret

#: Who every seeded PRODUCTION_ENTRY.entered_by and transition is attributed
#: to. A real user_id, not a literal sprinkled through the generator: the
#: column is a foreign key to USER, and a string that resolves to no user
#: leaves the "who entered this" column pointing at nobody.
SUPERVISOR_USER_ID = "USR-DEMO-SUP"


@dataclass(frozen=True)
class UserSpec:
    user_id: str
    username: str
    role: str
    full_name: str
    client_ids: tuple[str, ...]  # () means platform-wide (no tenant scope)


USERS = (
    UserSpec("USR-DEMO-ADMIN", "demo_admin", "admin", "Demo Administrator", ()),
    UserSpec("USR-DEMO-PLANNER", "demo_planner", "poweruser", "Demo Planner", ()),
    UserSpec(
        "USR-DEMO-LEADER",
        "demo_leader",
        "leader",
        "Demo Area Leader",
        ("DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID"),
    ),
    UserSpec("USR-DEMO-SUP", "demo_supervisor", "supervisor", "Demo Supervisor", ("DEMO-PIECE",)),
    UserSpec("USR-DEMO-OP", "demo_operator", "operator", "Demo Operator", ("DEMO-PIECE",)),
    UserSpec("USR-DEMO-VIEW", "demo_viewer", "viewer", "Demo Viewer", ("DEMO-PIECE",)),
)


@dataclass(frozen=True)
class ProductSpec:
    code: str
    name: str
    style: str
```

Add `client_type: str` and `products: tuple[ProductSpec, ...]` to `ClientScenario`, and populate all four scenarios. Derive `client_type` explicitly in each literal (not computed) so the test above compares two independent statements rather than a value against itself:

```python
    ClientScenario(
        client_id="DEMO-PIECE",
        name="Piecework Apparel Co.",
        pay_model="piece",
        client_type="Piece Rate",
        products=(
            ProductSpec("PC-SHIRT", "Classic Shirt", "STYLE-1"),
            ProductSpec("PC-PANT", "Work Pant", "STYLE-2"),
            ProductSpec("PC-JACK", "Field Jacket", "STYLE-3"),
        ),
        narrative=(NarrativeWindow(kind="supplier_quality_crisis", start_month=-8, end_month=-6),),
    ),
```

Repeat for `DEMO-HOURLY` (`"Hourly Rate"`, `HR-` codes), `DEMO-HYBRID` (`"Hybrid"`, `HY-` codes), `SAMPLE_REF` (`"Hourly Rate"`, `RF-` codes).

In `profiles.py`, add `defect_rows_per_inspection: int` to `Profile` — `2` on `FULL`, `1` on `SMOKE`.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `cd backend && pytest tests/test_seed/test_scenarios.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/seed/scenarios.py backend/seed/profiles.py backend/tests/test_seed/test_scenarios.py
git commit -m "feat(seed): real vocabulary, six-role credentials, per-client catalogs

Vocabulary read off the live VM rather than invented. All six roles get a
documented credential so multi-tenant scoping and viewer read-only are
demonstrable, not merely described."
```

---

### Task 3: Generator emits the widened stream

**Files:**
- Modify: `backend/seed/generator.py`
- Test: `backend/tests/test_seed/test_generator.py`, `backend/tests/test_seed/test_narrative.py`

**Interfaces:**
- Consumes: Task 1's events, Task 2's scenarios.
- Produces: `generate(scenarios, profile, seed, as_of) -> List[Event]` (signature unchanged) now emitting the widened set; `stream_digest` unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_seed/test_generator.py`:

```python
from collections import Counter
from datetime import date

from backend.seed.events import (
    AttendanceRecorded,
    ClientAccessGranted,
    DefectsFound,
    DefectTypeDefined,
    DowntimeLogged,
    ProductionRecorded,
    QualityInspected,
    UserCreated,
    WorkOrderReceived,
)
from backend.seed.generator import generate
from backend.seed.profiles import SMOKE
from backend.seed.scenarios import DEFECT_CODES, ROOT_CAUSES, SCENARIOS, USERS

AS_OF = date(2026, 8, 18)


def _stream():
    return generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)


def test_attendance_is_emitted_once_per_employee_per_worked_shift():
    """The headcount-only event could not express this; N rows per shift is the
    reason the model split."""
    events = _stream()
    attendance = [e for e in events if isinstance(e, AttendanceRecorded)]
    production = [e for e in events if isinstance(e, ProductionRecorded)]

    assert attendance
    per_shift = Counter((e.client_id, e.line_id, e.shift_id, e.shift_date) for e in attendance)
    # One production row per worked (client, line, shift, date); attendance is
    # one row per employee on that same key, so every key must exceed 1.
    assert len(per_shift) == len(production)
    assert min(per_shift.values()) > 1


def test_defect_codes_are_always_catalog_codes():
    events = _stream()
    defined = {(e.client_id, e.defect_code) for e in events if isinstance(e, DefectTypeDefined)}
    found = [e for e in events if isinstance(e, DefectsFound)]

    assert found
    for e in found:
        assert e.defect_code in DEFECT_CODES
        assert (e.client_id, e.defect_code) in defined


def test_every_defects_found_references_an_earlier_quality_entry():
    """Referential integrity in time: the materializer inserts in stream order,
    so a child may never precede its parent."""
    seen = set()
    for e in _stream():
        if isinstance(e, QualityInspected):
            seen.add(e.quality_entry_id)
        elif isinstance(e, DefectsFound):
            assert e.quality_entry_id in seen


def test_downtime_root_causes_come_from_the_live_vocabulary():
    for e in _stream():
        if isinstance(e, DowntimeLogged):
            assert e.root_cause_category in ROOT_CAUSES


def test_work_orders_carry_a_required_date_after_receipt():
    orders = [e for e in _stream() if isinstance(e, WorkOrderReceived)]

    assert orders
    for e in orders:
        assert e.required_date > e.at


def test_the_six_users_are_emitted_once_each_with_their_grants():
    events = _stream()
    users = [e for e in events if isinstance(e, UserCreated)]
    grants = [e for e in events if isinstance(e, ClientAccessGranted)]

    assert len(users) == len(USERS)
    assert len(grants) == sum(len(u.client_ids) for u in USERS)


def test_users_are_emitted_before_any_grant_references_them():
    created = set()
    for e in _stream():
        if isinstance(e, UserCreated):
            created.add(e.user_id)
        elif isinstance(e, ClientAccessGranted):
            assert e.user_id in created
```

Add to `backend/tests/test_seed/test_narrative.py`:

```python
def test_equipment_decline_biases_the_root_cause_toward_machine():
    """Spec section 6: DEMO-HOURLY must read as equipment reliability. Scaling
    only downtime MINUTES leaves Q2 an undifferentiated total."""
    from collections import Counter
    from datetime import date

    from backend.seed.events import DowntimeLogged
    from backend.seed.generator import _window_active, generate
    from backend.seed.profiles import FULL
    from backend.seed.scenarios import SCENARIOS

    as_of = date(2026, 8, 18)
    hourly = next(s for s in SCENARIOS if s.client_id == "DEMO-HOURLY")
    events = [
        e
        for e in generate(SCENARIOS, FULL, seed=1234, as_of=as_of)
        if isinstance(e, DowntimeLogged) and e.client_id == "DEMO-HOURLY"
    ]

    inside = Counter(
        e.root_cause_category
        for e in events
        if _window_active(hourly, e.shift_date.date(), as_of, "equipment_reliability_decline")
    )
    outside = Counter(
        e.root_cause_category
        for e in events
        if not _window_active(hourly, e.shift_date.date(), as_of, "equipment_reliability_decline")
    )

    assert inside["machine"] / sum(inside.values()) > 2 * (outside["machine"] / sum(outside.values()))
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `cd backend && pytest tests/test_seed/test_generator.py tests/test_seed/test_narrative.py -v`
Expected: FAIL — `ImportError` on the new event names, plus existing `ShiftWorked` tests failing.

- [ ] **Step 3: Rewrite the generator's emission**

Replace the `ShiftWorked` emission block. Preserve the existing structure exactly — the setup-day band, `activity_start`, the Mon–Fri loop, `_narrative_scale`, and every comment explaining why an offset is computed the way it is. Those comments record bugs already paid for; do not compress them.

Three locals the current generator does not keep must now be retained, because the widened events reference them: the hired employees (the `EmployeeHired` loop currently emits and forgets, but attendance needs one row per employee **on this line**), a `products_by_id` mapping (`WorkOrderReceived.style_model` reads the product's style), and `open_orders` — the work orders received on or before the day being generated, which `QualityInspected` inspects. Build the employee list as `list[tuple[employee_id, line_id]]` inside the setup band as each is emitted; build `open_orders` by recording `(received_day, work_order_id)` in the work-order loop and filtering it per day.

This forces one reordering: the work-order loop must run **before** the daily shift loop, since quality references orders. The work-order loop's own anchoring on `activity_start` is unchanged, so no event moves in time — only the order in which they are appended before the final sort, which `generate()` already normalizes by sorting on `order_key` and renumbering `seq`.

Emit the platform layer once, before the per-client loop, at `day0 - 1 day` so users exist before any client references them:

```python
    # Users are global. They are emitted BEFORE the per-client loop and stamped
    # a day earlier than the earliest client's setup, so ClientAccessGranted and
    # every `entered_by` reference resolves to a user already in the stream.
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
    grant_cursor = len(USERS)
    for spec in USERS:
        for cid in spec.client_ids:
            emit(
                ClientAccessGranted,
                platform_at + timedelta(minutes=grant_cursor),
                cid,
                user_id=spec.user_id,
                is_primary=cid == spec.client_ids[0],
            )
            grant_cursor += 1
```

The existing per-client `UserCreated` emission for `{cid}_supervisor` is removed — the six-role set replaces it. Add catalogs, thresholds, and config to the per-client setup band, each advancing `minute_cursor`, in this order: `ClientCreated`, `ClientConfigured`, `HoldReasonDefined` ×3, `HoldStatusDefined` ×4, `DefectTypeDefined` ×5, `LineCommissioned`, `ShiftDefined`, `ProductDefined`, `EmployeeHired`, `ThresholdSet` ×4. `ThresholdSet` is emitted under the first scenario's client only (KPI_THRESHOLD is global), guarded by `if scenario is scenarios[0]`.

Replace the inner shift body. The RNG draw ORDER and COUNT are load-bearing — draw everything unconditionally, before consulting narrative state, exactly as the hold block already does:

```python
                # Draws taken unconditionally and in a fixed order, before any
                # narrative state is consulted: a draw whose existence depends
                # on a window being active would make the stream's RNG
                # consumption vary with the calendar, and no two profiles would
                # be comparable. Same rule the hold block below documents.
                produced = rng.randint(180, 260)
                defect_rate = rng.uniform(0.01, 0.03) * scale["defects"]
                downtime_minutes = int(rng.randint(5, 40) * scale["downtime"])
                root_cause_draw = rng.random()
                run_time = round(rng.uniform(6.5, 7.8), 2)
                attendance_draws = [rng.random() for _ in range(profile.employees_per_client)]

                shift_hour = (6 + si * shift_hour_step) % 24
                shift_minute = (30 + li * line_minute_step) % 60
                at = datetime.combine(day, time(shift_hour, shift_minute))
                # shift_date is the SHIFT's own instant, stamped at its start
                # hour -- never midnight. A midnight shift_date sits on a
                # half-open range boundary and same-day queries return zero
                # (the date-boundary bug class fixed in #146).
                shift_date = datetime.combine(day, time(shift_hour, 0))

                defective = int(produced * defect_rate)
                scrap = defective // 3

                # --- attendance, one row per employee on this line
                crew = [e for e in employees if e.line_id == line_id]
                present = 0
                for ei, member in enumerate(crew):
                    # A lower scale["attendance"] means MORE absence: the
                    # labor-disruption window reduces effective headcount.
                    is_absent = attendance_draws[ei] > scale["attendance"] * 0.95
                    present += 0 if is_absent else 1
                    emit(
                        AttendanceRecorded,
                        at,
                        cid,
                        employee_id=member.employee_id,
                        line_id=line_id,
                        shift_id=shift_id,
                        shift_date=shift_date,
                        scheduled_hours=8.0,
                        hours_worked=0.0 if is_absent else 8.0,
                        is_absent=is_absent,
                    )

                # --- production
                emit(
                    ProductionRecorded,
                    at,
                    cid,
                    production_entry_id=f"{cid}-PE-{day.isoformat()}-{li}-{si}",
                    line_id=line_id,
                    shift_id=shift_id,
                    product_id=products[(li + si) % len(products)],
                    work_order_id=None,
                    shift_date=shift_date,
                    units_produced=produced,
                    run_time_hours=run_time,
                    scrap_count=scrap,
                    employees_assigned=max(1, present),
                    entered_by=SUPERVISOR_USER_ID,
                )

                # --- downtime, root cause first: the narrative biases the
                # CAUSE and the reason follows from it, so the two can never
                # disagree in the Q2 view.
                pool = _root_cause_pool(scenario, day, as_of)
                root_cause = pool[int(root_cause_draw * len(pool))]
                emit(
                    DowntimeLogged,
                    at,
                    cid,
                    line_id=line_id,
                    shift_id=shift_id,
                    shift_date=shift_date,
                    downtime_reason=REASON_BY_ROOT_CAUSE[root_cause],
                    root_cause_category=root_cause,
                    downtime_minutes=downtime_minutes,
                )
```

Quality is emitted against a work order, so it must run after the work-order loop rather than inside the shift loop. Move the shift loop below the work-order loop and, for each worked shift, pick the order via `open_orders[(li + si + offset) % len(open_orders)]` where `open_orders` is the list of orders received on or before `day`. If none are open yet, skip the quality/defect emission for that shift and record nothing — do not fabricate an order id.

```python
                if open_orders:
                    qe_id = f"{cid}-QE-{day.isoformat()}-{li}-{si}"
                    emit(
                        QualityInspected,
                        at,
                        cid,
                        quality_entry_id=qe_id,
                        work_order_id=open_orders[(li + si + offset) % len(open_orders)],
                        shift_date=shift_date,
                        units_inspected=produced,
                        units_passed=produced - defective,
                        units_defective=defective,
                        total_defects_count=defective,
                    )
                    remaining = defective
                    for k in range(profile.defect_rows_per_inspection):
                        last = k == profile.defect_rows_per_inspection - 1
                        count = remaining if last else remaining // 2
                        if count <= 0:
                            break
                        remaining -= count
                        emit(
                            DefectsFound,
                            at,
                            cid,
                            quality_entry_id=qe_id,
                            defect_code=DEFECT_CODES[(li + si + k) % len(DEFECT_CODES)],
                            defect_count=count,
                        )
```

Add the root-cause pool helper beside `_hold_rate`:

```python
EQUIPMENT_DECLINE_CAUSES = ("machine", "machine", "machine", "machine", "materials", "other")
SCHEDULING_PRESSURE_CAUSES = ("scheduling", "scheduling", "machine", "materials", "other")
BASELINE_CAUSES = ("attendance", "machine", "materials", "other", "scheduling")


def _root_cause_pool(scenario: ClientScenario, day: date, as_of: date) -> tuple:
    """Which root causes are plausible on this client-day. Biasing the pool
    rather than forcing a value keeps the RNG varying which shifts get which
    cause, so a window reads as a shift in the MIX rather than a block of
    identical rows."""
    if _window_active(scenario, day, as_of, "equipment_reliability_decline"):
        return EQUIPMENT_DECLINE_CAUSES
    if _window_active(scenario, day, as_of, "labor_disruption"):
        return SCHEDULING_PRESSURE_CAUSES
    return BASELINE_CAUSES
```

Add `required_date`, `style_model`, `origin`, and `priority` to the `WorkOrderReceived` emission. Draw all four unconditionally:

```python
        lead_days = rng.randint(20, 60)
        origin = WORK_ORDER_ORIGINS[rng.randrange(len(WORK_ORDER_ORIGINS))]
        # ~15% carry no priority: spec section 3 decision 6 excludes those from
        # the priority-adherence denominator and publishes their share as a
        # coverage figure. A dataset where every order has a priority cannot
        # demonstrate that the exclusion works.
        priority_draw = rng.random()
        priority = None if priority_draw < 0.15 else PRIORITIES[int(priority_draw * len(PRIORITIES))]
```

with `PRIORITIES = ("LOW", "NORMAL", "HIGH", "URGENT")` at module level, `style_model=products_by_id[product_id].style`, and `required_date=datetime.combine(opened + timedelta(days=lead_days), time(17, 0))`.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `cd backend && pytest tests/test_seed/ -v`
Expected: PASS, including the existing determinism and purity tests. If a pinned `stream_digest` value fails, that is correct — the stream changed. Re-pin it from the new output and note in the commit that the digest moved; do NOT loosen the assertion.

- [ ] **Step 5: Commit**

```bash
git add backend/seed/generator.py backend/tests/test_seed/
git commit -m "feat(seed): generator emits the widened stream

Per-employee attendance, production/quality/defect/downtime as separate
events, catalog-valid defect codes, root-cause-first downtime so the
narrative biases the cause rather than only the minutes, and work orders
carrying required_date, origin and priority."
```

---

### Task 4: Identity map and deterministic primary keys

Four master tables — `PRODUCTION_LINE`, `SHIFT`, `PRODUCT`, `EMPLOYEE` — use autoincrement **integer** PKs, while the stream identifies them by stable string business keys (`DEMO-PIECE-LINE-01`). The old seeder resolved this by ORM `add()` + `flush()` and reading `line.line_id` back. Core bulk insert has no such round trip, so the materializer allocates PKs itself and remembers them.

Allocation reads `MAX(pk)` inside the seeding transaction rather than using fixed offsets: `EMPLOYEE` has no tenant column at all (it is scoped through `EMPLOYEE_CLIENT_ASSIGNMENT`), so its integers are shared with every real client on a production database. A fixed offset would collide the moment a real employee exists — the `_next_id`/prefix collision class this repo has already hit once.

**Files:**
- Create: `backend/seed/identity.py`
- Test: `backend/tests/test_seed/test_identity.py`

**Interfaces:**
- Consumes: a live `sqlalchemy.Connection`.
- Produces: `class UnknownEntity(KeyError)`; `class IdMap` with `assign(table: str, key: str, value: object) -> None`, `resolve(table: str, key: str) -> object`, `has(table: str, key: str) -> bool`; `class IntPkAllocator` with `__init__(conn, table: Table)` and `next() -> int`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_seed/test_identity.py`:

```python
import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, insert

from backend.seed.identity import IdMap, IntPkAllocator, UnknownEntity


def test_resolve_names_the_missing_entity_instead_of_raising_a_bare_keyerror():
    """A silent miss becomes a NULL foreign key thousands of rows later. The
    error has to say which table and which key, or a stream-ordering bug is
    unreadable."""
    m = IdMap()
    m.assign("PRODUCTION_LINE", "DEMO-PIECE-LINE-01", 7)

    with pytest.raises(UnknownEntity) as exc:
        m.resolve("PRODUCTION_LINE", "DEMO-PIECE-LINE-99")

    assert "PRODUCTION_LINE" in str(exc.value)
    assert "DEMO-PIECE-LINE-99" in str(exc.value)


def test_assigning_the_same_key_twice_is_rejected():
    m = IdMap()
    m.assign("SHIFT", "S1", 1)

    with pytest.raises(ValueError):
        m.assign("SHIFT", "S1", 2)


def test_allocator_starts_above_the_existing_maximum():
    """EMPLOYEE has no tenant column, so its integers are shared with real
    clients on a production database. Starting at 1 would collide."""
    engine = create_engine("sqlite://")
    md = MetaData()
    t = Table("T", md, Column("id", Integer, primary_key=True), Column("name", String(10)))
    md.create_all(engine)

    with engine.begin() as conn:
        conn.execute(insert(t), [{"id": 41, "name": "existing"}])
        alloc = IntPkAllocator(conn, t)

        assert alloc.next() == 42
        assert alloc.next() == 43


def test_allocator_starts_at_one_on_an_empty_table():
    engine = create_engine("sqlite://")
    md = MetaData()
    t = Table("T", md, Column("id", Integer, primary_key=True))
    md.create_all(engine)

    with engine.begin() as conn:
        assert IntPkAllocator(conn, t).next() == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && pytest tests/test_seed/test_identity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.seed.identity'`.

- [ ] **Step 3: Write `identity.py`**

```python
"""Event keys to database primary keys.

The stream identifies entities by stable string business keys; four master
tables (PRODUCTION_LINE, SHIFT, PRODUCT, EMPLOYEE) use autoincrement integer
PKs. Core bulk insert gives no PK round trip, so the materializer allocates
them here and resolves foreign keys through the map.
"""

from sqlalchemy import Connection, Table, func, select


class UnknownEntity(KeyError):
    """A foreign key referenced an entity the stream never created."""


class IdMap:
    def __init__(self) -> None:
        self._by_table: dict[str, dict[str, object]] = {}

    def assign(self, table: str, key: str, value: object) -> None:
        bucket = self._by_table.setdefault(table, {})
        if key in bucket:
            raise ValueError(f"{table}: key {key!r} already assigned to {bucket[key]!r}")
        bucket[key] = value

    def resolve(self, table: str, key: str) -> object:
        try:
            return self._by_table[table][key]
        except KeyError:
            # Bare KeyError surfaces thousands of rows later as a NULL FK or an
            # IntegrityError naming a column, not the ordering bug that caused
            # it. Name both halves.
            raise UnknownEntity(
                f"{table}: no primary key assigned for {key!r} -- the stream referenced "
                "it before the event that creates it, or that event was never emitted"
            ) from None

    def has(self, table: str, key: str) -> bool:
        return key in self._by_table.get(table, {})


class IntPkAllocator:
    """Contiguous integer PKs above the table's current maximum.

    Reads MAX(pk) inside the seeding transaction rather than using a fixed
    offset: EMPLOYEE carries no tenant column, so its integers are shared with
    every real client on a production database.
    """

    def __init__(self, conn: Connection, table: Table) -> None:
        pk = list(table.primary_key.columns)[0]
        self._next = int(conn.execute(select(func.coalesce(func.max(pk), 0))).scalar_one()) + 1

    def next(self) -> int:
        value = self._next
        self._next += 1
        return value
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && pytest tests/test_seed/test_identity.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/seed/identity.py backend/tests/test_seed/test_identity.py
git commit -m "feat(seed): identity map and MAX-based integer PK allocation

Four master tables use autoincrement integer PKs the stream identifies by
string key, and Core bulk insert has no PK round trip. EMPLOYEE has no tenant
column, so allocation reads MAX() rather than using a fixed offset."
```

---

### Task 5: Materializer core — bulk insert, flush order, coverage gate

**Files:**
- Create: `backend/seed/materialize.py`
- Test: `backend/tests/test_seed/test_materialize.py`

**Interfaces:**
- Consumes: `IdMap`, `IntPkAllocator`, the event stream.
- Produces: `BATCH_SIZE: int`; `class RowSink` with `add(table_name: str, row: dict) -> None`, `rows(table_name: str) -> list[dict]`, `tables() -> list[str]`; `bulk_insert(conn, table, rows) -> None`; `flush(conn, sink) -> dict[str, int]`; `materialize(conn, events, profile) -> dict[str, int]`; `INSERT_ORDER: list[str]`; `CLIENT_SCOPE_COLUMN: dict[str, str | None]` (`None` marks a table that exists but is not tenant-scoped).

`INSERT_ORDER` is derived from `Base.metadata.sorted_tables`, not hand-written. SQLAlchemy already topologically sorts by foreign key, so the ordering cannot rot when a table is added. What *is* salvaged from the retiring `seed_sample_client._reset_table_order()` is the part `sorted_tables` cannot supply: which column scopes each table to a client (`client_id`, `client_id_fk`, `client_id_assigned`) and the one table reached only through its parent.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_seed/test_materialize.py`:

```python
from datetime import date, datetime

from sqlalchemy import func, select

from backend.database import Base
from backend.orm import HoldStatusTransition, WorkflowTransitionLog, WorkOrder
from backend.seed.generator import generate
from backend.seed.materialize import CLIENT_SCOPE_COLUMN, INSERT_ORDER, RowSink, materialize
from backend.seed.profiles import SMOKE
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 18)


def test_insert_order_is_derived_from_metadata_not_hand_written():
    """A hand-maintained FK order rots the first time a table is added. This
    one cannot: SQLAlchemy topologically sorts by foreign key."""
    assert INSERT_ORDER == [t.name for t in Base.metadata.sorted_tables]


def test_every_client_scoped_table_declares_its_scope_column():
    """Three different column names carry the tenant across these tables. The
    map is what --reset filters on; a missing entry means a client's rows
    survive a reset and collide on re-seed."""
    for table_name in ("PRODUCTION_ENTRY", "DEFECT_DETAIL", "EMPLOYEE"):
        assert table_name in CLIENT_SCOPE_COLUMN

    assert CLIENT_SCOPE_COLUMN["PRODUCTION_ENTRY"] == "client_id"
    assert CLIENT_SCOPE_COLUMN["DEFECT_DETAIL"] == "client_id_fk"
    assert CLIENT_SCOPE_COLUMN["EMPLOYEE"] == "client_id_assigned"


def test_sink_preserves_stream_order_within_a_table():
    """Spec section 12: cross-table order is irrelevant, but active_as_of
    tie-breaks on ascending transition_id, so a batch must never be sorted."""
    sink = RowSink()
    sink.add("WORK_ORDER", {"work_order_id": "B"})
    sink.add("SHIFT", {"shift_id": 1})
    sink.add("WORK_ORDER", {"work_order_id": "A"})

    assert [r["work_order_id"] for r in sink.rows("WORK_ORDER")] == ["B", "A"]


def test_a_smoke_seed_writes_rows(seed_engine):
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)

    with seed_engine.begin() as conn:
        counts = materialize(conn, events, SMOKE)

    assert counts["WORK_ORDER"] > 0
    assert counts["ATTENDANCE_ENTRY"] > counts["PRODUCTION_ENTRY"]


def test_transition_timestamps_are_not_all_the_seed_run_instant(seed_engine):
    """The defect this whole project exists to fix: 40 chains collapsed into a
    single instant because transitioned_at fell through to its server_default.
    That column HAS a server default -- omitting it is the failure mode."""
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        distinct = conn.execute(
            select(func.count(func.distinct(WorkflowTransitionLog.transitioned_at)))
        ).scalar_one()
        earliest = conn.execute(select(func.min(WorkflowTransitionLog.transitioned_at))).scalar_one()

    assert distinct > 10
    assert earliest < datetime(2026, 8, 1)


def test_created_at_is_back_dated_too(seed_engine):
    """created_at carries a server_default on every seeded table. A row whose
    created_at is the seed-run instant is a row the materializer forgot."""
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        earliest = conn.execute(select(func.min(WorkOrder.created_at))).scalar_one()

    assert earliest < datetime(2026, 8, 1)


def test_hold_status_history_is_monotonic_per_hold(seed_engine):
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        rows = conn.execute(
            select(
                HoldStatusTransition.hold_entry_id,
                HoldStatusTransition.transition_id,
                HoldStatusTransition.transitioned_at,
            ).order_by(HoldStatusTransition.hold_entry_id, HoldStatusTransition.transition_id)
        ).all()

    assert rows
    seen: dict = {}
    for hold_id, _tid, at in rows:
        if hold_id in seen:
            assert at >= seen[hold_id]
        seen[hold_id] = at
```

Add the `seed_engine` fixture to `backend/tests/test_seed/conftest.py` (create it). It must build the schema through Alembic, never `create_all` — `test_no_create_all_outside_alembic` guards that:

```python
import pytest
from sqlalchemy import create_engine

from backend.db.migrate import upgrade_to_head


@pytest.fixture
def seed_engine(tmp_path):
    """A real file-backed SQLite database with the schema built by Alembic.

    Alembic, not create_all: C5 made Alembic the single schema mechanism and
    test_no_create_all_outside_alembic enforces it. File-backed, not
    in-memory, because the materializer opens its own connection.
    """
    url = f"sqlite:///{tmp_path / 'seed.db'}"
    upgrade_to_head(url)
    engine = create_engine(url)
    yield engine
    engine.dispose()
```

`upgrade_to_head(url: Optional[str] = None)` (`backend/db/migrate.py:29`) accepts the URL directly, so no environment juggling is needed.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_seed/test_materialize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'backend.seed.materialize'`.

- [ ] **Step 3: Write `materialize.py`**

```python
"""Event stream -> database rows.

Mechanical. Every value written here comes from an event; this module invents
nothing, and contains no clock -- no datetime.now(), no func.now(), and no
column left to its server_default. That last one is not a style preference:
created_at carries a server default on every seeded table and
WORKFLOW_TRANSITION_LOG.transitioned_at does too, and letting them fall
through is precisely what collapsed all 40 existing transition chains into a
single instant.

Batching: rows accumulate per table and flush in Base.metadata.sorted_tables
order (FK-safe, derived rather than hand-maintained). Within a table the batch
keeps stream order and is never sorted -- active_as_of tie-breaks on ascending
transition_id, so insertion order is load-bearing (spec section 12).
"""

from typing import Iterable

from sqlalchemy import Connection, Table, insert

from backend.database import Base
from backend.seed.events import Event
from backend.seed.identity import IdMap
from backend.seed.profiles import Profile

#: Rows per executemany chunk. Bounded so a 32-column table cannot build a
#: statement past MariaDB's max_allowed_packet on the FULL profile.
BATCH_SIZE = 500

#: FK-safe insert order, derived from the metadata's topological sort. Never
#: hand-maintain this: a hand-written list rots the first time a table is added
#: and the failure is an IntegrityError far from the edit that caused it.
INSERT_ORDER = [t.name for t in Base.metadata.sorted_tables]

#: Which column scopes each table to a tenant. Salvaged from the retiring
#: seed_sample_client._reset_table_order(), which is the only place three
#: different names (client_id / client_id_fk / client_id_assigned) were ever
#: written down. --reset filters on this; a missing entry means a client's rows
#: survive a reset and collide on re-seed.
CLIENT_SCOPE_COLUMN = {
    "CLIENT": "client_id",
    "CLIENT_CONFIG": "client_id",
    "KPI_THRESHOLD": None,  # global; not client-scoped
    "HOLD_REASON_CATALOG": "client_id",
    "HOLD_STATUS_CATALOG": "client_id",
    "DEFECT_TYPE_CATALOG": "client_id",
    "PRODUCTION_LINE": "client_id",
    "SHIFT": "client_id",
    "PRODUCT": "client_id",
    "EMPLOYEE": "client_id_assigned",
    "EMPLOYEE_CLIENT_ASSIGNMENT": "client_id",
    "EMPLOYEE_LINE_ASSIGNMENT": "client_id",
    "USER_CLIENT_ASSIGNMENT": "client_id",
    "WORK_ORDER": "client_id",
    "WORKFLOW_TRANSITION_LOG": "client_id",
    "HOLD_ENTRY": "client_id",
    "HOLD_STATUS_TRANSITION": "client_id",
    "ATTENDANCE_ENTRY": "client_id",
    "PRODUCTION_ENTRY": "client_id",
    "QUALITY_ENTRY": "client_id",
    "DEFECT_DETAIL": "client_id_fk",
    "DOWNTIME_ENTRY": "client_id",
}


class RowSink:
    """Accumulates rows per table, preserving the order they were added."""

    def __init__(self) -> None:
        self._rows: dict[str, list[dict]] = {}

    def add(self, table_name: str, row: dict) -> None:
        self._rows.setdefault(table_name, []).append(row)

    def rows(self, table_name: str) -> list[dict]:
        return self._rows.get(table_name, [])

    def tables(self) -> list[str]:
        return list(self._rows)


def bulk_insert(conn: Connection, table: Table, rows: list[dict]) -> None:
    if not rows:
        return
    for start in range(0, len(rows), BATCH_SIZE):
        conn.execute(insert(table), rows[start : start + BATCH_SIZE])


def flush(conn: Connection, sink: RowSink) -> dict[str, int]:
    # A table written but not declared SEEDED is a table the coverage contract
    # does not govern -- it would never be checked for rows and could silently
    # empty. Checked against SEEDED, NOT against INSERT_ORDER: INSERT_ORDER is
    # every table in the metadata, so a check against it could never fire.
    from backend.seed.coverage import SEEDED

    undeclared = set(sink.tables()) - SEEDED
    if undeclared:
        raise RuntimeError(
            f"writers produced rows for tables outside the coverage contract: {sorted(undeclared)}"
        )

    counts: dict[str, int] = {}
    for name in INSERT_ORDER:
        rows = sink.rows(name)
        if not rows:
            continue
        bulk_insert(conn, Base.metadata.tables[name], rows)
        counts[name] = len(rows)
    return counts


def materialize(conn: Connection, events: Iterable[Event], profile: Profile) -> dict[str, int]:
    from backend.seed import writers_master, writers_operations

    sink = RowSink()
    ids = IdMap()
    allocators = writers_master.build_allocators(conn)

    for event in events:
        if writers_master.handle(event, sink, ids, allocators):
            continue
        if writers_operations.handle(event, sink, ids, profile):
            continue
        raise RuntimeError(f"no writer handles {type(event).__name__}")

    return flush(conn, sink)
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && pytest tests/test_seed/test_materialize.py -v`
Expected: the three pure tests PASS; the four `seed_engine` tests FAIL with `ModuleNotFoundError: backend.seed.writers_master` — Tasks 6 and 7.

- [ ] **Step 5: Commit**

```bash
git add backend/seed/materialize.py backend/tests/test_seed/test_materialize.py backend/tests/test_seed/conftest.py
git commit -m "feat(seed): materializer core - bulk insert, derived FK order, row sink

INSERT_ORDER derives from Base.metadata.sorted_tables so it cannot rot.
CLIENT_SCOPE_COLUMN salvages the three tenant-column names from the retiring
seed_sample_client._reset_table_order()."
```

---

### Task 6: Master-data writers

**Files:**
- Create: `backend/seed/writers_master.py`
- Test: `backend/tests/test_seed/test_materialize.py` (extend)

**Interfaces:**
- Consumes: `RowSink`, `IdMap`, `IntPkAllocator`, Task 1's master events.
- Produces: `build_allocators(conn) -> dict[str, IntPkAllocator]`; `handle(event, sink, ids, allocators) -> bool` (True when it owned the event); `INT_PK_TABLES: tuple[str, ...]`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_seed/test_materialize.py`:

```python
def test_users_cover_all_six_roles_and_can_authenticate(seed_engine):
    """A seeded password hash the verifier rejects is a demo nobody can log
    into -- and unit tests that only count rows would not notice."""
    from backend.auth.password import verify_password
    from backend.orm import User
    from backend.seed.scenarios import DEMO_PASSWORD

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        rows = conn.execute(select(User.username, User.role, User.password_hash)).all()

    assert {r.role for r in rows} == {"admin", "poweruser", "leader", "supervisor", "operator", "viewer"}
    for r in rows:
        assert verify_password(DEMO_PASSWORD, r.password_hash) is True


def test_the_platform_sentinel_never_reaches_a_client_column(seed_engine):
    from backend.seed.events import PLATFORM_CLIENT_ID

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        for table_name, column in CLIENT_SCOPE_COLUMN.items():
            if column is None:
                continue
            table = Base.metadata.tables[table_name]
            hits = conn.execute(
                select(func.count()).select_from(table).where(table.c[column] == PLATFORM_CLIENT_ID)
            ).scalar_one()
            assert hits == 0, f"{table_name}.{column} carries the stream sentinel"


def test_the_leader_reaches_three_clients_through_the_real_scope_resolver(seed_engine):
    """USER_CLIENT_ASSIGNMENT was zero for the entire life of the client-scope
    feature. Counting rows would not prove the resolver reads them.

    get_user_client_filter is the plain function resolve_client_scope delegates
    to (backend/auth/jwt.py:353); resolve_client_scope itself is a FastAPI
    dependency and needs a request to call. None means "all clients".
    """
    from sqlalchemy.orm import Session

    from backend.middleware.client_auth import get_user_client_filter
    from backend.orm import User

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with Session(seed_engine) as session:
        leader = session.query(User).filter(User.username == "demo_leader").one()
        viewer = session.query(User).filter(User.username == "demo_viewer").one()

        assert len(get_user_client_filter(leader, session)) == 3
        assert len(get_user_client_filter(viewer, session)) == 1


def test_integer_pks_are_assigned_and_resolvable(seed_engine):
    from backend.orm import ProductionLine, Shift

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        lines = conn.execute(select(ProductionLine.line_id, ProductionLine.line_code)).all()
        shifts = conn.execute(select(Shift.shift_id, Shift.client_id)).all()

    assert len({r.line_id for r in lines}) == len(lines)
    assert len({r.shift_id for r in shifts}) == len(shifts)


def test_defect_catalog_covers_every_code_per_client(seed_engine):
    from backend.orm import DefectTypeCatalog
    from backend.seed.scenarios import DEFECT_CODES, SCENARIOS as S

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        rows = conn.execute(select(DefectTypeCatalog.client_id, DefectTypeCatalog.defect_code)).all()

    by_client: dict = {}
    for r in rows:
        by_client.setdefault(r.client_id, set()).add(r.defect_code)

    assert set(by_client) == {s.client_id for s in S}
    for codes in by_client.values():
        assert codes == set(DEFECT_CODES)
```

Hashing is **argon2id** via `backend/auth/password.py` (`hash_password` / `verify_password`) — not bcrypt, and not passlib. `backend/auth/jwt.py` re-exports the same two under `get_password_hash` / `verify_password`; use `backend.auth.password` directly and do not introduce a third shim.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_seed/test_materialize.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.seed.writers_master`.

- [ ] **Step 3: Write `writers_master.py`**

One handler per master event. Every one supplies `created_at` (and `updated_at` where the column exists) from `event.at` — never omitted, never `func.now()`. Structure:

```python
"""Master-data writers: the entities operational rows point at.

Every row's created_at/updated_at comes from its event's instant. These
columns carry a server_default; letting them fall through would stamp all
45,000 rows at the seed-run instant, which is the defect this rebuild exists
to remove.
"""

from sqlalchemy import Connection

from backend.auth.security import hash_password
from backend.database import Base
from backend.seed import events as ev
from backend.seed.identity import IdMap, IntPkAllocator
from backend.seed.materialize import RowSink

#: Tables whose PK is an autoincrement integer the stream does not carry.
INT_PK_TABLES = ("PRODUCTION_LINE", "SHIFT", "PRODUCT", "EMPLOYEE")


def build_allocators(conn: Connection) -> dict[str, IntPkAllocator]:
    return {name: IntPkAllocator(conn, Base.metadata.tables[name]) for name in INT_PK_TABLES}


def handle(event, sink: RowSink, ids: IdMap, allocators: dict[str, IntPkAllocator]) -> bool:
    handler = _HANDLERS.get(type(event))
    if handler is None:
        return False
    handler(event, sink, ids, allocators)
    return True


def _client_created(e, sink, ids, allocators):
    sink.add(
        "CLIENT",
        {
            "client_id": e.client_id,
            "client_name": e.name,
            "client_type": e.client_type,
            "is_active": True,
            "created_at": e.at,
        },
    )


def _line_commissioned(e, sink, ids, allocators):
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
```

Continue with `_shift_defined` (`start_time`/`end_time` as `datetime.time(e.start_hour)` / `time(e.end_hour)`), `_product_defined`, `_employee_hired` (allocates `EMPLOYEE`, then emits `EMPLOYEE_CLIENT_ASSIGNMENT` and — when `e.line_id` is set — `EMPLOYEE_LINE_ASSIGNMENT` with `effective_date=e.at`), `_user_created` (`password_hash=hash_password(e.password)`, `client_id_assigned` = the comma-joined client list for scoped users and `None` for platform roles, matching the convention documented in `backend/tasks/daily_reports.py:143`), `_client_access_granted` (`USER_CLIENT_ASSIGNMENT`, `assigned_at=e.at`), `_defect_type_defined`, `_hold_reason_defined`, `_hold_status_defined`, `_threshold_set`, `_client_configured`.

`_user_created` needs the user's client list, which the event does not carry; look it up from `scenarios.USERS` by `user_id` rather than widening the event — the assignment already travels as its own `ClientAccessGranted` events, and duplicating it on `UserCreated` would let the two disagree.

End with the dispatch table:

```python
_HANDLERS = {
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
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && pytest tests/test_seed/test_materialize.py -v`
Expected: master tests PASS; the operations tests still FAIL on `writers_operations`.

- [ ] **Step 5: Commit**

```bash
git add backend/seed/writers_master.py backend/tests/test_seed/test_materialize.py
git commit -m "feat(seed): master-data writers with back-dated created_at

All six roles with verifiable bcrypt hashes, USER_CLIENT_ASSIGNMENT populated
so client scoping is demonstrable, and a full per-client defect catalog."
```

---

### Task 7: Operations writers

**Files:**
- Create: `backend/seed/writers_operations.py`
- Test: `backend/tests/test_seed/test_materialize.py` (extend)

**Interfaces:**
- Consumes: `RowSink`, `IdMap`, `Profile`, Task 1's operational events.
- Produces: `handle(event, sink, ids, profile) -> bool`; `reset() -> None`.

`WorkOrderReceived` must also set `planned_ship_date = e.required_date`, which lifts OTD's inference to its full-confidence tier instead of the 0.8 `required_date` fallback (`backend/calculations/otd.py:43`).

**Deviation from spec §12, stated explicitly.** The spec says the materializer "writes through" PR-C1's `record_hold_transition`. That function takes an ORM `HoldEntry` instance and calls `db.add(row)` — a per-row ORM path, which contradicts §4 and §10's Core-bulk-insert mandate and would need ORM objects for every hold. The materializer instead writes `HOLD_STATUS_TRANSITION` rows directly and Task 10 asserts they satisfy every invariant the recorder enforces: `transitioned_at` is a whole-second `datetime`, the opening row carries `from_status IS NULL`, and history is monotonic per hold. The binding contract is the shape of the data `active_as_of` reads, not the call site.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_seed/test_materialize.py`:

```python
def test_every_work_order_has_an_opening_transition(seed_engine):
    """60 of 100 orders had no chain at all in the old dataset, so 'what status
    was this on date D' was unanswerable -- the premise of PR-C."""
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        orders = {r.work_order_id for r in conn.execute(select(WorkOrder.work_order_id)).all()}
        opening = {
            r.work_order_id
            for r in conn.execute(
                select(WorkflowTransitionLog.work_order_id).where(WorkflowTransitionLog.from_status.is_(None))
            ).all()
        }

    assert orders
    assert orders - opening == set()


def test_transition_chains_strictly_increase_per_order(seed_engine):
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        rows = conn.execute(
            select(
                WorkflowTransitionLog.work_order_id,
                WorkflowTransitionLog.transition_id,
                WorkflowTransitionLog.transitioned_at,
            ).order_by(WorkflowTransitionLog.work_order_id, WorkflowTransitionLog.transition_id)
        ).all()

    last: dict = {}
    multi = 0
    for wo, _tid, at in rows:
        if wo in last:
            assert at > last[wo], f"{wo}: {at} does not follow {last[wo]}"
            multi += 1
        last[wo] = at

    assert multi > 0, "no order had more than one transition -- the chain assertion proved nothing"


def test_every_defect_detail_joins_to_its_clients_catalog(seed_engine):
    """All 80 live DEFECT_DETAIL rows say 'Stitching', a display name in no
    catalog, so the taxonomy DHU slices by is unjoinable."""
    from backend.orm import DefectDetail, DefectTypeCatalog

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(DefectDetail)).scalar_one()
        joined = conn.execute(
            select(func.count())
            .select_from(DefectDetail)
            .join(
                DefectTypeCatalog,
                (DefectDetail.defect_type == DefectTypeCatalog.defect_code)
                & (DefectDetail.client_id_fk == DefectTypeCatalog.client_id),
            )
        ).scalar_one()

    assert total > 0
    assert joined == total


def test_shift_date_is_never_midnight(seed_engine):
    """A midnight shift_date sits on a half-open range boundary and same-day
    queries return zero -- the date-boundary class fixed in #146."""
    from backend.orm import AttendanceEntry, ProductionEntry

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        for model in (ProductionEntry, AttendanceEntry):
            midnight = conn.execute(
                select(func.count()).select_from(model).where(func.strftime("%H:%M", model.shift_date) == "00:00")
            ).scalar_one()
            assert midnight == 0


def test_quality_entries_reference_real_work_orders(seed_engine):
    from backend.orm import QualityEntry

    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    with seed_engine.connect() as conn:
        orphans = conn.execute(
            select(func.count())
            .select_from(QualityEntry)
            .outerjoin(WorkOrder, QualityEntry.work_order_id == WorkOrder.work_order_id)
            .where(WorkOrder.work_order_id.is_(None))
        ).scalar_one()

    assert orphans == 0
```

`test_shift_date_is_never_midnight` uses `strftime`, which is SQLite-only. Task 10 runs this suite on MariaDB too, so replace it there with a dialect-portable expression (`sqlalchemy.func.hour(...)` on MySQL) or read the rows and assert in Python. Reading and asserting in Python is portable and this is a smoke-sized dataset — prefer that.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_seed/test_materialize.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.seed.writers_operations`.

- [ ] **Step 3: Write `writers_operations.py`**

Same dispatch shape as Task 6. Notes on the ones with a trap:

`_work_order_received` writes `WORK_ORDER` with `received_date=e.at`, `required_date=e.required_date`, `status` set to the enum's `RECEIVED` member, `origin=e.origin`, `priority=e.priority`, `style_model=e.style_model`, `created_at=e.at`, `updated_at=e.at`.

`_work_order_status_changed` writes one `WORKFLOW_TRANSITION_LOG` row with **`transitioned_at=e.at` supplied explicitly** — this column has a server default and omitting it is the original defect — and `transitioned_by=SUPERVISOR_USER_ID`. It also updates the parent order's `status`. A Core `insert()` cannot update an already-accumulated row, so keep the order's row dict in a local `dict[str, dict]` keyed by `work_order_id` and mutate it in place; the sink holds the same object, so the final flush writes the last status the stream reached. Add a comment saying so — it is the one place in the materializer where a row is mutated after being handed to the sink.

`_hold_opened` writes `HOLD_ENTRY` with `hold_date=e.at`, `hold_status` left at the value the first `HoldStatusChanged` will set, `hold_reason_category=e.reason_category`, `created_at=e.at`. Same in-place-mutation pattern for `hold_status` and `resume_date`.

`_hold_status_changed` writes `HOLD_STATUS_TRANSITION` with `transitioned_at=e.at` and `from_status=e.from_status` (explicitly `None` for the opening row — that is what `active_as_of`'s pre-history resolution reads).

Here are the three with a trap, in full. Everything else is a direct column map.

```python
def handle(event, sink: RowSink, ids: IdMap, profile: Profile) -> bool:
    handler = _HANDLERS.get(type(event))
    if handler is None:
        return False
    handler(event, sink, ids)
    return True


#: Rows already handed to the sink that a later event still amends. The sink
#: holds the SAME dict object, so mutating it here is what the final flush
#: writes. This is the only place in the materializer where a row changes
#: after being added -- a Core insert() cannot UPDATE an accumulated row, and
#: emitting a second WORK_ORDER row per status change would duplicate the
#: order. Keyed by business id, cleared per materialize() call.
_open_rows: dict[str, dict] = {}


def _work_order_received(e, sink, ids):
    row = {
        "work_order_id": e.work_order_id,
        "client_id": e.client_id,
        "style_model": e.style_model,
        "planned_quantity": e.planned_quantity,
        "received_date": e.at,
        "required_date": e.required_date,
        "priority": e.priority,
        "origin": e.origin,
        "status": WorkOrderStatus.RECEIVED,
        "created_at": e.at,
        "updated_at": e.at,
    }
    _open_rows[f"WO:{e.work_order_id}"] = row
    sink.add("WORK_ORDER", row)


def _work_order_status_changed(e, sink, ids):
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
            "transitioned_by": SUPERVISOR_USER_ID,
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


def _hold_status_changed(e, sink, ids):
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
            "transitioned_by": SUPERVISOR_USER_ID,
            "transitioned_at": e.at,
        },
    )
    hold = _open_rows[f"HOLD:{e.hold_entry_id}"]
    hold["hold_status"] = e.to_status
    hold["updated_at"] = e.at
    if e.to_status == "RESUMED":
        hold["resume_date"] = e.at
```

`materialize()` must clear `_open_rows` at the start of each call, or a second seed in the same process amends the previous run's rows. Add `writers_operations.reset()` and call it from `materialize()`; a test that seeds twice into two engines in one process is what catches this.

`_attendance_recorded`, `_production_recorded`, `_quality_inspected`, `_defects_found`, and `_downtime_logged` are direct column maps. Resolve `line_id`, `shift_id`, `product_id`, and `employee_id` through `ids.resolve(...)`. `production_entry_id` and `quality_entry_id` come from their events; the other three string PKs do not, so derive each from parts that are already unique:

- `ATTENDANCE_ENTRY.attendance_entry_id` = `f"{e.client_id}-AE-{e.shift_date:%Y%m%d}-{e.shift_id}-{e.employee_id}"` — one row per employee per shift per day.
- `DEFECT_DETAIL.defect_detail_id` = `f"{e.quality_entry_id}-{e.defect_code}"` — the generator emits each code at most once per inspection, so no counter is needed. If that ever stops holding, the PK collides loudly on insert rather than silently overwriting.
- `DOWNTIME_ENTRY.downtime_entry_id` = `f"{e.client_id}-DT-{e.shift_date:%Y%m%d}-{e.line_id}-{e.shift_id}"`.

`_downtime_logged` also writes `root_cause_category=e.root_cause_category` — the column exists and is what Q2 and the Q4 correlation block slice by.

- [ ] **Step 4: Run the tests**

Run: `cd backend && pytest tests/test_seed/ -v`
Expected: PASS, all of `test_materialize.py`.

- [ ] **Step 5: Commit**

```bash
git add backend/seed/writers_operations.py backend/tests/test_seed/test_materialize.py
git commit -m "feat(seed): operations writers with real transition chains

Every work order gets an opening transition and a strictly increasing chain
with transitioned_at supplied explicitly, hold history is monotonic, and
defect rows carry catalog codes that actually join."
```

---

### Task 8: Coverage contract

Spec §8: every `Base.metadata` table is either seeded or explicitly excluded with a written reason — the gate that would have caught `USER_CLIENT_ASSIGNMENT = 0` for the entire life of the client-scope feature. **S1b declares only what S1b seeds.** The completeness half — every metadata table has a home in one bucket or the other — turns on in S2, once every table has one. Declaring a table S1b does not seed would fail S1b's own gate.

**Files:**
- Create: `backend/seed/coverage.py`
- Test: `backend/tests/test_seed/test_coverage.py`

**Interfaces:**
- Consumes: `Base.metadata`.
- Produces: `SEEDED: FrozenSet[str]`, `NOT_SEEDED: Dict[str, str]`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_seed/test_coverage.py`:

```python
from datetime import date

from sqlalchemy import func, select

from backend.database import Base
from backend.seed.coverage import NOT_SEEDED, SEEDED
from backend.seed.generator import generate
from backend.seed.materialize import materialize
from backend.seed.profiles import SMOKE
from backend.seed.scenarios import SCENARIOS


def test_the_two_buckets_are_disjoint():
    assert SEEDED & set(NOT_SEEDED) == frozenset()


def test_every_declared_table_exists_in_the_schema():
    known = set(Base.metadata.tables)
    for name in SEEDED | set(NOT_SEEDED):
        assert name in known, f"{name} is declared but is not a table"


def test_not_seeded_holds_exactly_token_blacklist():
    """Spec section 7. Fabricated revoked tokens would demonstrate nothing and
    could only mislead."""
    assert set(NOT_SEEDED) == {"TOKEN_BLACKLIST"}


def test_every_exclusion_carries_a_reason():
    for name, reason in NOT_SEEDED.items():
        assert len(reason) > 30, f"{name}'s exclusion reason is not an explanation"


def test_every_seeded_table_actually_has_rows(seed_engine):
    """The gate. A table declared seeded but left empty is the failure this
    contract exists to make loud."""
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=date(2026, 8, 18))
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)

    empty = []
    with seed_engine.connect() as conn:
        for name in sorted(SEEDED):
            table = Base.metadata.tables[name]
            if conn.execute(select(func.count()).select_from(table)).scalar_one() == 0:
                empty.append(name)

    assert empty == []


def test_the_materializer_writes_nothing_outside_the_contract(seed_engine):
    """The other direction: a table written but not declared is a table the
    contract does not govern."""
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=date(2026, 8, 18))
    with seed_engine.begin() as conn:
        counts = materialize(conn, events, SMOKE)

    assert set(counts) - SEEDED == set()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && pytest tests/test_seed/test_coverage.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.seed.coverage`.

- [ ] **Step 3: Write `coverage.py`**

```python
"""What the seeder covers, and what it deliberately does not.

Mirrors backend/audit/registry.py's AUDITED_TABLES / EXCLUDED_TABLES pattern,
which is already guarded in tests. Nothing fails today when a feature ships
without demo data -- nine application sections have a UI, an API surface, and
zero rows. This contract is what turns that into a failing build.

S1b DECLARES ONLY WHAT S1b SEEDS. The completeness half of the gate -- every
Base.metadata table has a home in one bucket or the other -- turns on in S2,
once every table has one. Pre-declaring a table this seeder does not populate
would fail this file's own gate (spec section 8).
"""

from typing import Dict, FrozenSet

SEEDED: FrozenSet[str] = frozenset(
    {
        "CLIENT",
        "CLIENT_CONFIG",
        "KPI_THRESHOLD",
        "HOLD_REASON_CATALOG",
        "HOLD_STATUS_CATALOG",
        "DEFECT_TYPE_CATALOG",
        "USER",
        "USER_CLIENT_ASSIGNMENT",
        "EMPLOYEE",
        "EMPLOYEE_CLIENT_ASSIGNMENT",
        "EMPLOYEE_LINE_ASSIGNMENT",
        "PRODUCTION_LINE",
        "SHIFT",
        "PRODUCT",
        "WORK_ORDER",
        "WORKFLOW_TRANSITION_LOG",
        "HOLD_ENTRY",
        "HOLD_STATUS_TRANSITION",
        "ATTENDANCE_ENTRY",
        "PRODUCTION_ENTRY",
        "QUALITY_ENTRY",
        "DEFECT_DETAIL",
        "DOWNTIME_ENTRY",
    }
)

NOT_SEEDED: Dict[str, str] = {
    "TOKEN_BLACKLIST": (
        "JWT revocation ledger written when a user logs out. Fabricated revoked tokens "
        "would demonstrate nothing about the feature and could only mislead a reader into "
        "thinking sessions had been revoked that never existed."
    ),
}
```

Reconcile this list against `materialize.CLIENT_SCOPE_COLUMN` — they must name the same tables. If they diverge, one of them is wrong; fix the wrong one rather than loosening the test.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && pytest tests/test_seed/test_coverage.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/seed/coverage.py backend/tests/test_seed/test_coverage.py
git commit -m "feat(seed): coverage contract for the tables S1b seeds

Every declared table must have rows after a seed run. Completeness across all
of Base.metadata turns on in S2, once every table has a home."
```

---

### Task 9: CLI and production safety

**Files:**
- Create: `backend/seed/cli.py`
- Test: `backend/tests/test_seed/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `ALLOWLIST: FrozenSet[str]`; `class SeedError(RuntimeError)`; `seed(engine, *, client_ids, profile_name, seed_value, as_of, reset) -> dict[str, int]`; `main(argv=None) -> int`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_seed/test_cli.py`:

```python
from datetime import date

import pytest
from sqlalchemy import func, insert, select

from backend.database import Base
from backend.seed.cli import ALLOWLIST, SeedError, main, seed


def test_allowlist_is_exactly_the_four_scenario_clients():
    from backend.seed.scenarios import SCENARIOS

    assert ALLOWLIST == frozenset(s.client_id for s in SCENARIOS)


def test_a_client_outside_the_allowlist_is_refused(seed_engine):
    """The prod-safety guard: this seeder must be unable to touch a real
    tenant's rows even when handed its id."""
    with pytest.raises(SeedError) as exc:
        seed(
            seed_engine,
            client_ids=("REAL-CUSTOMER",),
            profile_name="smoke",
            seed_value=1234,
            as_of=date(2026, 8, 18),
            reset=False,
        )

    assert "REAL-CUSTOMER" in str(exc.value)


def test_reset_deletes_only_allowlisted_client_rows(seed_engine):
    """--reset must leave every other tenant untouched."""
    client = Base.metadata.tables["CLIENT"]
    with seed_engine.begin() as conn:
        conn.execute(
            insert(client),
            [{"client_id": "REAL-CUSTOMER", "client_name": "Real", "client_type": "Hourly Rate", "is_active": True}],
        )

    seed(
        seed_engine,
        client_ids=("DEMO-PIECE",),
        profile_name="smoke",
        seed_value=1234,
        as_of=date(2026, 8, 18),
        reset=True,
    )
    seed(
        seed_engine,
        client_ids=("DEMO-PIECE",),
        profile_name="smoke",
        seed_value=1234,
        as_of=date(2026, 8, 18),
        reset=True,
    )

    with seed_engine.connect() as conn:
        survivors = conn.execute(select(client.c.client_id).where(client.c.client_id == "REAL-CUSTOMER")).all()
        demo = conn.execute(select(func.count()).select_from(client).where(client.c.client_id == "DEMO-PIECE")).scalar_one()

    assert len(survivors) == 1
    assert demo == 1, "a second --reset seed must not duplicate the client row"


def test_the_same_inputs_produce_the_same_row_counts(seed_engine, tmp_path):
    """Determinism is what lets the dataset be asserted against rather than
    eyeballed (spec section 9)."""
    from sqlalchemy import create_engine

    from backend.db.migrate import upgrade_to_head

    first = seed(
        seed_engine,
        client_ids=tuple(ALLOWLIST),
        profile_name="smoke",
        seed_value=1234,
        as_of=date(2026, 8, 18),
        reset=False,
    )

    url = f"sqlite:///{tmp_path / 'second.db'}"
    upgrade_to_head(url)
    other = create_engine(url)
    second = seed(
        other,
        client_ids=tuple(ALLOWLIST),
        profile_name="smoke",
        seed_value=1234,
        as_of=date(2026, 8, 18),
        reset=False,
    )
    other.dispose()

    assert first == second


def test_as_of_is_required_to_be_explicit_or_defaulted_visibly(capsys):
    """A test that pins --as-of does not drift with the calendar; the CLI's
    default does. Assert the default is TODAY rather than a hardcoded date, so
    the seeder still anchors to its run date in production (spec section 9)."""
    from backend.seed.cli import build_parser

    args = build_parser().parse_args([])

    assert args.as_of == date.today()


def test_main_refuses_an_unknown_profile():
    assert main(["--profile", "gigantic"]) == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && pytest tests/test_seed/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: backend.seed.cli`.

- [ ] **Step 3: Write `cli.py`**

```python
"""Entry point for the demo seeder.

  python -m backend.seed.cli --profile full --as-of 2026-08-18

Prod-safety carries over from seed_sample_client unchanged (spec section 9):
INSERT-only, refuses any client not on the allowlist, never creates or drops
schema -- Alembic is the single schema mechanism -- and --reset deletes only
allowlisted clients' rows.
"""

import argparse
from datetime import date

from sqlalchemy import Engine, delete, select

from backend.audit import audit_suppressed
from backend.database import Base
from backend.seed.coverage import SEEDED
from backend.seed.generator import generate
from backend.seed.materialize import CLIENT_SCOPE_COLUMN, INSERT_ORDER, materialize
from backend.seed.profiles import PROFILES
from backend.seed.scenarios import SCENARIOS

ALLOWLIST = frozenset(s.client_id for s in SCENARIOS)


class SeedError(RuntimeError):
    """A guard refused the operation; the message is user-facing."""


def _reset(conn, client_ids: tuple[str, ...]) -> None:
    """Delete only these clients' rows, children first.

    Reverse INSERT_ORDER rather than a hand-written list: it is the same
    metadata topological sort, so the two can never drift apart.

    ATTENDANCE_HOUR_ALLOCATION has no tenant column of its own -- only a raw FK
    to ATTENDANCE_ENTRY -- and its ORM cascade only fires on session.delete(),
    not a Core delete. Without the subquery below it survives a reset as an
    orphan and collides on re-seed. (Salvaged from seed_sample_client.)
    """
    attendance = Base.metadata.tables["ATTENDANCE_ENTRY"]
    allocation = Base.metadata.tables.get("ATTENDANCE_HOUR_ALLOCATION")
    if allocation is not None:
        conn.execute(
            delete(allocation).where(
                allocation.c.attendance_entry_id.in_(
                    select(attendance.c.attendance_entry_id).where(attendance.c.client_id.in_(client_ids))
                )
            )
        )

    for name in reversed(INSERT_ORDER):
        if name not in SEEDED:
            continue
        column = CLIENT_SCOPE_COLUMN.get(name)
        if column is None:
            continue
        table = Base.metadata.tables[name]
        conn.execute(delete(table).where(table.c[column].in_(client_ids)))


@audit_suppressed()
def seed(
    engine: Engine,
    *,
    client_ids: tuple[str, ...],
    profile_name: str,
    seed_value: int,
    as_of: date,
    reset: bool,
) -> dict[str, int]:
    unknown = sorted(set(client_ids) - ALLOWLIST)
    if unknown:
        raise SeedError(
            f"refusing to seed client(s) not on the demo allowlist: {', '.join(unknown)}. "
            "This seeder is INSERT-only against demo tenants and must never touch a real one."
        )
    profile = PROFILES.get(profile_name)
    if profile is None:
        raise SeedError(f"unknown profile {profile_name!r}; known: {', '.join(sorted(PROFILES))}")

    scenarios = tuple(s for s in SCENARIOS if s.client_id in client_ids)
    events = generate(scenarios, profile, seed=seed_value, as_of=as_of)

    with engine.begin() as conn:
        if reset:
            _reset(conn, tuple(client_ids))
        return materialize(conn, events, profile)
```

Note the ordering trap: `KPI_THRESHOLD` is global (no client column), so `_reset` skips it, and a re-seed would therefore duplicate its rows. Handle it by making `_threshold_set` write with a deterministic `threshold_id` and having `_reset` delete exactly those ids. Write a test for the second-`--reset` case before implementing it — `test_reset_deletes_only_allowlisted_client_rows` already covers the CLIENT row; add the same assertion for `KPI_THRESHOLD`.

`build_parser()` declares `--client` (repeatable, default all of `ALLOWLIST`), `--profile` (default `full`), `--seed` (default `1234`), `--as-of` (`date.fromisoformat`, default `date.today()`), and `--reset`. `main()` catches `SeedError`, prints it to stderr, and returns `2`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && pytest tests/test_seed/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/seed/cli.py backend/tests/test_seed/test_cli.py
git commit -m "feat(seed): CLI with the allowlist, --reset, and audit suppression

Prod-safety carries over from seed_sample_client unchanged. --reset walks the
reverse of the derived insert order so the two cannot drift."
```

---

### Task 10: Gates — purity, isolation, dialect, and measured duration

**Files:**
- Create: `backend/tests/test_seed/test_seed_gates.py`
- Modify: `backend/tests/test_seed/test_purity.py`
- Modify: `.github/workflows/ci.yml` (add a step to the existing `mariadb-portability` job)

**Interfaces:**
- Consumes: everything.
- Produces: no application code — gates only.

- [ ] **Step 1: Write the failing gates**

`backend/tests/test_seed/test_seed_gates.py`:

```python
import ast
import subprocess
import sys
from pathlib import Path

import pytest

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"
WRITE_LAYER = ("materialize.py", "writers_master.py", "writers_operations.py")

BANNED_CALLS = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("date", "today"),
    ("func", "now"),
    ("func", "current_timestamp"),
}


def _banned_clock_calls(path: Path) -> list[str]:
    tree = ast.parse(path.read_text())
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        owner = node.func.value
        if isinstance(owner, ast.Name) and (owner.id, node.func.attr) in BANNED_CALLS:
            found.append(f"{path.name}:{node.lineno} {owner.id}.{node.func.attr}()")
    return found


@pytest.mark.parametrize("filename", WRITE_LAYER)
def test_the_write_layer_contains_no_clock(filename):
    """Every timestamp originates in its event. This is the defect that
    collapsed all 40 existing transition chains into a single instant."""
    assert _banned_clock_calls(SEED_DIR / filename) == []


def test_the_clock_guard_is_not_vacuous(tmp_path):
    """A guard that cannot fail proves nothing. Feed it a file that violates
    the rule and require a hit."""
    bad = tmp_path / "bad.py"
    bad.write_text("from datetime import datetime\nx = datetime.utcnow()\n")

    assert _banned_clock_calls(bad) != []


def test_importing_the_app_pulls_in_no_seed_module():
    """S1b changes no runtime behaviour: backend.seed must stay unreachable
    from the application's import graph, exactly as S1a verified."""
    code = (
        "import backend.main;"
        "import sys;"
        "print([m for m in sys.modules if m.startswith('backend.seed')])"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(SEED_DIR.parents[1]),
        check=True,
    )

    assert out.stdout.strip().endswith("[]")
```

Add to `test_purity.py` the assertion that the *generator* layer still imports no SQLAlchemy, and that the new `identity.py`/`materialize.py`/`writers_*.py` are explicitly **exempt** from that rule — list them so the exemption is deliberate rather than an oversight.

- [ ] **Step 2: Run the gates and watch the vacuity control fail first**

Run: `cd backend && pytest tests/test_seed/test_seed_gates.py -v`
Expected: `test_the_clock_guard_is_not_vacuous` must PASS on its own; the parametrized guards must PASS. To prove they are not vacuous against the real files, temporarily insert `datetime.utcnow()` into `writers_master.py`, re-run, watch it FAIL, then revert. Record that you did it in the commit message — a mutation proof you did not run is not a proof.

- [ ] **Step 3: Add the MariaDB run to CI**

In `.github/workflows/ci.yml`, inside the existing `mariadb-portability` job, after the schema is up, add:

```yaml
      - name: Seed suite on MariaDB
        # This repo's recurring bug class is MariaDB-only behaviour SQLite
        # tests cannot catch (SUM Integer->Decimal, DATETIME rounding, the
        # 307 scheme downgrade). The seeder writes 45,000 rows of exactly the
        # timestamp-sensitive data that class bites, so the gates run on both
        # dialects (spec section 8).
        env:
          SEED_TEST_DATABASE_URL: ${{ env.MARIADB_URL }}
        working-directory: backend
        run: pytest tests/test_seed/ -v --tb=short
```

Make `seed_engine` honour `SEED_TEST_DATABASE_URL` when it is set, falling back to the `tmp_path` SQLite URL otherwise. Confirm the job's existing env var name for the MariaDB URL before writing this — read the job rather than assuming `MARIADB_URL`.

- [ ] **Step 4: Measure the seed and record it**

Spec §10 commits to measuring rather than to a number. Run the FULL profile on both dialects and record wall-clock time and total row count:

```bash
cd backend && python -m timeit -n 1 -r 1 \
  "import subprocess; subprocess.run(['python','-m','backend.seed.cli','--profile','full','--as-of','2026-08-18','--reset'],check=True)"
```

Append the two numbers to this plan's Review section. If SQLite cold-start proves unacceptable for Render's boot auto-seed, the remedy is shipping a pre-built SQLite artifact — **not** reducing the dataset. Do not act on that here; record the number and raise it in S1c.

- [ ] **Step 5: Run the whole backend suite**

Run: `cd backend && pytest tests/ --tb=short -q` (foreground, `timeout: 900000`)
Expected: PASS, coverage ≥ 75%. The old seeder's tests still pass — nothing was retired in this PR.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/test_seed/ .github/workflows/ci.yml
git commit -m "test(seed): clock, isolation, and dual-dialect gates

AST guard proving the write layer holds no clock (mutation-verified by
inserting datetime.utcnow() into writers_master.py and watching it fail),
proof that backend.main still imports no seed module, and the seed suite
running on MariaDB where this repo's real bug class lives."
```

---

### Task 11: Scripted-event assertions against the seeded database

Spec §11 says the *full* assertion suite closes in S2. But S1b claims to be independently verifiable — "it either produces monotonic transition chains for every work order or it does not" — and seven of the ten assertions in spec §8 run entirely on data S1b writes. Deferring those would ship a dataset whose headline observables nobody checked, which is precisely how the current one rotted.

These run on the **FULL** profile: a 14-day smoke window cannot contain a 60-day-old hold or twelve monthly buckets. Keep them in their own file so the smoke-speed suite stays fast, and mark them `@pytest.mark.slow` if the repo has that marker.

**Files:**
- Create: `backend/tests/test_seed/test_narrative_dataset.py`

**Interfaces:**
- Consumes: `seed_engine`, `generate`, `materialize`, `FULL`.
- Produces: no application code.

**In scope here** (§8 rows 1, 2, 3, 7, 8, 9, 10). **Deferred to S2, with the reason:** "demotions co-located with scheduling-category downtime" needs `WorkOrderDemoted`, which S1b does not emit; "≥ 1 audit row for each of the 14 audited tables" needs `AUDIT_ENTRY` authoring, which spec §11 puts in S2; the coverage half of the absenteeism assertion needs `COVERAGE_ENTRY`, also S2. State those three exclusions in the module docstring so a reader can tell a deferral from an oversight.

- [ ] **Step 1: Write the failing assertions**

`backend/tests/test_seed/test_narrative_dataset.py`:

```python
"""Spec section 8's scripted-event assertions, against a FULL seeded database.

Three of the ten are deferred to S2 because S1b does not write their data:
demotions co-located with scheduling downtime (needs WorkOrderDemoted),
one audit row per audited table (needs AUDIT_ENTRY authoring), and the
floating-pool half of the absenteeism assertion (needs COVERAGE_ENTRY).
Everything else runs here -- a dataset whose headline observables nobody
checks is how the current one rotted.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from backend.orm import (
    AttendanceEntry,
    DefectDetail,
    HoldEntry,
    ProductionEntry,
    QualityEntry,
    WorkOrder,
)
from backend.seed.generator import _window_active, generate
from backend.seed.materialize import materialize
from backend.seed.profiles import FULL
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 18)


@pytest.fixture(scope="module")
def full_db(seed_engine_module):
    events = generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF)
    with seed_engine_module.begin() as conn:
        materialize(conn, events, FULL)
    return seed_engine_module


def _dhu(conn, client_id, months):
    """Defects per hundred units over a set of (year, month) buckets."""
    rows = conn.execute(
        select(QualityEntry.shift_date, QualityEntry.total_defects_count, QualityEntry.units_inspected).where(
            QualityEntry.client_id == client_id
        )
    ).all()
    defects = units = 0
    for shift_date, d, u in rows:
        if (shift_date.year, shift_date.month) in months:
            defects += d
            units += u
    return (defects * 100 / units) if units else 0.0


def test_demo_piece_dhu_spikes_in_its_crisis_window(full_db):
    scenario = next(s for s in SCENARIOS if s.client_id == "DEMO-PIECE")
    crisis, baseline = set(), set()
    day = AS_OF - timedelta(days=364)
    while day <= AS_OF:
        bucket = crisis if _window_active(scenario, day, AS_OF, "supplier_quality_crisis") else baseline
        bucket.add((day.year, day.month))
        day += timedelta(days=1)
    # A month straddling the window boundary lands in both; drop those so the
    # comparison is between clean populations.
    crisis, baseline = crisis - baseline, baseline - crisis

    with full_db.connect() as conn:
        assert _dhu(conn, "DEMO-PIECE", crisis) >= 2 * _dhu(conn, "DEMO-PIECE", baseline)


def test_at_least_three_holds_are_aged_past_sixty_days(full_db):
    cutoff = AS_OF - timedelta(days=60)
    with full_db.connect() as conn:
        chronic = conn.execute(
            select(func.count())
            .select_from(HoldEntry)
            .where(HoldEntry.resume_date.is_(None), HoldEntry.hold_date < cutoff)
        ).scalar_one()

    assert chronic >= 3


def test_every_client_has_twelve_distinct_months_of_production_and_quality(full_db):
    with full_db.connect() as conn:
        for scenario in SCENARIOS:
            for model in (ProductionEntry, QualityEntry):
                dates = conn.execute(
                    select(model.shift_date).where(model.client_id == scenario.client_id)
                ).scalars().all()
                months = {(d.year, d.month) for d in dates}

                assert len(months) >= 12, f"{scenario.client_id}/{model.__name__}: {len(months)} months"


def test_demo_hourly_maintenance_downtime_dominates_inside_its_window(full_db):
    from collections import Counter

    from backend.orm import DowntimeEntry

    scenario = next(s for s in SCENARIOS if s.client_id == "DEMO-HOURLY")
    with full_db.connect() as conn:
        rows = conn.execute(
            select(DowntimeEntry.shift_date, DowntimeEntry.downtime_reason, DowntimeEntry.downtime_duration_minutes)
            .where(DowntimeEntry.client_id == "DEMO-HOURLY")
        ).all()

    inside = Counter()
    for shift_date, reason, minutes in rows:
        if _window_active(scenario, shift_date.date(), AS_OF, "equipment_reliability_decline"):
            inside[reason] += minutes

    others = sum(v for k, v in inside.items() if k != "MAINTENANCE")

    assert inside["MAINTENANCE"] >= 2 * others


def test_demo_hybrid_absenteeism_peaks_inside_its_window(full_db):
    scenario = next(s for s in SCENARIOS if s.client_id == "DEMO-HYBRID")
    with full_db.connect() as conn:
        rows = conn.execute(
            select(AttendanceEntry.shift_date, AttendanceEntry.is_absent).where(
                AttendanceEntry.client_id == "DEMO-HYBRID"
            )
        ).all()

    inside = [a for d, a in rows if _window_active(scenario, d.date(), AS_OF, "labor_disruption")]
    outside = [a for d, a in rows if not _window_active(scenario, d.date(), AS_OF, "labor_disruption")]

    assert inside and outside
    assert sum(bool(a) for a in inside) / len(inside) > sum(bool(a) for a in outside) / len(outside)


def test_otd_dips_below_eighty_percent_for_at_least_one_client_and_never_for_sample_ref(full_db):
    """Spec section 8 row 3. SAMPLE_REF is the healthy control -- if it dips,
    the dashboards are uniformly red and the thresholds read as broken."""
    from backend.calculations.otd import calculate_otd_metrics  # confirm the real entry point

    with full_db.connect() as conn:
        delivered = conn.execute(
            select(WorkOrder.client_id, WorkOrder.required_date, WorkOrder.actual_delivery_date).where(
                WorkOrder.actual_delivery_date.isnot(None)
            )
        ).all()

    by_client: dict = {}
    for client_id, required, actual in delivered:
        on_time, total = by_client.setdefault(client_id, [0, 0])
        by_client[client_id] = [on_time + (1 if actual <= required else 0), total + 1]

    assert by_client, "no work order has a delivery date -- OTD is undemonstrable"
    rates = {c: on / total for c, (on, total) in by_client.items() if total}

    assert min(rates.values()) < 0.80
    assert rates["SAMPLE_REF"] >= 0.80


def test_the_priority_adherence_denominator_is_non_empty_and_incomplete(full_db):
    """Spec section 3 decision 6: orders with no priority are excluded from the
    denominator and their share is published as a coverage figure. A dataset
    where every order has a priority cannot demonstrate the exclusion works."""
    with full_db.connect() as conn:
        total = conn.execute(select(func.count()).select_from(WorkOrder)).scalar_one()
        with_priority = conn.execute(
            select(func.count()).select_from(WorkOrder).where(WorkOrder.priority.isnot(None))
        ).scalar_one()

    assert with_priority > 0
    assert with_priority < total


def test_defect_rows_exist_for_every_client(full_db):
    with full_db.connect() as conn:
        clients = conn.execute(select(func.distinct(DefectDetail.client_id_fk))).scalars().all()

    assert set(clients) == {s.client_id for s in SCENARIOS}
```

Add a module-scoped `seed_engine_module` fixture beside `seed_engine` in `conftest.py` — same body, `scope="module"`, using `tmp_path_factory`. A FULL seed per test would run this file's seeder eight times.

The OTD assertion above computes the ratio inline rather than calling the production calculator, because `calculate_otd_metrics`'s real signature is unverified. **Before implementing, read `backend/calculations/otd.py` and call the production function if it can be driven from a plain session** — an assertion against a reimplementation of the metric proves the seeder agrees with the test author, not with the application. Only fall back to the inline computation if the calculator needs a request context, and say so in a comment.

- [ ] **Step 2: Run them and watch each fail for its own reason**

Run: `cd backend && pytest tests/test_seed/test_narrative_dataset.py -v` (foreground, `timeout: 900000`)
Expected: failures naming the observable, not import errors. A test that fails because a fixture is missing has proved nothing — fix the fixture first, then read each failure.

- [ ] **Step 3: Tune the generator until every assertion holds**

Do **not** weaken an assertion to match the data. The assertions are the specification of what the demo must show; the generator's constants (`DEFECT_CRISIS_SCALE`, `DOWNTIME_DECLINE_SCALE`, `ATTENDANCE_DISRUPTION_SCALE`, `HOLD_RATE_*`, the root-cause pools, and the delivery-lateness draw) are the knobs. If an assertion cannot be satisfied by any constant, that is a finding about the narrative design — write it down and raise it rather than lowering the bar.

OTD needs a lateness mechanism that does not exist yet: `actual_delivery_date` is currently the SHIPPED transition instant, which bears no relation to `required_date`. Add a per-order lateness draw in the generator — biased late inside each client's narrative window and never late for `SAMPLE_REF` — so the OTD dip is caused by the story rather than by accident.

- [ ] **Step 4: Re-run the seed suite, then the whole backend suite**

Run: `cd backend && pytest tests/test_seed/ -v` then `cd backend && pytest tests/ --tb=short -q` (both foreground, `timeout: 900000`)
Expected: PASS, coverage ≥ 75%. The old seeder's tests still pass — nothing is retired in this PR.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_seed/test_narrative_dataset.py backend/tests/test_seed/conftest.py backend/seed/
git commit -m "test(seed): spec section 8 assertions against a FULL seeded database

Seven of the ten run on data S1b writes; the other three are deferred to S2
with the reason recorded in the module docstring. Adds the per-order lateness
draw OTD needs so the dip is caused by the narrative, not by accident."
```

---

## Review

*(Filled in as the plan executes.)*

- Seed duration, SQLite / FULL: _____
- Seed duration, MariaDB / FULL: _____
- Total rows written, FULL: _____
- Deviations from this plan and why: _____

---

## Carried into S1c (do not do here)

1. Repoint `backend/bootstrap/lifecycle.py:183` **and its `EXPECTED_CLIENTS` set on line 138** — the set still names `ACME-MFG / TEXTILE-PRO / FASHION-WORKS / QUALITY-STITCH / GLOBAL-APPAREL`. Miss it and every boot decides demo data is incomplete and calls the destructive `rebuild_schema()`, in a loop.
2. `scripts/deploy.sh:145` — `python3 ../backend/scripts/init_demo_database.py`. No test covers deploy scripts; a miss breaks a deploy.
3. `.github/workflows/ci.yml:86` — the e2e-sqlite seeding step, and lines 240–248 whose smoke URLs pass `client_id=ACME-MFG`.
4. `deploy/smoke/compose-smoke.sh:25` — `CLIENT_ID="${CLIENT_ID:-ACME-MFG}"`, in the required `compose-stack-smoke` check.
5. `frontend/e2e/helpers.ts` plus `auth.spec.ts`, `attendance-labor-allocation.spec.ts`, `database-config.spec.ts` — old credentials and `client_id: 'ACME-MFG'`.
6. `backend/tests/test_demo_seed_gate.py` — rewrite against the new entry point. **This guards the Run-7 C-1 remediation** (an ungated `drop_all` could wipe a real database). There is an obvious wrong way to make it pass during a retirement: asserting the old import no longer exists. The gate must still prove that with `DEMO_MODE` off the seeder returns before touching the database.
7. `backend/tests/test_audit/test_suppression_sites.py` — repoint both seeder tests to `backend.seed.cli.seed`. Keep the contract at **zero audit rows**: S1b writes no `AUDIT_ENTRY`, and it is S2 that starts authoring back-dated audit rows explicitly, at which point the contract changes to "every audit row is one the materializer authored" rather than "there are none".
8. Delete `backend/scripts/init_demo_database.py` (2,043), `_seed_operations.py` (621), `seed_sample_client.py` (379), and the `_seed_*` helpers, plus `tests/test_scripts/test_init_demo_database.py` and `test_seed_sample_client.py`. Leave `test_create_admin.py` alone — unrelated.
9. Comment-only references in `backend/services/csv_upload_processor.py` and `backend/pivot/hooks.py`.
10. Document the six credentials and `DEMO_PASSWORD` in `docs/deployment/vm-deploy-runbook.md`.
11. Spec §13 notes it: the window ends at seed-run date, so an un-reseeded VM goes stale exactly as it has now. Raise scheduling a periodic re-seed as a runbook follow-up.
