# Demo Seeder Rebuild — Design

**Date:** 2026-08-13
**Status:** Approved in brainstorm; ready for implementation planning
**Prerequisite for:** Cycle 4 PR-C (`docs/superpowers/specs/2026-08-06-pivot-summarization-layer-design.md`)
**Depends on:** PR-C1 (hold-status transition capture), which must land first so the seeder can populate that table

## 1. Problem

The demo dataset no longer represents the system. An audit of 476 API routes across 57 areas,
38 frontend routes, and all 60 tables — cross-referenced against live row counts on the VM —
found three classes of failure.

**Nine application sections have a UI and an API surface but zero data:**

| Section | API routes | Backing table(s) | Live rows |
|---|---|---|---|
| Assumption variance report | 11 | `CALCULATION_ASSUMPTION`, `ASSUMPTION_CHANGE` | 0, 0 |
| Part opportunities (DPMO basis) | 7 | `PART_OPPORTUNITIES` | 0 |
| Floating-pool coverage | 7 | `COVERAGE_ENTRY`, `shift_coverage` | 0, 0 |
| Client-scope authorization | 5 | `USER_CLIENT_ASSIGNMENT` | 0 |
| Alert accuracy / predictions | 5 | `ALERT_HISTORY` | 0 |
| Saved filters | 14 | `SAVED_FILTER`, `FILTER_HISTORY` | 0, 0 |
| User preferences | 6 | `USER_PREFERENCES` | 0 |
| Import history | 1 | `import_log` | 0 |
| Domain events (`events/bus.py`; no API) | — | `EVENT_STORE` | 0 |

One consequence is already live in production code: `backend/calculations/efficiency.py:158`
counts `CoverageEntry` rows for a shift, so floating-pool coverage contributes exactly zero to
every efficiency calculation.

**Two datasets are structurally unusable.** `WORKFLOW_TRANSITION_LOG` covers 40 of 100 work
orders, and those 40 each carry exactly one distinct timestamp — every transition stamped at
seed time, so status intervals are zero-length and "what status was this on date D" is
unanswerable. That question is the entire premise of PR-C. `AUDIT_ENTRY` holds 5 rows spanning
1 of its 14 audited tables.

**The core KPI tables are token samples.** Over the same four-month window, each client has 720
attendance rows but only 20 production entries, 20 quality entries, 20 defect details, 4
downtime entries, 2 jobs, and 7 holds. Every OEE, FPY, DHU, and downtime-by-cause chart is
drawing on roughly one production entry per client per week. MRP is structurally present but
sparse: 4 BOM headers for 12 products, 12 stock snapshots, 24 component checks.

The window also ends 2026-08-05 while today is 2026-08-13, so the demo shows no recent activity.

The root cause is structural, not incidental: nothing fails when a feature ships without demo
data. The seeder is 3,955 lines across four modules (`init_demo_database.py` alone is 2,043,
four times the repo's 500-line rule) writing rows through 36 per-row ORM `add()` sites, with no
gate asserting that any table is populated or that any metric is demonstrable.

## 2. Goals

1. Every application section has representative data, including MRP and Simulation.
2. Twelve months of full-density history, anchored to seed-run date.
3. Status history with real, monotonic timestamps — `active_as_of` and the PR-C transitions
   dataset become answerable.
4. Degradation becomes a failing build, not a live discovery.
5. Seeder modules obey the repo's 500-line rule.

**Non-goals.** No production code changes to support seeding (no time-injection seams). No new
capture columns beyond PR-C1's hold-status history. No changes to the demo's prod-safety policy.

## 3. Decisions settled in brainstorm

1. **Generation via an explicit timestamped event stream** (option C), not replay through app
   write paths and not direct shaped inserts. Replay cannot back-date `transitioned_at` /
   `occurred_at` without changing production code, and both seeder entry points are wrapped in
   `@audit_suppressed()`, so replay would leave the audit trail empty. Direct shaped inserts are
   what produced the current gaps.
2. **Twelve months, full density.** Roughly 45,000–50,000 rows. Quality over seed speed.
3. **Hybrid shaping**: a statistical baseline with scripted events injected at fixed dates.
   Purely statistical data cannot be asserted against, which is how the current seeder rotted;
   purely scripted data makes every day mechanically regular.
4. **A documented new credential set** replaces the current logins.
5. **`NOT_SEEDED` contains exactly one table**, `TOKEN_BLACKLIST`.
6. **Priority-adherence denominator** (ruled during this cycle): orders where priority was
   actionable; `ON_HOLD` counts as actionable; ratio is order-level binary with demotion count
   carried as a separate churn measure; orders with no priority are excluded from the
   denominator and their share published as a coverage figure.

## 4. Architecture

Three stages, strictly separated, with chronology owned by exactly one of them.

**Stage 1 — Scenario (`scenarios.py`).** Declarative data, no database access: per client, the
pay model, lines, shifts, employees, products, BOMs, thresholds, and the list of scripted events
with their fixed offsets from the window end.

**Stage 2 — Generator (`generator.py`).** Pure function from scenario plus RNG seed to a
chronologically ordered stream of typed, timestamped events. No database access. The statistical
baseline lives here; scripted events are merged in at their dates. Emits events such as
`EmployeeHired`, `WorkOrderReceived`, `WorkOrderReleased`, `WorkOrderDemoted`, `HoldPlaced`,
`HoldStatusChanged`, `HoldResumed`, `ShiftWorked`, `ThresholdChanged`, `AssumptionRevised`,
`RoleGranted`, `CsvImported`, `FilterSaved`, `AlertRaised`, `AlertOutcomeObserved`.

**Stage 3 — Materializer (`materialize.py`).** Walks the stream in order and emits SQLAlchemy
Core bulk inserts, batched per table in FK-safe order. Every derived artifact —
`WORKFLOW_TRANSITION_LOG`, hold-status history, `AUDIT_ENTRY`, `import_log`, `ALERT`,
`ALERT_HISTORY`, `EVENT_STORE` — is written from the same events as the rows they describe.

**The load-bearing invariant: every timestamp originates in its event.** `materialize.py`
contains no `func.now()`, no `datetime.now()`, and no reliance on `server_default`. This is
enforced by a static guard test, because it is exactly the defect that collapsed all 40 existing
transition chains into a single instant.

## 5. Module structure

Replacing `scripts/init_demo_database.py` (2,043), `scripts/_seed_operations.py` (621), and
`scripts/seed_sample_client.py` (379):

```
backend/seed/
  __init__.py
  events.py        # frozen dataclasses, one per event type
  scenarios.py     # declarative per-client scenarios + scripted events
  generator.py     # scenario + seed -> ordered event stream
  materialize.py   # event stream -> Core bulk inserts, FK-ordered
  coverage.py      # SEEDED / NOT_SEEDED contract + reasons
  profiles.py      # full (12 months) and smoke (14 days, for tests)
  cli.py           # --reset, --client, --profile, --seed, --as-of
```

Each file stays under 500 lines. `backend/db/factories.py` (912) is test-fixture
infrastructure with a different purpose and is left alone; the implementer confirms this before
touching it.

The boot path at `backend/bootstrap/lifecycle.py:183` is repointed to the new entry point. Its
`DEMO_MODE` gate and the destructive-rebuild guard are preserved verbatim.

## 6. Narrative design

Four clients, each demonstrating a different failure mode, plus one healthy control so the
dashboards are not uniformly red:

| Client | Pay model | Story |
|---|---|---|
| `DEMO-PIECE` | Piece rate | Supplier-quality crisis in months −8..−6: DHU spike, chronic holds, OTD dip, demotion cluster |
| `DEMO-HOURLY` | Hourly | Equipment-reliability decline in months −5..−3: unplanned-maintenance downtime, OEE availability drag, changeover excess |
| `DEMO-HYBRID` | Hybrid | Labor disruption in months −4..−2: absenteeism spike, floating-pool coverage response, efficiency recovery |
| `SAMPLE_REF` | Hourly | Healthy baseline — every metric in specification for the full year |

Each scripted event carries the observable it must produce, and each observable becomes a test
(section 8).

## 7. Coverage contract

`coverage.py` declares every table in `Base.metadata` as either seeded or explicitly excluded
with a written reason, mirroring the `AUDITED_TABLES` / `EXCLUDED_TABLES` pattern in
`backend/audit/registry.py` that is already guarded in tests.

`NOT_SEEDED` has one entry:

- `TOKEN_BLACKLIST` — a JWT revocation ledger written when a user logs out. Fabricated revoked
  tokens would demonstrate nothing and could only mislead.

`SAVED_FILTER`, `FILTER_HISTORY`, and `USER_PREFERENCES` are seeded despite being per-user state:
they back 20 API routes, and an empty filter dropdown on every login reads as broken rather than
personal.

## 8. Testing and gates

**Coverage gate.** Every `Base.metadata` table appears in exactly one of `SEEDED` / `NOT_SEEDED`;
a table in neither fails the build. After a seed run, every `SEEDED` table has rows. This is the
gate that would have caught `USER_CLIENT_ASSIGNMENT = 0` for the entire life of the client-scope
feature.

Phasing across the two PRs: S1 introduces the contract and enforces "every declared `SEEDED`
table has rows" for the tables it declares. The completeness half — every `Base.metadata` table
has a home in one bucket or the other — turns on in S2, once every table has one. S1 must not
pre-declare tables it does not seed, since that would fail its own gate.

**Scripted-event assertions.** Each runs against the seeded database:

| Assertion | Guards |
|---|---|
| `DEMO-PIECE` DHU in the crisis window ≥ 2× its baseline months | DHU derivation, Q3 view |
| ≥ 3 holds aged past 60 days at seed date, all in the chronic list | WIP aging, chronic holds |
| ≥ 1 month per client below 80% OTD, and `SAMPLE_REF` never below | OTD, threshold colouring |
| Demotions co-located with scheduling-category downtime in the same bucket | Q4 correlation block |
| Every work order has a transition chain with strictly increasing timestamps | PR-C transitions dataset |
| ≥ 1 audit row for each of the 14 audited tables | Audit trail read API |
| `DEMO-HOURLY` unplanned-maintenance downtime ≥ 2× other categories in its window | Downtime taxonomy, Q2 view |
| `DEMO-HYBRID` absenteeism peak coincides with non-zero coverage entries | Absenteeism, floating pool, efficiency |
| Every seeded client has ≥ 12 distinct months of production and quality data | Monthly pivot buckets |
| Priority-adherence denominator is non-empty and below 100% for ≥ 1 client | Priority adherence |

**Determinism.** Same `(seed, profile, as-of)` produces an identical event stream and identical
row counts. Tests pin an explicit `--as-of` so they do not drift with the calendar.

**Structural guards.** `materialize.py` contains no `func.now()` / `datetime.now()`. Every work
order has at least one transition row. Hold-status history is monotonic per hold.

**Dialects.** Full seed runs against both SQLite and MariaDB in CI; the scripted-event
assertions run against both, since this repo's recurring bug class is MariaDB-only behaviour that
SQLite tests cannot catch.

## 9. Determinism, safety, credentials

Seeded RNG with a fixed default; the window ends at the seed-run date unless `--as-of` overrides.

The existing prod-safety policy carries over unchanged: INSERT-only against the demo-client
allowlist, no `drop_all`, and `--reset` deleting only allowlisted clients' rows in the existing
`RESET_TABLE_ORDER` FK sequence.

Audit suppression stays enabled. Audit rows are authored explicitly from events, with real actors
and back-dated `occurred_at` — the only way to obtain a trail predating the seed run.

Credentials are a documented new set covering all six roles (admin, poweruser, leader,
supervisor, operator, viewer), recorded in the deployment runbook. Role-to-client assignments
populate `USER_CLIENT_ASSIGNMENT` so multi-tenant scoping is demonstrable: at least one leader
with several clients, one supervisor with one, and one viewer to prove read-only enforcement.

## 10. Performance

Core `insert().values([...])` in batches with one transaction per table group, replacing 36
per-row ORM `add()` sites. Seed duration is measured on both dialects and reported.

Render auto-seeds on boot under `DEMO_MODE` on SQLite. If measured cold-start proves
unacceptable at full density, the correct remedy is shipping a pre-built SQLite artifact, not
reducing the dataset. Measure before optimizing.

## 11. Sequencing

1. **PR-C1** — hold-status transition capture + `active_as_of` rewrite. Must precede the seeder,
   which populates the new table.
2. **This rebuild**, as two PRs:
   - **S1 — engine and operational spine.** `backend/seed/` package, event model, generator,
     materializer, profiles, CLI; clients, users and assignments, employees, lines, shifts,
     products, work orders with full transition chains, holds with status history, attendance,
     production, quality, defects, downtime. Boot path repointed; old seeder modules retired.
     Coverage contract and the determinism, structural, and dialect gates land here.
   - **S2 — remaining feature coverage.** Assumptions and variance, part opportunities,
     floating-pool coverage, alerts and alert history, saved filters, preferences, import logs,
     domain events, MRP depth, Simulation scenarios. The full scripted-event assertion suite and
     the "every `SEEDED` table has rows" gate close here.

   S1 is independently verifiable: it either produces monotonic transition chains for every work
   order or it does not.
3. **PR-C2** — transitions dataset + priority adherence.
4. **PR-C3** — DHU, rework-%, changeover, Q4 correlation, concept-register re-grades.

## 12. Constraints inherited from PR-C1

PR-C1 shipped `HOLD_STATUS_TRANSITION` and `record_hold_transition`, which the materializer writes
through for hold history. Three properties of that interface bind this project:

**`transitioned_at` must be a `datetime`, never a `date`.** The recorder calls
`.replace(microsecond=0)` on whatever it is given, which raises on a bare `date`. No caller can
trigger this today — `crud/hold/core.py` converts before insert — so PR-C1 deliberately added no
guard rather than writing error handling for an unreachable branch. The seeder is the caller that
makes it reachable: every historical instant the generator emits must already be a `datetime`.

**Timestamps are truncated to whole seconds.** MariaDB `DATETIME` carries no fractional precision
and rounds on store, which would move a `23:59:59.5` event to the next day. The generator must
therefore treat one second as its finest resolution, and must not rely on sub-second ordering to
sequence two events.

**Ordering within a shared second falls to `transition_id`.** `active_as_of` tie-breaks on
`(transitioned_at DESC, transition_id DESC)`, so when two transitions share a second the
later-inserted row wins. The materializer already walks the event stream in chronological order,
which satisfies this — but it means events must be inserted in the order they occurred, not
grouped per table in a way that reorders them. This was observed live on the VM: three real
transitions landed in the same second on the first production write.

## 13. Risks

**Volume estimates are approximate.** Roughly 45,000–50,000 rows at full density derives from 4
clients × 2 lines × 2 shifts × ~250 working days. Actual counts are whatever the generator
produces; the tests assert observable properties, not row totals.

**Seed duration is unmeasured.** Section 10 commits to measuring rather than to a number.

**The window ends at seed-run date.** Re-running on a later day shifts the whole window, so a VM
left unseeded goes stale exactly as it has now. Scheduling a periodic re-seed is out of scope
here and is noted as a follow-up for the deployment runbook.
