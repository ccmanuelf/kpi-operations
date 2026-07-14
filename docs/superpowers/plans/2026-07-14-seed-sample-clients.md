# Seed Sample Demo Clients Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A prod-safe, INSERT-only CLI script `backend/scripts/seed_sample_client.py` that populates a fixed allowlist of DEMO clients with a full, credible, UI-functional dataset (master data, config/catalog layer, capacity planning-scheduling graph, work-order/workflow/hold variety, 90 days of daily Operations data, and a simulation scenario) so the app can be validated as a real user across Planning / Operations / Simulation.

**Architecture:** One focused script mirroring `backend/scripts/create_admin.py` (own engine, `ensure_migrated` guard, `main(argv)->int`, fail-fast, argv/secret-safe). It reuses `backend/db/factories.py::TestDataFactory` for transactional entities and mirrors the credible-value formulas + config/catalog blocks of `backend/scripts/init_demo_database.py`. Every section helper is idempotent (skip-if-exists); `--reset` does a scoped FK-safe per-client delete via a single complete ordered table list. A hard ALLOWLIST + a static-scan test guarantee it can never drop/create schema or touch a non-demo client.

**Tech Stack:** Python 3.11, SQLAlchemy 2.0 ORM, argparse, pytest (template-clone `db_session` fixture), MariaDB + SQLite portable (ORM inserts only — no dialect SQL).

## Global Constraints

- **Allowlist only.** `ALLOWLIST = frozenset({"DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID", "SAMPLE_REF"})`. Any `--client` not in it → `SeedError` → exit 1, zero writes. Default (no `--client`) seeds `("DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID")` only.
- **Never touch schema.** No `Base.metadata.create_all`, `drop_all`, `rebuild_schema`; no reference to `DEMO_MODE`. `ensure_migrated(engine)` requires `alembic_version` + `CLIENT` + `USER` tables or exits 1. Enforced by a static source-scan test.
- **No credential/user writes.** The script creates no `User` rows and never sets `password_hash`. `entered_by`/`inspector_id` resolve to an existing user (client-scoped operator, else admin); `SeedError` if none.
- **Prod-safe secrets.** `DATABASE_URL` is read from env (default `sqlite:///database/kpi_platform.db`) and NEVER echoed, even on parse failure.
- **Determinism.** Value RNG is seeded from `hashlib.sha256` of a stable string key (NOT builtin `hash()`, which is per-process salted), so generated values are stable across runs/processes.
- **Idempotent.** Every section helper is skip-if-exists; a second run without `--reset` adds zero rows. `--reset` deletes only the target client's rows (children-first) and leaves the `CLIENT` row and all other clients intact.
- **ClientType stores the human value string** (`"Piece Rate"`, not `PIECE_RATE`) — always pass the `ClientType` enum member to the ORM, which serializes via `values_callable`.
- **Naming traps:** `JOB.client_id_fk` and `DEFECT_DETAIL.client_id_fk` (not `client_id`); `Employee.client_id_assigned` (Text, comma-list — DEMO employees are single-client); two line concepts (`PRODUCTION_LINE` operational vs `capacity_production_lines`).
- **Deterministic client-scoped PKs — never use `TestDataFactory`'s auto-generated string PKs in this prod script.** Several `TestDataFactory` methods mint their string primary key from a process-local `_next_id("PE"|"QE"|"DD"|"DT"|"ATT"|"HOLD"|"JOB"|...)` counter that restarts every process, causing PK collisions across separate `--client` invocations or against an already-populated prod DB (this is exactly the Task-2 defect-catalog bug). So for every entity whose PK is an app-generated string — `Job` (`job_id`), `HoldEntry` (`hold_entry_id`), `ProductionEntry` (`production_entry_id`), `QualityEntry` (`quality_entry_id`), `DefectDetail` (`defect_detail_id`), `DowntimeEntry` (`downtime_entry_id`), `AttendanceEntry` (`attendance_entry_id`) — either pass an explicit deterministic id `f"<PREFIX>-{client_id}-{seq:04d}"` (when the factory exposes the id param, e.g. `create_job(job_id=...)`) or construct the ORM object directly (when it does not). `TestDataFactory` is fine ONLY for DB-autoincrement PKs (`Shift`, `Product`, `Employee`, `WorkflowTransitionLog`, assignments) or where an explicit unique code is already passed. A cross-process regression test (`TestDataFactory.reset_counters()` between clients) must assert no PK collision for the daily-data entities.
- Backend verify: `pytest tests/` from `backend/` (coverage gate ≥75%). Files under 500 lines. Conventional commits. One expected status code per assertion (no permissive `in [...]`).

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/scripts/seed_sample_client.py` | Create | The script: CLI, safety guards, `CLIENT_SPECS`, RNG, section helpers, `seed_client` orchestrator, `reset_client_data`, `RESET_TABLE_ORDER`, `main`. |
| `backend/scripts/_seed_credible.py` | Create (only if the script nears ~500 lines) | Optional sibling holding the credible-value helpers (production/quality/downtime/attendance value math) to keep the main file focused. Default: keep everything in one file until it approaches the limit. |
| `backend/tests/test_scripts/test_seed_sample_client.py` | Create | All test groups: safety (allowlist/static-scan/ensure_migrated), per-section counts, workflow completeness, hold-chain, credibility bounds, idempotency, scoped reset, CLI smoke. |

Reference files to READ while implementing (do not modify): `backend/scripts/create_admin.py` (skeleton), `backend/db/factories.py` (`TestDataFactory` signatures), `backend/scripts/init_demo_database.py` (credible-value + config/catalog + capacity blocks — line anchors given per task), the ORM files under `backend/orm/` and `backend/orm/capacity/`, and `backend/tests/test_scripts/test_create_admin.py` (CLI-test pattern), `backend/tests/conftest.py` (`db_session` fixture).

---

### Task 1: Script skeleton — CLI, safety guards, specs, orchestrator, reset scaffold

**Files:**
- Create: `backend/scripts/seed_sample_client.py`
- Test: `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces:**
- Produces (later tasks consume these exact signatures):
  - `ALLOWLIST: frozenset[str]`, `DEFAULT_CLIENTS: tuple[str, ...]`
  - `class SeedError(RuntimeError)`
  - `@dataclass(frozen=True) class ClientSpec: client_id: str; client_name: str; client_type: ClientType; num_employees: int; num_work_orders: int`
  - `CLIENT_SPECS: dict[str, ClientSpec]` (keys = the 3 DEMO ids + `SAMPLE_REF`)
  - `ensure_migrated(engine: Engine) -> None`
  - `rng_for(*key_parts: object) -> random.Random` — deterministic per key
  - `resolve_entered_by(session: Session, client_id: str) -> str`
  - `seed_client(session: Session, spec: ClientSpec, days: int) -> None` — orchestrator (Task 1 wires only `seed_client_row`; later tasks append their calls in FK order)
  - `seed_client_row(session: Session, spec: ClientSpec) -> None` — idempotent client insert
  - `reset_client_data(session: Session, client_id: str) -> None` — iterates `RESET_TABLE_ORDER`
  - `RESET_TABLE_ORDER: list[tuple[type, str]]` — complete children-first (ORM class, client-column) list
  - `main(argv: Optional[list[str]] = None) -> int`

- [ ] **Step 1: Write the failing safety tests**

Create `backend/tests/test_scripts/test_seed_sample_client.py`:

```python
import subprocess
import sys
from pathlib import Path

import pytest

from backend.orm import Client
from backend.orm.client import ClientType
from backend.scripts import seed_sample_client as seed


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_SRC = (REPO_ROOT / "backend/scripts/seed_sample_client.py").read_text(encoding="utf-8")


def test_allowlist_is_exactly_the_demo_clients():
    assert seed.ALLOWLIST == frozenset({"DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID", "SAMPLE_REF"})
    assert set(seed.DEFAULT_CLIENTS) == {"DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID"}


def test_prod_safety_static_scan():
    # The script must never be able to drop/create schema or gate on DEMO_MODE.
    for forbidden in ("drop_all", "create_all", "rebuild_schema", "DEMO_MODE"):
        assert forbidden not in SCRIPT_SRC, f"forbidden token {forbidden!r} present in seed script"


def test_main_refuses_non_allowlist_client(capsys):
    rc = seed.main(["--client", "REAL-PROD-CLIENT"])
    assert rc == 1
    assert "allowlist" in capsys.readouterr().err.lower()


def test_ensure_migrated_rejects_empty_db(tmp_path):
    from sqlalchemy import create_engine

    engine = create_engine(f"sqlite:///{tmp_path/'empty.db'}")
    try:
        with pytest.raises(seed.SeedError):
            seed.ensure_migrated(engine)
    finally:
        engine.dispose()


def test_rng_is_deterministic_across_calls():
    a = [seed.rng_for("DEMO-PIECE", "prod", 3).random() for _ in range(1)]
    b = [seed.rng_for("DEMO-PIECE", "prod", 3).random() for _ in range(1)]
    assert a == b
    assert seed.rng_for("DEMO-PIECE", "prod", 3).random() != seed.rng_for("DEMO-HOURLY", "prod", 3).random()


def test_seed_client_row_idempotent(db_session):
    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client_row(db_session, spec)
    seed.seed_client_row(db_session, spec)  # second call must be a no-op
    db_session.commit()
    rows = db_session.query(Client).filter(Client.client_id == "DEMO-PIECE").all()
    assert len(rows) == 1
    assert rows[0].client_type == ClientType.PIECE_RATE
    assert rows[0].client_name == spec.client_name
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q`
Expected: FAIL — `ModuleNotFoundError: backend.scripts.seed_sample_client` (module not created yet).

- [ ] **Step 3: Write the script skeleton**

Read `backend/scripts/create_admin.py` first and mirror its `sys.path` bootstrap, engine/`main` structure, and `DATABASE_URL` handling verbatim. Create `backend/scripts/seed_sample_client.py`:

```python
"""
Prod-safe demo-client seeder. INSERT-only; refuses any client not on a fixed
allowlist; never creates/drops schema (Alembic is the single schema mechanism).

Populates DEMO clients with a full, credible dataset (master data, config/catalog
layer, capacity planning-scheduling graph, work-order/workflow/hold variety, daily
Operations data, a simulation scenario) so the app can be validated as a real user.

VM invocation:
  docker compose -f docker-compose.prod.yml exec backend \\
      python -m backend.scripts.seed_sample_client --days 90
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import argparse  # noqa: E402
import hashlib  # noqa: E402
import random  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import TYPE_CHECKING, Optional  # noqa: E402

from sqlalchemy import create_engine, inspect  # noqa: E402
from sqlalchemy.exc import ArgumentError, NoSuchModuleError, OperationalError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from backend.orm.client import Client, ClientType  # noqa: E402

if TYPE_CHECKING:
    from sqlalchemy import Engine  # noqa: E402


class SeedError(RuntimeError):
    """A guard refused the operation; the message is user-facing."""


ALLOWLIST = frozenset({"DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID", "SAMPLE_REF"})
DEFAULT_CLIENTS = ("DEMO-PIECE", "DEMO-HOURLY", "DEMO-HYBRID")


@dataclass(frozen=True)
class ClientSpec:
    client_id: str
    client_name: str
    client_type: ClientType
    num_employees: int
    num_work_orders: int


CLIENT_SPECS: dict[str, ClientSpec] = {
    "DEMO-PIECE": ClientSpec("DEMO-PIECE", "Demo Piece-Rate Garments", ClientType.PIECE_RATE, 8, 8),
    "DEMO-HOURLY": ClientSpec("DEMO-HOURLY", "Demo Hourly Assembly", ClientType.HOURLY_RATE, 8, 8),
    "DEMO-HYBRID": ClientSpec("DEMO-HYBRID", "Demo Hybrid Works", ClientType.HYBRID, 8, 8),
    "SAMPLE_REF": ClientSpec("SAMPLE_REF", "SAMPLE_REF", ClientType.PIECE_RATE, 8, 8),
}


def rng_for(*key_parts: object) -> random.Random:
    """Deterministic RNG keyed on a stable sha256 of the parts (NOT builtin
    hash(), which is per-process salted for strings)."""
    key = "|".join(str(p) for p in key_parts).encode("utf-8")
    seed_int = int.from_bytes(hashlib.sha256(key).digest()[:8], "big")
    return random.Random(seed_int)


def ensure_migrated(engine: "Engine") -> None:
    """Refuse to touch a database Alembic hasn't built (never creates schema)."""
    insp = inspect(engine)
    if not (insp.has_table("alembic_version") and insp.has_table("CLIENT") and insp.has_table("USER")):
        raise SeedError(
            "database is not migrated (alembic_version/CLIENT/USER missing). "
            "Start the backend once (its entrypoint runs `alembic upgrade head`), then retry."
        )


def resolve_entered_by(session: Session, client_id: str) -> str:
    """Resolve a real USER.user_id for entered_by/inspector_id: prefer a
    client-scoped operator, else any admin. No users are created."""
    from backend.orm.user import User

    scoped = (
        session.query(User)
        .filter(User.client_id_assigned.isnot(None), User.client_id_assigned.contains(client_id))
        .first()
    )
    if scoped is not None:
        return scoped.user_id
    admin = session.query(User).filter(User.role == "admin").first()
    if admin is not None:
        return admin.user_id
    raise SeedError(f"no usable entered_by user for {client_id} (need a client operator or an admin).")


def seed_client_row(session: Session, spec: ClientSpec) -> None:
    """Idempotent CLIENT insert."""
    if session.get(Client, spec.client_id) is not None:
        return
    session.add(
        Client(
            client_id=spec.client_id,
            client_name=spec.client_name,
            client_type=spec.client_type,
            is_active=1,
        )
    )
    session.flush()


# Children-first ordered (ORM class, client-column) list for scoped reset.
# Completed here so reset is correct as later tasks bring tables online
# (deleting zero rows for a not-yet-seeded table is harmless). NEVER includes CLIENT.
def _reset_table_order() -> list[tuple[type, str]]:
    from backend.orm import (
        AttendanceEntry,
        DefectDetail,
        DowntimeEntry,
        HoldEntry,
        Job,
        ProductionEntry,
        QualityEntry,
        Shift,
        Product,
        WorkOrder,
        WorkflowTransitionLog,
    )
    from backend.orm.employee import Employee
    from backend.orm.employee_line_assignment import EmployeeLineAssignment
    from backend.orm.employee_client_assignment import EmployeeClientAssignment
    from backend.orm.production_line import ProductionLine
    from backend.orm.client_config import ClientConfig
    from backend.orm.kpi_threshold import KPIThreshold
    from backend.orm.alert import AlertConfig
    from backend.orm.hold_status_catalog import HoldStatusCatalog
    from backend.orm.hold_reason_catalog import HoldReasonCatalog
    from backend.orm.defect_type_catalog import DefectTypeCatalog
    from backend.orm.simulation_scenario import SimulationScenario
    from backend.orm.capacity import (
        CapacityKPICommitment,
        CapacityScheduleDetail,
        CapacitySchedule,
        CapacityComponentCheck,
        CapacityAnalysis,
        CapacityStockSnapshot,
        CapacityBOMDetail,
        CapacityBOMHeader,
        CapacityProductionStandard,
        CapacityOrder,
        CapacityScenario,
        CapacityCalendar,
        CapacityProductionLine,
    )

    return [
        (DefectDetail, "client_id_fk"),
        (QualityEntry, "client_id"),
        (ProductionEntry, "client_id"),
        (DowntimeEntry, "client_id"),
        (AttendanceEntry, "client_id"),
        (WorkflowTransitionLog, "client_id"),
        (HoldEntry, "client_id"),
        (Job, "client_id_fk"),
        (WorkOrder, "client_id"),
        (CapacityKPICommitment, "client_id"),
        (CapacityScheduleDetail, "client_id"),
        (CapacitySchedule, "client_id"),
        (CapacityComponentCheck, "client_id"),
        (CapacityAnalysis, "client_id"),
        (CapacityStockSnapshot, "client_id"),
        (CapacityBOMDetail, "client_id"),
        (CapacityBOMHeader, "client_id"),
        (CapacityProductionStandard, "client_id"),
        (CapacityOrder, "client_id"),
        (CapacityScenario, "client_id"),
        (CapacityCalendar, "client_id"),
        (CapacityProductionLine, "client_id"),
        (EmployeeLineAssignment, "client_id"),
        (EmployeeClientAssignment, "client_id"),
        (Employee, "client_id_assigned"),
        (Shift, "client_id"),
        (Product, "client_id"),
        (ProductionLine, "client_id"),
        (SimulationScenario, "client_id"),
        (AlertConfig, "client_id"),
        (KPIThreshold, "client_id"),
        (ClientConfig, "client_id"),
        (HoldStatusCatalog, "client_id"),
        (HoldReasonCatalog, "client_id"),
        (DefectTypeCatalog, "client_id"),
    ]


RESET_TABLE_ORDER = _reset_table_order()


def reset_client_data(session: Session, client_id: str) -> None:
    """Delete ONLY this client's rows, children-first. Leaves CLIENT + other clients intact."""
    for cls, col in RESET_TABLE_ORDER:
        session.query(cls).filter(getattr(cls, col) == client_id).delete(synchronize_session=False)
    session.flush()


def seed_client(session: Session, spec: ClientSpec, days: int) -> None:
    """Orchestrator — seed one client in FK order. Later tasks append their
    section calls here (catalogs/config → master data → capacity → work orders
    → holds → daily data → simulation)."""
    seed_client_row(session, spec)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="seed_sample_client",
        description="Seed DEMO clients with a full credible dataset (INSERT-only, allowlist-guarded).",
    )
    parser.add_argument("--client", default=None, help=f"one of {sorted(ALLOWLIST)}; default = the 3 DEMO-* clients")
    parser.add_argument("--days", type=int, default=90, help="days of daily Operations data (default 90)")
    parser.add_argument("--reset", action="store_true", help="delete this client's existing rows before seeding")
    args = parser.parse_args(argv)

    if args.client is not None and args.client not in ALLOWLIST:
        print(f"ERROR: {args.client!r} is not on the demo allowlist {sorted(ALLOWLIST)}; refusing.", file=sys.stderr)
        return 1
    targets = [args.client] if args.client else list(DEFAULT_CLIENTS)

    database_url = os.getenv("DATABASE_URL", "sqlite:///database/kpi_platform.db")
    try:
        engine = create_engine(database_url)
    except (ArgumentError, NoSuchModuleError):
        print("ERROR: invalid DATABASE_URL (unparseable URL or unknown dialect); check the environment/.env.",
              file=sys.stderr)
        return 1

    try:
        ensure_migrated(engine)
        with Session(engine) as session:
            for client_id in targets:
                spec = CLIENT_SPECS[client_id]
                if args.reset:
                    reset_client_data(session, client_id)
                seed_client(session, spec, args.days)
                session.commit()
                print(f"Seeded {client_id} ({args.days} days).")
    except SeedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OperationalError as exc:
        print(f"ERROR: database unreachable: {exc.orig}", file=sys.stderr)
        return 1
    finally:
        engine.dispose()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Also create an empty `backend/tests/test_scripts/__init__.py` only if the directory does not already have one (check first: `ls backend/tests/test_scripts/__init__.py`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q`
Expected: PASS (6 tests). If `backend.orm.capacity` import names differ, read `backend/orm/capacity/__init__.py` and fix the import names in `_reset_table_order` to match exactly.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_sample_client.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): prod-safe demo-client seeder skeleton (allowlist, guards, reset scaffold)"
```

---

### Task 2: Catalogs + config layer

**Files:**
- Modify: `backend/scripts/seed_sample_client.py`
- Test: `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces:**
- Produces: `seed_catalogs(session, client_id) -> None`, `seed_config_layer(session, client_id) -> None`. Both idempotent; wired into `seed_client` right after `seed_client_row`.

- [ ] **Step 1: Write the failing test**

Append to the test file:

```python
def test_catalogs_and_config_seeded_and_idempotent(db_session):
    from backend.orm.hold_status_catalog import HoldStatusCatalog
    from backend.orm.hold_reason_catalog import HoldReasonCatalog
    from backend.orm.defect_type_catalog import DefectTypeCatalog
    from backend.orm.client_config import ClientConfig
    from backend.orm.kpi_threshold import KPIThreshold
    from backend.orm.alert import AlertConfig

    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client_row(db_session, spec)
    for _ in range(2):  # idempotent
        seed.seed_catalogs(db_session, "DEMO-PIECE")
        seed.seed_config_layer(db_session, "DEMO-PIECE")
    db_session.commit()

    cid = "DEMO-PIECE"
    assert db_session.query(HoldStatusCatalog).filter_by(client_id=cid).count() == 7
    assert db_session.query(HoldReasonCatalog).filter_by(client_id=cid).count() >= 6
    assert db_session.query(DefectTypeCatalog).filter_by(client_id=cid).count() >= 5
    assert db_session.query(ClientConfig).filter_by(client_id=cid).count() == 1
    assert db_session.query(KPIThreshold).filter_by(client_id=cid).count() >= 6
    assert db_session.query(AlertConfig).filter_by(client_id=cid).count() >= 3
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py::test_catalogs_and_config_seeded_and_idempotent -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'seed_catalogs'`.

- [ ] **Step 3: Implement the two helpers**

Read the config/catalog blocks in `backend/scripts/init_demo_database.py:1587-1706` (AlertConfig, KPIThreshold, HoldStatusCatalog, HoldReasonCatalog) and mirror them per-client. Add to `seed_sample_client.py` (imports at top-of-function to keep module import light). Note the full 7-status hold chain (spec requires all seven), per-client `KPIThreshold` (not global), and reuse `TestDataFactory.create_defect_type_catalog` for defect types:

```python
_HOLD_STATUSES = [
    ("PENDING_HOLD_APPROVAL", "Pending Hold Approval", 1),
    ("ON_HOLD", "On Hold", 2),
    ("PENDING_RESUME_APPROVAL", "Pending Resume Approval", 3),
    ("RESUMED", "Resumed", 4),
    ("RELEASED", "Released", 5),
    ("CANCELLED", "Cancelled", 6),
    ("SCRAPPED", "Scrapped", 7),
]
_HOLD_REASONS = [
    ("QUALITY_ISSUE", "Quality Issue", 1),
    ("MATERIAL_SHORTAGE", "Material Shortage", 2),
    ("MATERIAL_INSPECTION", "Material Inspection", 3),
    ("ENGINEERING_REVIEW", "Engineering Review", 4),
    ("CUSTOMER_REQUEST", "Customer Request", 5),
    ("CAPACITY_CONSTRAINT", "Capacity Constraint", 6),
]
_DEFECT_TYPES = [
    ("STITCH", "Stitching", "SEWING", "MAJOR"),
    ("FABRIC", "Fabric Defect", "MATERIAL", "MAJOR"),
    ("MEASURE", "Measurement", "DIMENSIONAL", "MINOR"),
    ("COLOR", "Color Shade", "VISUAL", "MINOR"),
    ("STAIN", "Stain", "VISUAL", "MINOR"),
]
_KPI_THRESHOLDS = [
    ("efficiency", 85.0, 75.0, 60.0, "%", "Y"),
    ("performance", 95.0, 85.0, 70.0, "%", "Y"),
    ("quality_rate", 99.0, 97.0, 95.0, "%", "Y"),
    ("oee", 85.0, 75.0, 60.0, "%", "Y"),
    ("availability", 90.0, 80.0, 70.0, "%", "Y"),
    ("otd", 95.0, 90.0, 80.0, "%", "Y"),
]
_ALERT_CONFIGS = [
    ("efficiency", 75.0, 60.0),
    ("otd", 90.0, 80.0),
    ("quality", 97.0, 95.0),
]


def seed_catalogs(session: Session, client_id: str) -> None:
    from backend.orm.hold_status_catalog import HoldStatusCatalog
    from backend.orm.hold_reason_catalog import HoldReasonCatalog
    from backend.db.factories import TestDataFactory

    if session.query(HoldStatusCatalog).filter_by(client_id=client_id).first() is None:
        for code, name, order in _HOLD_STATUSES:
            session.add(HoldStatusCatalog(client_id=client_id, status_code=code, display_name=name,
                                          is_default=True, is_active=True, sort_order=order))
    if session.query(HoldReasonCatalog).filter_by(client_id=client_id).first() is None:
        for code, name, order in _HOLD_REASONS:
            session.add(HoldReasonCatalog(client_id=client_id, reason_code=code, display_name=name,
                                          is_default=True, is_active=True, sort_order=order))
    from backend.orm.defect_type_catalog import DefectTypeCatalog
    if session.query(DefectTypeCatalog).filter_by(client_id=client_id).first() is None:
        for code, name, category, severity in _DEFECT_TYPES:
            TestDataFactory.create_defect_type_catalog(
                session, client_id=client_id, defect_code=code, defect_name=name,
                category=category, severity_default=severity,
            )
    session.flush()


def seed_config_layer(session: Session, client_id: str) -> None:
    from backend.orm.client_config import ClientConfig
    from backend.orm.kpi_threshold import KPIThreshold
    from backend.orm.alert import AlertConfig

    if session.query(ClientConfig).filter_by(client_id=client_id).first() is None:
        session.add(ClientConfig(client_id=client_id))  # all targets have credible defaults
    if session.query(KPIThreshold).filter_by(client_id=client_id).first() is None:
        for kpi_key, target, warning, critical, unit, higher in _KPI_THRESHOLDS:
            session.add(KPIThreshold(threshold_id=f"KPI-TH-{client_id}-{kpi_key.upper()}", client_id=client_id,
                                     kpi_key=kpi_key, target_value=target, warning_threshold=warning,
                                     critical_threshold=critical, unit=unit, higher_is_better=higher))
    if session.query(AlertConfig).filter_by(client_id=client_id).first() is None:
        for alert_type, warning, critical in _ALERT_CONFIGS:
            session.add(AlertConfig(config_id=f"ALERT-CFG-{client_id}-{alert_type.upper()}", client_id=client_id,
                                    alert_type=alert_type, enabled=True, warning_threshold=warning,
                                    critical_threshold=critical))
    session.flush()
```

Wire into the orchestrator:

```python
def seed_client(session: Session, spec: ClientSpec, days: int) -> None:
    seed_client_row(session, spec)
    seed_catalogs(session, spec.client_id)
    seed_config_layer(session, spec.client_id)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q`
Expected: PASS (all Task-1 + Task-2 tests). If a catalog field name differs, read the ORM file named in the import and correct it.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_sample_client.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): per-client hold/reason/defect catalogs + config/threshold/alert layer"
```

---

### Task 3: Master data — shifts, products, lines, employees + assignments

**Files:**
- Modify: `backend/scripts/seed_sample_client.py`
- Test: `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces:**
- Produces: `seed_shifts(session, client_id) -> list[Shift]`, `seed_products(session, client_id) -> list[Product]`, `seed_lines(session, client_id) -> tuple[list, list]` (operational lines, capacity lines), `seed_employees(session, spec) -> list[Employee]`. All idempotent; wired into `seed_client` after the config layer.

- [ ] **Step 1: Write the failing test**

```python
def test_master_data_seeded_and_idempotent(db_session):
    from backend.orm import Shift, Product
    from backend.orm.employee import Employee
    from backend.orm.production_line import ProductionLine
    from backend.orm.employee_client_assignment import EmployeeClientAssignment
    from backend.orm.employee_line_assignment import EmployeeLineAssignment

    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client_row(db_session, spec)
    for _ in range(2):
        seed.seed_shifts(db_session, spec.client_id)
        seed.seed_products(db_session, spec.client_id)
        seed.seed_lines(db_session, spec.client_id)
        seed.seed_employees(db_session, spec)
    db_session.commit()

    cid = "DEMO-PIECE"
    assert db_session.query(Shift).filter_by(client_id=cid).count() == 2
    assert db_session.query(Product).filter_by(client_id=cid).count() == 3
    assert db_session.query(ProductionLine).filter_by(client_id=cid).count() == 2
    assert db_session.query(Employee).filter_by(client_id_assigned=cid).count() == spec.num_employees
    assert db_session.query(EmployeeClientAssignment).filter_by(client_id=cid).count() == spec.num_employees
    assert db_session.query(EmployeeLineAssignment).filter_by(client_id=cid).count() >= spec.num_employees
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py::test_master_data_seeded_and_idempotent -q`
Expected: FAIL — `seed_shifts` undefined.

- [ ] **Step 3: Implement the helpers**

Reuse `TestDataFactory.create_shift/create_product/create_employee`. Employee codes are globally unique — namespace by a short client prefix. Create the operational `ProductionLine` directly (factory has no line helper) and a matching `CapacityProductionLine`, bridging via `capacity_line_id`. Read `backend/orm/production_line.py`, `backend/orm/capacity/production_lines.py`, `backend/orm/employee_client_assignment.py` (has helper `assign_employee_to_client`), and `backend/orm/employee_line_assignment.py` to confirm constructor fields before writing.

```python
def _prefix(client_id: str) -> str:
    return "".join(part[0] for part in client_id.split("-"))[:3].upper()  # DEMO-PIECE -> "DP"


def seed_shifts(session: Session, client_id: str) -> list:
    from backend.orm import Shift
    from backend.db.factories import TestDataFactory

    existing = session.query(Shift).filter_by(client_id=client_id).all()
    if existing:
        return existing
    day = TestDataFactory.create_shift(session, client_id=client_id, shift_name="Day", start_time="06:00:00", end_time="14:00:00")
    night = TestDataFactory.create_shift(session, client_id=client_id, shift_name="Night", start_time="14:00:00", end_time="22:00:00")
    return [day, night]


def seed_products(session: Session, client_id: str) -> list:
    from backend.orm import Product
    from decimal import Decimal
    from backend.db.factories import TestDataFactory

    existing = session.query(Product).filter_by(client_id=client_id).all()
    if existing:
        return existing
    p = _prefix(client_id)
    specs = [(f"{p}-P1", "Polo Shirt", Decimal("0.12")), (f"{p}-P2", "T-Shirt", Decimal("0.08")),
             (f"{p}-P3", "Jacket", Decimal("0.30"))]
    return [TestDataFactory.create_product(session, client_id=client_id, product_code=code,
                                           product_name=name, ideal_cycle_time=ct) for code, name, ct in specs]


def seed_lines(session: Session, client_id: str):
    from backend.orm.production_line import ProductionLine
    from backend.orm.capacity import CapacityProductionLine

    existing = session.query(ProductionLine).filter_by(client_id=client_id).all()
    if existing:
        cap = session.query(CapacityProductionLine).filter_by(client_id=client_id).all()
        return existing, cap
    p = _prefix(client_id)
    lines, cap_lines = [], []
    for i in (1, 2):
        cap = CapacityProductionLine(client_id=client_id, line_code=f"{p}-CL{i}", line_name=f"Capacity Line {i}",
                                     is_active=True)
        session.add(cap)
        session.flush()  # get cap.id
        line = ProductionLine(client_id=client_id, line_code=f"{p}-L{i}", line_name=f"Line {i}",
                              line_type="DEDICATED", is_active=True, capacity_line_id=cap.id)
        session.add(line)
        lines.append(line)
        cap_lines.append(cap)
    session.flush()
    return lines, cap_lines


def seed_employees(session: Session, spec: ClientSpec) -> list:
    from backend.orm.employee import Employee
    from backend.orm.employee_client_assignment import assign_employee_to_client
    from backend.orm.employee_line_assignment import EmployeeLineAssignment
    from datetime import date
    from decimal import Decimal
    from backend.db.factories import TestDataFactory

    cid = spec.client_id
    existing = session.query(Employee).filter_by(client_id_assigned=cid).all()
    if existing:
        return existing
    lines, _ = seed_lines(session, cid)
    p = _prefix(cid)
    employees = []
    for n in range(1, spec.num_employees + 1):
        emp = TestDataFactory.create_employee(session, client_id=cid, employee_code=f"{p}-EMP-{n:03d}",
                                              employee_name=f"{spec.client_name} Operator {n}")
        assign_employee_to_client(session, employee_id=emp.employee_id, client_id=cid)
        line = lines[(n - 1) % len(lines)]
        session.add(EmployeeLineAssignment(employee_id=emp.employee_id, line_id=line.line_id, client_id=cid,
                                           allocation_percentage=Decimal("100.00"), is_primary=True,
                                           effective_date=date(2026, 1, 1)))
        employees.append(emp)
    session.flush()
    return employees
```

Wire into `seed_client` after `seed_config_layer`:

```python
    seed_shifts(session, spec.client_id)
    seed_products(session, spec.client_id)
    seed_lines(session, spec.client_id)
    seed_employees(session, spec)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q`
Expected: PASS. Confirm `assign_employee_to_client` signature by reading `backend/orm/employee_client_assignment.py`; adjust the call if it differs (e.g. requires `assignment_type`).

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_sample_client.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): master data — shifts, products, operational+capacity lines, employees + assignments"
```

---

### Task 4: Capacity planning-scheduling graph

**Files:**
- Modify: `backend/scripts/seed_sample_client.py`
- Test: `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces:**
- Produces: `seed_capacity_graph(session, client_id, days) -> None` (idempotent). Wired into `seed_client` after master data.

**Interfaces consumed:** `rng_for`, `seed_lines` (uses the capacity lines it created). Build any capacity codes from the full `client_id` (e.g. `f"{client_id}-ORD-{n}"`) — do NOT use a short prefix (globally-unique columns must not collide across clients).

- [ ] **Step 1: Write the failing test**

```python
def test_capacity_graph_seeded_and_idempotent(db_session):
    from backend.orm.capacity import (
        CapacityCalendar, CapacityOrder, CapacityProductionStandard, CapacityBOMHeader,
        CapacityStockSnapshot, CapacityComponentCheck, CapacitySchedule, CapacityScheduleDetail,
        CapacityKPICommitment,
    )
    from backend.orm.capacity.orders import OrderStatus

    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client_row(db_session, spec)
    seed.seed_lines(db_session, spec.client_id)
    for _ in range(2):
        seed.seed_capacity_graph(db_session, spec.client_id, days=30)
    db_session.commit()

    cid = "DEMO-PIECE"
    assert db_session.query(CapacityCalendar).filter_by(client_id=cid).count() >= 30
    orders = db_session.query(CapacityOrder).filter_by(client_id=cid).all()
    assert len(orders) >= 5
    statuses = {o.status for o in orders}
    assert OrderStatus.COMPLETED in statuses and OrderStatus.CANCELLED in statuses
    assert db_session.query(CapacityProductionStandard).filter_by(client_id=cid).count() >= 1
    assert db_session.query(CapacityBOMHeader).filter_by(client_id=cid).count() >= 1
    assert db_session.query(CapacityStockSnapshot).filter_by(client_id=cid).count() >= 1
    assert db_session.query(CapacityComponentCheck).filter_by(client_id=cid).count() >= 1
    assert db_session.query(CapacitySchedule).filter_by(client_id=cid).count() >= 1
    assert db_session.query(CapacityScheduleDetail).filter_by(client_id=cid).count() >= 1
    assert db_session.query(CapacityKPICommitment).filter_by(client_id=cid).count() >= 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py::test_capacity_graph_seeded_and_idempotent -q`
Expected: FAIL — `seed_capacity_graph` undefined.

- [ ] **Step 3: Implement `seed_capacity_graph`**

The `TestDataFactory` does NOT cover capacity. READ these ORM files for exact constructor fields + enum values, and mirror the capacity block of `backend/scripts/init_demo_database.py` (search it for `CapacityCalendar(`, `CapacityOrder(`, `CapacitySchedule(` to copy field usage): `backend/orm/capacity/{calendar,orders,standards,bom,stock,component_check,schedule,kpi_commitment}.py`. Build, all filtered/scoped by `client_id`, idempotent on the FIRST entity (`if session.query(CapacityCalendar).filter_by(client_id=client_id).first(): return`):
- `CapacityCalendar`: one row per calendar day over the window (`is_working_day=True` on weekdays, credible `shift1_hours=8.0`).
- `CapacityOrder`: ≥5 rows deliberately spanning `OrderStatus` DRAFT/CONFIRMED/SCHEDULED/IN_PROGRESS/COMPLETED + CANCELLED and `OrderPriority` values; credible `order_quantity`, `required_date`.
- `CapacityProductionStandard`: SAM minutes per style/operation (≥1 per product style).
- `CapacityBOMHeader` + `CapacityBOMDetail`: one parent item with ≥2 components.
- `CapacityStockSnapshot`: ≥1 per component item, credible on-hand/available.
- `CapacityComponentCheck`: mix of `ComponentStatus` OK/SHORTAGE/PARTIAL against the orders.
- `CapacitySchedule` (period over the window) + `CapacityScheduleDetail` (rows tying orders→lines→dates) + `CapacityKPICommitment` (≥1 `kpi_key` with a committed value).

Use `rng_for(client_id, "capacity")` for any varied numeric values so they are deterministic and credible (quantities 500–5000, SAM 0.5–5.0 min, stock ≥0). Wire into `seed_client`:

```python
    seed_capacity_graph(session, spec.client_id, days)
```
(placed after `seed_employees`, before work orders).

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q`
Expected: PASS. Fix any field-name mismatch by reading the specific capacity ORM file.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_sample_client.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): capacity planning-scheduling graph (calendar/orders/standards/BOM/stock/checks/schedule/commitments)"
```

---

### Task 5: Work orders + workflow variety + jobs + transition log + holds

**Files:**
- Modify: `backend/scripts/seed_sample_client.py`
- Test: `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces:**
- Produces: `seed_work_orders(session, spec, entered_by) -> list[WorkOrder]` (creates WOs across all statuses + `WorkflowTransitionLog` + some `Job`s), `seed_holds(session, client_id, work_orders, entered_by) -> None` (full hold chain, ≥1 open ON_HOLD), `_transition_chain(status) -> list[tuple]`. Wired into `seed_client` after the capacity graph.

- [ ] **Step 1: Write the failing test**

```python
def test_work_orders_cover_all_statuses_with_transitions_and_holds(db_session):
    from backend.orm import WorkOrder, WorkOrderStatus, WorkflowTransitionLog, HoldEntry, Job

    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client(db_session, spec, days=10)  # full orchestrator so entered_by resolves
    db_session.commit()

    cid = "DEMO-PIECE"
    wos = db_session.query(WorkOrder).filter_by(client_id=cid).all()
    present = {wo.status for wo in wos}
    required = {WorkOrderStatus.RECEIVED, WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS,
                WorkOrderStatus.COMPLETED, WorkOrderStatus.SHIPPED, WorkOrderStatus.CLOSED,
                WorkOrderStatus.CANCELLED, WorkOrderStatus.ON_HOLD}
    assert required.issubset(present), f"missing statuses: {required - present}"
    assert db_session.query(WorkflowTransitionLog).filter_by(client_id=cid).count() >= len(wos)
    assert db_session.query(Job).filter_by(client_id_fk=cid).count() >= 1

    holds = db_session.query(HoldEntry).filter_by(client_id=cid).all()
    hold_statuses = {h.hold_status for h in holds}
    for expected in ("PENDING_HOLD_APPROVAL", "ON_HOLD", "PENDING_RESUME_APPROVAL", "RESUMED",
                     "RELEASED", "CANCELLED", "SCRAPPED"):
        assert expected in hold_statuses, f"missing hold status {expected}"
```

NOTE: this test requires an `entered_by` user to exist. Add a module-level autouse-free helper at the top of the test file (once) that seeds an admin, and call it in tests that run the full orchestrator:

```python
def _seed_admin(db_session):
    from backend.db.factories import TestDataFactory
    if db_session.query(__import__("backend.orm", fromlist=["User"]).User).filter_by(role="admin").first() is None:
        TestDataFactory.create_user(db_session, username="seed_admin", role="admin")
        db_session.flush()
```

Call `_seed_admin(db_session)` as the first line of `test_work_orders_cover_all_statuses_with_transitions_and_holds` (and any later full-orchestrator test).

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py::test_work_orders_cover_all_statuses_with_transitions_and_holds -q`
Expected: FAIL — `seed_work_orders` undefined.

- [ ] **Step 3: Implement work orders + transitions + holds**

Use `TestDataFactory.create_work_order` (pass explicit `status`, `planned_ship_date`, `actual_delivery_date` via kwargs for OTD), `TestDataFactory.create_job`, `TestDataFactory.create_workflow_transition`, and `TestDataFactory.create_hold_entry`. Read `backend/orm/work_order.py` for `WorkOrderStatus` members and `backend/orm/hold_entry.py` for `HoldStatus`/`HoldReason` constants. The hold `created_by`/`entered_by` must be a real user id (`resolve_entered_by`). Build a credible transition chain per WO (initial `from_status=None` → its terminal status via intermediate steps).

```python
def seed_work_orders(session: Session, spec: ClientSpec, entered_by: str) -> list:
    from datetime import datetime, timedelta, timezone
    from backend.orm import WorkOrder, WorkOrderStatus
    from backend.db.factories import TestDataFactory

    cid = spec.client_id
    existing = session.query(WorkOrder).filter_by(client_id=cid).all()
    if existing:
        return existing

    states = [WorkOrderStatus.RECEIVED, WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS,
              WorkOrderStatus.COMPLETED, WorkOrderStatus.SHIPPED, WorkOrderStatus.CLOSED,
              WorkOrderStatus.CANCELLED, WorkOrderStatus.ON_HOLD]
    rng = rng_for(cid, "work_orders")
    now = datetime(2026, 6, 15, tzinfo=timezone.utc)  # fixed anchor for determinism
    wos = []
    for i, status in enumerate(states, start=1):
        wo_id = f"WO-{cid}-{i:03d}"  # full client_id — work_order_id PK is GLOBALLY unique
        planned_ship = now - timedelta(days=rng.randint(5, 40))
        # delivered on time for terminal states so OTD computes both hit/miss
        delivered = planned_ship + timedelta(days=rng.randint(-3, 6)) if status in (
            WorkOrderStatus.SHIPPED, WorkOrderStatus.CLOSED) else None
        wo = TestDataFactory.create_work_order(
            session, client_id=cid, work_order_id=wo_id, status=status,
            planned_quantity=rng.randint(500, 3000), planned_ship_date=planned_ship,
            actual_delivery_date=delivered, priority=rng.choice(["HIGH", "MEDIUM", "LOW"]),
        )
        # transition chain to the terminal status
        chain = _transition_chain(status)  # e.g. [None->RECEIVED, RECEIVED->RELEASED, ...]
        for frm, to in chain:
            TestDataFactory.create_workflow_transition(
                session, work_order_id=wo_id, from_status=(frm.value if frm else None),
                to_status=to.value, transitioned_by=entered_by, client_id=cid)
        if status in (WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED):
            # explicit deterministic job_id (do NOT let the factory mint a _next_id PK)
            TestDataFactory.create_job(session, work_order_id=wo_id, client_id=cid, job_id=f"JOB-{cid}-{i:03d}")
        wos.append(wo)
    session.flush()
    return wos


def _transition_chain(status):
    from backend.orm import WorkOrderStatus as S
    linear = [S.RECEIVED, S.RELEASED, S.IN_PROGRESS, S.COMPLETED, S.SHIPPED, S.CLOSED]
    if status in linear:
        upto = linear[: linear.index(status) + 1]
    elif status == S.CANCELLED:
        upto = [S.RECEIVED, S.RELEASED, S.CANCELLED]
    elif status == S.ON_HOLD:
        upto = [S.RECEIVED, S.RELEASED, S.IN_PROGRESS, S.ON_HOLD]
    else:
        upto = [status]
    prev = None
    chain = []
    for s in upto:
        chain.append((prev, s))
        prev = s
    return chain


def seed_holds(session: Session, client_id: str, work_orders: list, entered_by: str) -> None:
    # Construct HoldEntry directly: TestDataFactory.create_hold_entry mints
    # hold_entry_id via _next_id("HOLD") (process-local counter → cross-process
    # PK collision). Use a deterministic client-scoped PK instead.
    from datetime import datetime, timezone
    from backend.orm import HoldEntry

    if session.query(HoldEntry).filter_by(client_id=client_id).first() is not None:
        return
    chain = ["PENDING_HOLD_APPROVAL", "ON_HOLD", "PENDING_RESUME_APPROVAL", "RESUMED",
             "RELEASED", "CANCELLED", "SCRAPPED"]
    for i, hold_status in enumerate(chain, start=1):
        wo = work_orders[i % len(work_orders)]
        session.add(HoldEntry(
            hold_entry_id=f"HOLD-{client_id}-{i:03d}", work_order_id=wo.work_order_id,
            client_id=client_id, hold_initiated_by=entered_by, hold_reason="QUALITY_ISSUE",
            hold_reason_category="QUALITY", hold_status=hold_status,
            hold_date=datetime(2026, 6, 15, tzinfo=timezone.utc)))
    session.flush()
```

Wire into `seed_client` (resolve the user once):

```python
    entered_by = resolve_entered_by(session, spec.client_id)
    work_orders = seed_work_orders(session, spec, entered_by)
    seed_holds(session, spec.client_id, work_orders, entered_by)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q`
Expected: PASS. Read `backend/orm/hold_entry.py` to confirm the `HoldEntry` constructor fields used (`hold_entry_id`, `work_order_id`, `client_id`, `hold_initiated_by`, `hold_reason`, `hold_reason_category`, `hold_status`, `hold_date`) and that `hold_status` is a plain string column. Confirm `create_workflow_transition` accepts `from_status=None`. Read `backend/orm/work_order.py` for the exact `WorkOrderStatus` members before building `states`/`_transition_chain`.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_sample_client.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): work-order status variety + workflow transition log + full hold chain"
```

---

### Task 6: Daily Operations data — production / quality+defects / downtime / attendance (credible)

**Files:**
- Modify: `backend/scripts/seed_sample_client.py`
- Test: `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces:**
- Produces: `seed_daily_data(session, spec, days, entered_by) -> None` (idempotent). Wired into `seed_client` after holds.

- [ ] **Step 1: Write the failing credibility + count test**

```python
def test_daily_data_scales_with_days_and_is_credible(db_session):
    from decimal import Decimal
    from backend.orm import ProductionEntry, QualityEntry, DowntimeEntry, AttendanceEntry, DefectDetail

    _seed_admin(db_session)
    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client(db_session, spec, days=20)
    db_session.commit()

    cid = "DEMO-PIECE"
    prod = db_session.query(ProductionEntry).filter_by(client_id=cid).all()
    assert len(prod) >= 20  # at least one per working span day
    for pe in prod:
        assert pe.units_produced > 0
        assert pe.run_time_hours > 0
        assert pe.employees_assigned > 0
        assert pe.defect_count >= 0 and pe.scrap_count >= 0
        assert pe.defect_count <= pe.units_produced
    assert db_session.query(QualityEntry).filter_by(client_id=cid).count() >= 20
    assert db_session.query(DefectDetail).filter_by(client_id_fk=cid).count() >= 1
    assert db_session.query(DowntimeEntry).filter_by(client_id=cid).count() >= 1
    assert db_session.query(AttendanceEntry).filter_by(client_id=cid).count() >= 20

    # quality math is internally consistent (credibility)
    for qe in db_session.query(QualityEntry).filter_by(client_id=cid).all():
        assert qe.units_passed + qe.units_defective == qe.units_inspected
        assert 0 <= qe.units_defective <= qe.units_inspected


def test_daily_data_pks_client_scoped_no_cross_process_collision(db_session):
    # Reproduces the process-local-counter PK-collision class deterministically:
    # seed one client, reset the factory counters (= a fresh process), seed another;
    # deterministic client-scoped PKs must not collide.
    from backend.db.factories import TestDataFactory
    from backend.orm import ProductionEntry, AttendanceEntry, QualityEntry

    _seed_admin(db_session)
    seed.seed_client(db_session, seed.CLIENT_SPECS["DEMO-PIECE"], days=8)
    db_session.commit()
    TestDataFactory.reset_counters()
    seed.seed_client(db_session, seed.CLIENT_SPECS["DEMO-HOURLY"], days=8)  # must NOT IntegrityError
    db_session.commit()

    for model, pk in ((ProductionEntry, "production_entry_id"), (AttendanceEntry, "attendance_entry_id"),
                      (QualityEntry, "quality_entry_id")):
        rows = db_session.query(model).all()
        ids = [getattr(r, pk) for r in rows]
        assert len(ids) == len(set(ids)), f"{pk} collides across clients"
        for r in rows:
            owner = getattr(r, "client_id", None) or getattr(r, "client_id_fk", None)
            assert owner in getattr(r, pk), f"{pk} must be client-scoped"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py::test_daily_data_scales_with_days_and_is_credible -q`
Expected: FAIL — `seed_daily_data` undefined.

- [ ] **Step 3: Implement `seed_daily_data`**

Mirror the credible-value formula from `backend/scripts/init_demo_database.py:1340-1400` (read it). Deterministic per (client, date). One production entry per working day (skip weekends) per the first product/shift/line; a quality entry + defect detail per working day tied to a rotating seeded work order; occasional downtime; attendance per employee per working day. **Construct every entity DIRECTLY with a deterministic client-scoped PK** — do NOT use `TestDataFactory.create_production_entry/create_quality_entry/create_defect_detail/create_downtime_entry/create_attendance_entry` (they mint `_next_id` counter PKs that collide across processes — see Global Constraints). Read `backend/db/factories.py` for the correct non-PK field names/defaults each entity needs, and the ORM files for required columns (`AttendanceEntry.scheduled_hours` is required; `ProductionEntry.production_date`/`shift_date` are datetimes).

```python
def seed_daily_data(session: Session, spec: ClientSpec, days: int, entered_by: str) -> None:
    from datetime import date, datetime, timedelta
    from decimal import Decimal
    from backend.orm import (ProductionEntry, QualityEntry, DefectDetail, DowntimeEntry,
                             AttendanceEntry, AbsenceType, WorkOrder)

    cid = spec.client_id
    if session.query(ProductionEntry).filter_by(client_id=cid).first() is not None:
        return
    products = seed_products(session, cid)
    shifts = seed_shifts(session, cid)
    lines, _ = seed_lines(session, cid)
    employees = seed_employees(session, spec)
    work_orders = session.query(WorkOrder).filter_by(client_id=cid).all()
    product, shift, line = products[0], shifts[0], lines[0]
    end = date(2026, 6, 15)  # fixed anchor for determinism
    ideal_ct = float(product.ideal_cycle_time or Decimal("0.12"))
    seq = 0

    for d in range(days):
        day = end - timedelta(days=days - 1 - d)
        if day.weekday() >= 5:
            continue
        seq += 1
        day_dt = datetime.combine(day, datetime.min.time())
        rng = rng_for(cid, "daily", day.isoformat())
        units = rng.randint(600, 1600)
        target_perf = rng.uniform(0.82, 0.96)
        run_time = round(ideal_ct * units / target_perf, 2)
        downtime_h = round(run_time * rng.uniform(0.05, 0.08), 2)
        setup_h = round(run_time * 0.02, 2)
        defects = max(1, int(units * rng.uniform(0.003, 0.012)))
        scrap = defects // 3
        wo = work_orders[seq % len(work_orders)] if work_orders else None
        session.add(ProductionEntry(
            production_entry_id=f"PE-{cid}-{seq:04d}", client_id=cid, product_id=product.product_id,
            shift_id=shift.shift_id, line_id=line.line_id, entered_by=entered_by,
            production_date=day_dt, shift_date=day_dt, units_produced=units,
            run_time_hours=Decimal(str(run_time)), setup_time_hours=Decimal(str(setup_h)),
            downtime_hours=Decimal(str(downtime_h)), defect_count=defects, scrap_count=scrap,
            rework_count=defects - scrap, employees_assigned=len(employees),
            work_order_id=(wo.work_order_id if wo else None)))
        if wo is not None:
            qe_id = f"QE-{cid}-{seq:04d}"
            units_def = defects + scrap
            session.add(QualityEntry(
                quality_entry_id=qe_id, work_order_id=wo.work_order_id, client_id=cid,
                inspector_id=entered_by, inspection_date=day_dt, shift_date=day_dt,
                units_inspected=units, units_passed=units - units_def, units_defective=units_def,
                total_defects_count=units_def, units_scrapped=scrap, units_reworked=defects - scrap))
            session.add(DefectDetail(
                defect_detail_id=f"DD-{cid}-{seq:04d}", quality_entry_id=qe_id, client_id_fk=cid,
                defect_type="Stitching", defect_count=defects, severity="MINOR"))
        if seq % 5 == 1:
            session.add(DowntimeEntry(
                downtime_entry_id=f"DT-{cid}-{seq:04d}", client_id=cid, reported_by=entered_by,
                downtime_reason=rng.choice(["EQUIPMENT_FAILURE", "MATERIAL_SHORTAGE", "CHANGEOVER"]),
                shift_date=day_dt, downtime_duration_minutes=int(downtime_h * 60)))
        for j, emp in enumerate(employees, start=1):
            arng = rng_for(cid, "att", day.isoformat(), emp.employee_id)
            absent = arng.random() < 0.05
            session.add(AttendanceEntry(
                attendance_entry_id=f"ATT-{cid}-{seq:04d}-{j:02d}", employee_id=emp.employee_id,
                client_id=cid, shift_id=shift.shift_id, shift_date=day_dt,
                scheduled_hours=Decimal("8.0"), actual_hours=Decimal("0") if absent else Decimal("8.0"),
                absence_hours=Decimal("8.0") if absent else Decimal("0"),
                absence_type=AbsenceType.UNSCHEDULED_ABSENCE if absent else None,
                is_absent=1 if absent else 0))
    session.flush()
```

Wire into `seed_client` after `seed_holds`:

```python
    seed_daily_data(session, spec, days, entered_by)
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_sample_client.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): 90-day credible daily Operations data (production/quality+defects/downtime/attendance)"
```

---

### Task 7: Simulation scenario + reset/idempotency integration + CLI smoke + full-suite green

**Files:**
- Modify: `backend/scripts/seed_sample_client.py`
- Test: `backend/tests/test_scripts/test_seed_sample_client.py`

**Interfaces:**
- Produces: `seed_simulation(session, client_id) -> None` (idempotent). Final wiring of the orchestrator (all sections).

- [ ] **Step 1: Write the failing simulation + integration tests**

```python
def test_simulation_scenario_seeded(db_session):
    from backend.orm.simulation_scenario import SimulationScenario

    _seed_admin(db_session)
    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client(db_session, spec, days=5)
    db_session.commit()
    scenarios = db_session.query(SimulationScenario).filter_by(client_id="DEMO-PIECE").all()
    assert len(scenarios) == 1
    assert scenarios[0].config_json is not None
    assert scenarios[0].is_active is True


def test_full_seed_is_idempotent(db_session):
    from backend.orm import ProductionEntry

    _seed_admin(db_session)
    spec = seed.CLIENT_SPECS["DEMO-PIECE"]
    seed.seed_client(db_session, spec, days=10)
    db_session.commit()
    before = db_session.query(ProductionEntry).filter_by(client_id="DEMO-PIECE").count()
    seed.seed_client(db_session, spec, days=10)  # second full run
    db_session.commit()
    after = db_session.query(ProductionEntry).filter_by(client_id="DEMO-PIECE").count()
    assert after == before  # zero new rows


def test_reset_removes_only_target_client(db_session):
    from backend.orm import ProductionEntry, Client

    _seed_admin(db_session)
    piece = seed.CLIENT_SPECS["DEMO-PIECE"]
    hourly = seed.CLIENT_SPECS["DEMO-HOURLY"]
    seed.seed_client(db_session, piece, days=6)
    seed.seed_client(db_session, hourly, days=6)
    db_session.commit()

    seed.reset_client_data(db_session, "DEMO-PIECE")
    db_session.commit()
    assert db_session.query(ProductionEntry).filter_by(client_id="DEMO-PIECE").count() == 0
    assert db_session.query(ProductionEntry).filter_by(client_id="DEMO-HOURLY").count() > 0
    assert db_session.get(Client, "DEMO-PIECE") is not None  # CLIENT row kept


def test_cli_smoke_seeds_and_reports(tmp_path, monkeypatch, capsys):
    from backend.db.migrate import upgrade_to_head
    from backend.db.factories import TestDataFactory
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as SASession
    from backend.orm import ProductionEntry

    db_file = tmp_path / "cli.db"
    url = f"sqlite:///{db_file}"
    upgrade_to_head(url)
    eng = create_engine(url)
    with SASession(eng) as s:  # need an admin for entered_by
        TestDataFactory.create_user(s, username="cli_admin", role="admin")
        s.commit()
    eng.dispose()

    monkeypatch.setenv("DATABASE_URL", url)
    rc = seed.main(["--client", "DEMO-PIECE", "--days", "8"])
    assert rc == 0
    assert "Seeded DEMO-PIECE" in capsys.readouterr().out

    eng = create_engine(url)
    with SASession(eng) as s:
        assert s.query(ProductionEntry).filter_by(client_id="DEMO-PIECE").count() > 0
    eng.dispose()
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py::test_simulation_scenario_seeded -q`
Expected: FAIL — `seed_simulation` undefined.

- [ ] **Step 3: Implement `seed_simulation` + finalize orchestrator**

Read `backend/orm/simulation_scenario.py` and `backend/simulation_v2/models.py` (`SimulationConfig`) for the `config_json` shape; build a minimal valid config via `SimulationConfig(...).model_dump()` (mirror how `init_demo_database` seeds a scenario — search it for `SimulationScenario(`). If constructing a full `SimulationConfig` is heavy, use the smallest valid dict the model accepts (read the model's required fields); the goal is a non-null, schema-valid `config_json`.

```python
def seed_simulation(session: Session, client_id: str) -> None:
    from backend.orm.simulation_scenario import SimulationScenario

    if session.query(SimulationScenario).filter_by(client_id=client_id).first() is not None:
        return
    from backend.simulation_v2.models import SimulationConfig  # read this for required fields

    config = SimulationConfig(...).model_dump()  # fill required fields per the model
    session.add(SimulationScenario(
        name=f"{client_id} Baseline Scenario", client_id=client_id, config_json=config,
        description="Seeded baseline what-if scenario", is_active=True))
    session.flush()
```

Add the final orchestrator line after daily data:

```python
    seed_simulation(session, spec.client_id)
```

- [ ] **Step 4: Run the full script test file + full backend suite**

Run: `cd backend && python -m pytest tests/test_scripts/test_seed_sample_client.py -q && python -m pytest tests/ -q`
Expected: all new tests PASS; full suite PASS; coverage ≥75%.

- [ ] **Step 5: Lint / format / typecheck**

Run: `cd backend && ruff check scripts/seed_sample_client.py tests/test_scripts/test_seed_sample_client.py && ruff format --check scripts/seed_sample_client.py`
Expected: clean. (If the repo uses a different formatter/pre-commit, run `pre-commit run --files backend/scripts/seed_sample_client.py backend/tests/test_scripts/test_seed_sample_client.py`.)

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/seed_sample_client.py backend/tests/test_scripts/test_seed_sample_client.py
git commit -m "feat(seed): simulation scenario + reset/idempotency integration + CLI smoke"
```

---

## Verification (whole-PR definition of done)

1. `cd backend && python -m pytest tests/ -q` — all green, coverage ≥75%; the new test file covers all eight groups (safety, counts, workflow completeness, hold chain, credibility bounds, idempotency, scoped reset, CLI smoke).
2. `git diff main...HEAD --stat` shows only `backend/scripts/seed_sample_client.py`, `backend/tests/test_scripts/test_seed_sample_client.py` (+ `__init__.py` if newly created) and the spec/plan docs.
3. Prod-safety static-scan test green (no `drop_all`/`create_all`/`rebuild_schema`/`DEMO_MODE`); allowlist-refusal test green.
4. Final whole-branch review + `/code-review` + `/cross-review`; all 7 CI checks green; merge on user confirmation.
5. Post-merge, run on the VM against MariaDB (confirm-first per exec):
   `docker compose -f docker-compose.prod.yml exec backend python -m backend.scripts.seed_sample_client --days 90`
   then verify the three DEMO clients populate every UI area (the follow-on 2A validation pass).
