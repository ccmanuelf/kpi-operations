# Seeder Cutover (S1c) — Design

Status: approved in brainstorm, 2026-08-21
Predecessors: `2026-08-13-demo-seeder-rebuild-design.md` (§11 sequencing),
`2026-08-14-seeder-rebuild-s1a-engine.md`, `2026-08-18-seeder-rebuild-s1b-materializer.md`

## 1. Problem

S1a built a pure event engine; S1b built the materializer, CLI and gates. Both landed
deliberately wired to nothing: `backend/seed/` is on `main` and reachable from no production
path. The old seeder still runs every boot and every deploy.

S1c closes that: it points the boot path, CI, e2e and smoke checks at `backend/seed`, retires
~5,900 lines of the old seeder, and fixes the two `--reset` hazards that S1b documented but
deliberately left — because until now nothing called `_reset`, and S1c is what makes it live.

## 2. Goals

1. `backend/seed` is the only demo seeder. The old modules are gone, not deprecated.
2. The boot path can no longer destroy a database.
3. `--reset` cannot strand or silently delete another tenant's data.
4. No behaviour change on the VM; one deliberate, manual reset of the Render demo.

Non-goals: S2 feature coverage (alerts, assumptions, floating-pool, simulation), periodic
re-seed scheduling, and any change to Alembic revisions. S1c adds no migrations.

### 2.1 Demo-coverage gaps this cutover makes visible

The old seeder wrote 45 tables; `backend.seed` writes 23 (`coverage.py:SEEDED`). That gap
belongs to S1b, but S1c is where it becomes *user-visible*, because until this change the
boot path ran the old seeder and the VM's four tenants were populated by
`seed_sample_client.seed_client()`. Recorded here rather than in an untracked note, ranked
by how much it actually hurts, so S2 inherits a decision list rather than a rediscovery:

1. **`BREAK_TIME` — changes numbers, not just screens.** `production_kpi_service` falls back
   to full `scheduled_hours` when no break rows exist, so efficiency is systematically
   overstated (~14% for a 60-min break on an 8h shift), `is_estimated` does not flag it, and
   `crud/production/core.py` persists the value. This is the only gap that silently alters
   stored KPI data; it should be closed first.
2. **Global `KPI_THRESHOLD` rows — re-opens a shipped fix.** The retired
   `_seed_reference.py` wrote 10 `client_id=None` rows specifically so the admin thresholds
   panel was not empty in its default view; `AdminSettings.thresholds.spec.ts` is that fix's
   regression test. The new seeder writes per-client keys only, so 0 of 10 fields populate
   until a client is selected.
3. **Capacity planning (13 `capacity_*` tables).** `poweruser` logs in straight onto
   `/capacity-planning`, and `demo_planner` is a poweruser — so the seeded planner's first
   screen reads all zeros. "Plan vs Actual" is entirely capacity-sourced, and onboarding can
   never reach its `capacity_plan_created` step.
4. **Labor-hours cluster.** `ATTENDANCE_HOUR_ALLOCATION` unseeded and `labor_class` /
   `normal_hours` / `double_hours` / `triple_hours` never set, so every row buckets as
   `unclassified`, Billed reads 0.00, and the grid's amber completeness chip fires on 100%
   of rows instead of the minority the old seeder left incomplete.
5. **Lower impact, same class.** `WORK_ORDER.delay_classification` never set, so
   `otd_net_pct == otd_gross_pct` everywhere; `CLIENT` contact fields never set;
   `is_floating_pool` hardcoded False; `JOB`, `ALERT`, `PART_OPPORTUNITIES` and
   `SIMULATION_SCENARIO` empty. `EQUIPMENT` and `DASHBOARD_WIDGET_DEFAULTS` are inert.

`NOT_SEEDED` in `coverage.py` is deliberately **not** the complement of `SEEDED` — it records
only permanently-excluded tables and is pinned to `TOKEN_BLACKLIST` by
`test_not_seeded_holds_exactly_token_blacklist` (section 7). Full-coverage accounting is the
S2 gate, so this list is prose here rather than a contract there, on purpose.

## 3. Decisions settled in brainstorm

**D1 — the destructive boot path is retired, not repointed.** The old `init_database()` created
the schema *and* seeded it, which is why a destructive `rebuild_schema()` sits in front of it.
The new seeder does neither: Alembic owns schema (C5) and `backend/seed` is INSERT-only with a
scoped `--reset`. So `rebuild_schema()`, its `SchemaRebuildError` re-raise, and the
`client_count > 0` guard all leave the boot path. Recovery becomes `seed(..., reset=True)` —
the same outcome for a stale demo, with the blast radius reduced from *every table in the
database* to *these four allowlisted tenants*.

This is the hazard the Run 7 audit raised as C-1. Retiring the path removes the class rather
than continuing to rely on configuration keeping it dormant.

**D2 — `EXPECTED_CLIENTS` is derived, not literal.** It becomes `backend.seed.cli.ALLOWLIST`.
Today it names `ACME-MFG / TEXTILE-PRO / FASHION-WORKS / QUALITY-STITCH / GLOBAL-APPAREL` while
the new seeder produces `DEMO-PIECE / DEMO-HOURLY / DEMO-HYBRID / SAMPLE_REF`. Repointing the
seeder without this makes every boot decide the demo is incomplete and re-seed forever — with
the destructive rebuild in front of it, that was an infinite data-loss loop. Deriving the set
from the seeder's own allowlist makes the check and the thing checked incapable of diverging.

**D3 — Render is rebuilt once, deliberately.** `--reset` is scoped to the allowlist, so it
cannot remove the five legacy clients Render still carries; retiring `rebuild_schema()` means
nothing else will either. Rather than ship temporary cleanup code whose only job is to be
deleted later, Render's database is dropped once during the cutover and repopulated by Alembic
plus the new seeder. This is safe precisely because Render is a disposable demo.

Measured, not assumed: the VM already runs `DEMO-PIECE / DEMO-HOURLY / DEMO-HYBRID /
SAMPLE_REF` with `DEMO_MODE=false`, so it needs no migration and is unaffected by the boot-path
change. Render is the only environment requiring action.

**D4 — `scripts/deploy.sh` is deleted, not repointed.** It is dead: it targets
`/var/www/kpi-operations` (the VM uses `/opt/kpi-operations`), builds schema from
`schema_complete_multitenant.sql` which exists nowhere in the repo or on the VM, and is
referenced by nothing operational — the VM deploys via `docker compose` per the runbook. It
would fail on its first command. Repointing it would mean maintaining an unrunnable script that
creates schema from a raw SQL dump, i.e. the second schema mechanism C5 eliminated.

**D5 — two PRs, hazards first.** The cutover is what makes the `--reset` hazards reachable, so
they are fixed before the seeder goes live rather than shipping a live path and a known hazard
together.

## 4. PR-1 — `--reset` hazard fixes

Touches `backend/seed/cli.py` and its tests only. No live impact: the seeder is still wired to
nothing when this lands.

### 4.1 Nullable tenant column hides a child from the sweep

`_reset` filters each swept table by its own tenant column. A child whose tenant column is
NULLABLE and NULL is therefore never selected — and then RESTRICTs its parent's DELETE. No
sweep *order* can fix this: the row is never visited at all, so `test_reset_ordering.py`
cannot see it either.

Two edges exist today, both reproducible on plain SQLite with `PRAGMA foreign_keys=ON`:

- `FLOATING_POOL.employee_id -> EMPLOYEE`
- `ALERT.work_order_id -> WORK_ORDER`

The first is reachable through ordinary use: `backend/crud/floating_pool/assignments.py` builds
`FloatingPool(...)` with `client_id` omitted, so every `POST /api/floating-pool/assign` writes a
NULL-tenant row referencing a real employee.

**Fix.** Sweep these by parent-subquery, as `DEPENDENT_SWEEPS` already does for grandchildren —
selecting by *parent in scope* rather than by own tenant, with the guard that the child's own
tenant is NULL **or** itself in scope, so a row explicitly owned by another tenant is never
removed even when it points at a demo parent.

The edge set is **derived** from `Base.metadata` (swept child + nullable tenant column + FK into
another swept table), consistent with `CLIENT_SCOPED_TABLES`, `DEPENDENT_SWEEPS` and
`SELF_REFERENTIAL_SWEEPS`, so a third edge added later is handled rather than rotting.

### 4.2 Shared employee loses a real tenant's assignment, silently

`EMPLOYEE` is swept by its bare `client_id_assigned`, while two of its children declare
`ondelete=CASCADE`:

- `EMPLOYEE_CLIENT_ASSIGNMENT.employee_id -> EMPLOYEE`
- `EMPLOYEE_LINE_ASSIGNMENT.employee_id -> EMPLOYEE`

An employee whose `client_id_assigned` names a demo tenant but who also holds a client or line
assignment belonging to a real one loses that real row when the demo employee is deleted. No
IntegrityError, no row count to notice — worse than the RESTRICT because it is silent.

`EMPLOYEE` is the only swept table with this shape, because it is the only one whose children
can belong to a *different* tenant than the parent: an employee may be shared across clients,
whereas a work order, hold or production line belongs to exactly one. The other five
CASCADE edges into swept tables (`WORKFLOW_TRANSITION_LOG`, `HOLD_STATUS_TRANSITION`,
`ATTENDANCE_HOUR_ALLOCATION`, `ASSUMPTION_CHANGE`, `EMPLOYEE_LINE_ASSIGNMENT.line_id`) are
single-tenant chains and cannot strand another tenant's data.

**Fix.** Exclude from the `EMPLOYEE` delete any employee holding a row in either cascade child
whose own `client_id` falls outside the allowlist. Their demo assignment rows are still cleared
by the normal scoped sweep, which is correct; only the shared `EMPLOYEE` row survives.

Handled **explicitly rather than generically**: a general "never delete a parent whose cascade
reaches a foreign tenant" derivation is substantial machinery for a shape only `EMPLOYEE` has.
Following the repo's idiom, the *detection* is derived — the set of CASCADE edges into a swept
table whose child carries its own tenant column — and pinned by a guard test asserting that set
is exactly the known one, so a third instance fails the build rather than shipping silently.

### 4.3 Testing

Each hazard's reproduction becomes a permanent test — plant a NULL-tenant `FLOATING_POOL` row
and reset; plant a shared employee and assert the real tenant's assignment survives. Each new
assertion carries a named single-line mutation proving it can fail. Both reproduce on SQLite, so
neither needs MariaDB.

## 5. PR-2 — the cutover

### 5.1 Boot path (`backend/bootstrap/lifecycle.py`)

Removed: `rebuild_schema()`, the `SchemaRebuildError` re-raise, and the `client_count > 0`
guard. With no destructive step there is no half-rebuilt state, so the path returns to ordinary
best-effort — a failed demo seed leaves the app serving without demo data rather than crashing
it.

Replaced by `seed(..., reset=True)` scoped to the allowlist: a no-op reset then seed on an empty
database; a scoped clear then reseed on a partial one. `FORCE_RESEED` survives as an operator
affordance, now meaning `reset=True` rather than "drop everything".

**The `DEMO_MODE` check stays the first statement in the function** — the Run 7 C-1
remediation.

**The import must stay deferred inside the function.** S1b ships a gate asserting
`backend.seed` is unreachable from the application's import graph
(`import backend.main` leaves `sys.modules` free of `backend.seed.*`). A deferred import — as
`init_database` is today — keeps that assertion true, and the gate then enforces something
better than before: the seeder stays out of the import graph until the `DEMO_MODE` branch
actually fires. The gate is kept unchanged and allowed to constrain the implementation.

### 5.2 Remaining call sites

| site | today | after |
|---|---|---|
| `ci.yml` e2e-sqlite seed step | `init_demo_database.py` | `alembic upgrade head` + `python -m backend.seed.cli` |
| `ci.yml` smoke URLs (4) | `client_id=ACME-MFG` | `client_id=DEMO-PIECE` |
| `deploy/smoke/compose-smoke.sh` | `CLIENT_ID=ACME-MFG` | `DEMO-PIECE` |
| `frontend/e2e/attendance-labor-allocation.spec.ts` | `client_id: 'ACME-MFG'` | `DEMO-PIECE` |
| `frontend/e2e/helpers.ts` | `operator1`/`leader1`, `password123` | `demo_operator`/`demo_leader`, `DemoSeed#2026` |

The one non-mechanical piece: the old seeder created the schema *and* seeded; the new one only
seeds. Any caller that relied on it for a schema now needs `alembic upgrade head` first, which
is why the CI seeding step becomes two commands.

Credentials map cleanly — the seeded roster (`demo_admin`, `demo_planner`, `demo_leader`,
`demo_supervisor`, `demo_operator`, `demo_viewer`, all with `DEMO_PASSWORD`) covers both roles
the e2e suite uses, and `demo_operator`/`demo_leader` are assigned to `DEMO-PIECE`, so the
client and credential swaps are consistent.

### 5.3 Retirement

| removed | lines |
|---|---|
| `backend/scripts/init_demo_database.py` | 2,043 |
| `backend/scripts/_seed_*.py` (six helpers) | 1,446 |
| `backend/scripts/seed_sample_client.py` | 379 |
| `scripts/deploy.sh` (dead, D4) | 417 |
| `backend/tests/test_scripts/test_init_demo_database.py` | 295 |
| `backend/tests/test_scripts/test_seed_sample_client.py` | 1,277 |
| **total** | **≈ 5,857** |

No module outside the old seeders imports any helper. Two apparent external consumers were
checked and are false positives: `backend/pivot/hooks.py` carries a *comment* citing
`_seed_operations.py`'s `open_statuses` set, and `test_onboarding_routes.py` defines a local
function named `_seed_capacity_order`. `backend/tests/test_scripts/test_create_admin.py` is
unrelated and stays.

**Two tests are rewritten, not deleted:**

`test_demo_seed_gate.py` guards the Run 7 C-1 remediation. The tempting shortcut during a
retirement is to assert the old import no longer exists — that passes while proving nothing. It
must keep proving that with `DEMO_MODE` off the seeder returns *before touching the database*:
the rewritten form patches `backend.seed.cli.seed` and asserts it is never called.

`test_audit/test_suppression_sites.py` repoints both seeder tests at `backend.seed.cli.seed`,
keeping the contract at **zero audit rows**. S2 is where that contract changes to "every audit
row is one the materializer authored".

**Comments referencing deleted files.** `backend/seed/cli.py` and `materialize.py` carry
rationale citing "the retiring `seed_sample_client.py`" — the salvaged `CLIENT_SCOPE_COLUMN`
map, the `RESET_TABLE_ORDER` lineage, why `USER` is never deleted. That history is load-bearing
for future readers and is reworded to past tense with the file marked removed, not dropped and
not left dangling. Same for `pivot/hooks.py` and `test_no_bulk_writes_on_audited_tables.py`.

### 5.4 Documentation

`docs/deployment/vm-deploy-runbook.md` gains the six seeded credentials and `DEMO_PASSWORD`;
its "Seeding demo/sample clients" section is repointed to `python -m backend.seed.cli`; and the
periodic re-seed question is recorded as a follow-up — the seeded window ends at seed-run date,
so an un-reseeded VM goes stale exactly as it does today.

## 6. Verification

Beyond the full suite, mypy, and the seven required checks:

- **The destructive path is gone by construction:** a test asserting `rebuild_schema` is not
  reachable from `lifecycle.py`, so it cannot be reintroduced silently.
- **The drift class is closed:** a test asserting the boot path's expected-client set *is*
  `backend.seed.cli.ALLOWLIST`, not a literal that can diverge from it.
- **The C-1 gate still bites:** with `DEMO_MODE` off, `backend.seed.cli.seed` is never called —
  proven by patching it, not by asserting an import is absent.
- **The purity gate is unchanged and must stay green:** `import backend.main` leaves
  `sys.modules` free of `backend.seed.*`, which is what forces the deferred import.
- **Render:** after the one-time rebuild, exactly four clients, and the demo renders.
- **VM:** unchanged — `DEMO_MODE=false` means the boot path is dormant there either way. Health,
  frontend and the DB probe re-verified after deploy.

Every new assertion carries a named single-line mutation proving it can fail. The S1a/S1b
ledger records this failure mode more than a dozen times — a correct fix shipping with no test
capable of noticing its removal — and three adversarial review waves on S1b found it recurring
even in guards written specifically to prevent it. A guard that only ever passes is treated as
absent.

## 7. Risks

**Render is the only environment that changes.** Its one-time rebuild is manual and deliberate
(D3). CORRECTED 2026-08-24: measured before merge, Render serves the legacy FIVE and none
of the new four, and it has no persistent disk — `render.yaml` recreates the database on
every deploy — so the repopulation is automatic and D3 reduces to a post-deploy check that
exactly four allowlisted clients are present. See the plan's post-merge section.

**The e2e suite depends on seeded credentials.** If the roster or `DEMO_PASSWORD` changes later,
`helpers.ts` must follow. This is a new coupling that did not exist while the e2e suite used the
old seeder's users; it is accepted because the alternative is duplicating the roster.

**EMPLOYEE re-seed idempotency is a prerequisite for the first real tenant.** Tasks 1 and 2
made `--reset` protect a tenant outside the allowlist rather than silently deleting its rows —
the correct direction. But protection and re-seed are in tension: `EMPLOYEE.employee_code`
carries a GLOBAL unique index, and `EMPLOYEE` has no re-seed idempotency, so a spared employee
collides on the next seed and `seed(reset=True)` raises. Both hazards converge on the same
missing capability: resolve an existing employee's PK into the IdMap instead of inserting,
exactly what S1b built for `USER` under its Ruling 17.

This is unreachable today — the VM hosts only `DEMO-PIECE / DEMO-HOURLY / DEMO-HYBRID /
SAMPLE_REF`, and Render is demo-only after its one-time rebuild, so no tenant exists that could
reference a demo employee. **The trigger is explicit: before the first non-allowlisted tenant is
created on any deployment, EMPLOYEE re-seed idempotency must land.** Until then the failure mode
is a loud, non-destructive `IntegrityError` that preserves the customer's data, recoverable by
deleting the offending row. Recorded here rather than only in `_reset`'s docstring, because a
deferral that lives in a comment is one nobody reads before onboarding a customer.

**A note for whoever lands that work.** Three tests currently assert
`pytest.raises(IntegrityError)` — the two shared-employee tests and the foreign-owned
null-tenant test. They discriminate correctly today (removing the guard stops the raise, and
they fail), but they are pinned to the CURRENT failure mode, not to the desired one. Adding
employee idempotency removes the collision, `seed(reset=True)` starts succeeding, and those
three tests will fail on a raise that no longer happens. That is the correct signal, not a
regression: **flip them to assert clean success plus survival** at that point. Stated here so
the failure reads as "the deferred fix landed" rather than "the idempotency change broke
`--reset`".

**`deploy.sh` deletion is irreversible in the working tree but not in history.** If some
unrecorded workflow used it, that surfaces after the fact. Mitigated by the evidence that it
cannot currently run at all.
