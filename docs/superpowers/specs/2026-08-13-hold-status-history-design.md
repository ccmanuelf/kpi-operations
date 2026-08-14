# Hold-Status Transition History — Design (Cycle 4 PR-C1)

**Date:** 2026-08-13
**Status:** Approved in brainstorm (owner Ruling A, 2026-08-13); ready for implementation planning
**Blocks:** `docs/superpowers/specs/2026-08-13-demo-seeder-rebuild-design.md` (the seeder populates this table)
**Part of:** Cycle 4 PR-C (`docs/superpowers/specs/2026-08-06-pivot-summarization-layer-design.md`)

## 1. Problem

`backend/calculations/wip_aging.py:97` `active_as_of(as_of)` is the single source of truth for
WIP-aging scoping — the aggregate, top-N, trend, and chronic-hold queries all filter on it. Its
status arm tests `HoldEntry.hold_status`, which is **current** state, so a past `as_of` is judged
partly by what the hold looks like today. Its own docstring records the consequence:

> a hold that was only PENDING_HOLD_APPROVAL back then but has since been approved counts for
> that date, and one still pending now is absent from every past date.

Dates and resume state are evaluated correctly; the defect is confined to the status arm and
only bites callers that walk past dates — `/api/kpi/wip-aging/trend`. As-of-now callers pass
today's date and are unaffected.

The docstring also names the fix and forbids the workaround:

> Fixing it properly needs a status-transition history to ask "what was this hold's status on
> date D", which is exactly the transitions dataset scoped for Cycle 4 PR-C. Do not paper over it
> with more current-status logic.

Owner ruling (2026-08-13): apply the real fix and ship it with PR-C.

## 2. Why not read `AUDIT_ENTRY`

`HOLD_ENTRY` is in `AUDITED_TABLES`, so every `hold_status` change is already captured with
old and new values and an `occurred_at`. Reading that instead of adding a table was considered
and rejected:

- `active_as_of` must remain a **SQL predicate** composable into `and_()`, so callers keep
  index-assisted `ORDER BY ... LIMIT` instead of loading every candidate hold into memory. The
  audit payload is JSON; extracting a field from it inside that predicate means dialect-specific
  JSON functions on both SQLite and MariaDB, in the single hottest predicate in the module.
- The audit trail is deliberately not backfilled and is admin-scoped. Making a KPI query depend
  on it couples reporting to an access-controlled compliance log.
- `WORKFLOW_TRANSITION_LOG` already establishes the pattern in this codebase for exactly this
  question about work orders. Holds should answer it the same way.

## 3. Design

### 3.1 New table

`HOLD_STATUS_TRANSITION`, mirroring `WORKFLOW_TRANSITION_LOG` (`backend/orm/workflow.py`):

| Column | Type | Notes |
|---|---|---|
| `transition_id` | Integer PK, autoincrement | |
| `hold_entry_id` | FK → `HOLD_ENTRY.hold_entry_id`, ON DELETE CASCADE, NOT NULL | |
| `client_id` | FK → `CLIENT.client_id`, NOT NULL | denormalized for client-scoped queries, same as the workflow log |
| `from_status` | String(30), nullable | NULL for the row recording hold creation |
| `to_status` | String(30), NOT NULL | |
| `transitioned_by` | FK → `USER.user_id`, String(50), nullable | matches the workflow log's corrected type |
| `transitioned_at` | DateTime, NOT NULL, indexed | |
| `notes` | Text, nullable | transition reason |

Indexes: `(hold_entry_id)`, `(client_id, transitioned_at)`, `(to_status, transitioned_at)` —
the same three the workflow log carries.

Delivered as a new Alembic revision. No edits to shipped revisions; the schema-parity guard
against `Base.metadata` must stay green on both dialects.

### 3.2 Write path

Every place that creates a hold or changes `hold_status` writes a transition row in the same
transaction: hold creation (a row with `from_status = NULL`), approval, release/resume, and any
status correction. These live under `backend/crud/hold/`. The implementer enumerates every
`hold_status` write site and covers all of them; a static guard test asserts no `hold_status`
assignment exists outside the module that also records a transition.

### 3.3 `active_as_of` rewrite

The date and resume arms are unchanged. The status arm becomes: *the hold's status as of the
cutoff, taken from its transition history* — the `to_status` of its latest transition at or
before the cutoff — and that status must not be in `NON_WIP_HOLD_STATUSES`.

Expressed as a correlated subquery against `HOLD_STATUS_TRANSITION`, using plain comparisons
against a bound datetime. No dialect-specific date arithmetic, no JSON extraction, no window
functions — portable by construction, matching the constraint the current predicate already
documents.

### 3.4 Degradation boundary

There is **no backfill** (owner ruling, 2026-08-12). Holds created before this table exists have
no history, so a query for a date before their first transition row can find no status.

Rule: when a hold has no transition at or before the cutoff, fall back to its current
`hold_status` — today's exact behaviour. The fix is therefore exact from a hold's first recorded
transition onward and degrades to the documented known limitation before it, rather than dropping
those holds from history altogether (which would be strictly worse, and is the failure mode the
pre-2026-08 `hold_status == ON_HOLD` filter had).

The module exposes the boundary the way the audit read API does with `_trail_started_at`: a
helper returning `MIN(transitioned_at)`, so callers and docs can state honestly from when the
trend is exact.

## 4. Testing

- **Predicate unit tests, both dialects.** The docstring's own scenario: a hold that was
  `PENDING_HOLD_APPROVAL` on date D and was approved afterwards must be **absent** from D and
  present later; a hold approved before D and still pending nothing must be present at D.
- **Fallback test.** A hold with no transition rows behaves exactly as today at every `as_of`.
- **Invariance test.** The four callers (aggregate, top-N, trend, chronic) return identical
  results to the current implementation when `as_of` is today — the fix must not move as-of-now
  numbers.
- **Trend regression.** A fixture where current-status logic and history logic genuinely disagree,
  asserting the trend changes. This test must be watched failing against the old predicate before
  it counts as evidence; a fixture where both agree would pass vacuously.
- **Write-path coverage.** Every `hold_status` write site produces a transition row; asserted by
  the static guard plus per-site tests.
- **Schema parity.** Baseline equals `Base.metadata` on SQLite and MariaDB, as every CI run
  already asserts.

## 5. Scope boundaries

In scope: the table, its Alembic revision, write-path instrumentation, the `active_as_of` status
arm, the boundary helper, and updating the docstring that currently documents the limitation.

Out of scope: the PR-C transitions **dataset** and priority adherence (PR-C2); backfill of any
kind; changes to `NON_WIP_HOLD_STATUSES` membership, which was settled by owner ruling on
2026-08-11 (`PENDING_HOLD_APPROVAL` is not aging WIP, `PENDING_RESUME_APPROVAL` is).

## 6. Risk

The rewrite touches the predicate four endpoints depend on. The invariance test in section 4 is
the control: as-of-now behaviour must be bit-identical, so any movement in today's dashboards
signals a defect rather than the intended improvement.

---

## Amendment (2026-08-14): earliest-transition fallback — PR-C1b

**Status:** Owner-accepted 2026-08-14, after an adversarial cross-model review of PR-C1 raised it.
**Supersedes:** §3.4's two-tier fallback.

### The observation

§3.4 falls back to the hold's **current** `hold_status` whenever no transition exists at or before
the cutoff. For a hold that has *some* history but none before the cutoff, a strictly better answer
is already stored: the **earliest** transition's `from_status` is the state the hold held
immediately before that transition, and because it is the earliest, that state extends backwards
over all prior time — including the as-of date.

Falling back to current status in that case is not merely imprecise, it can be actively wrong in a
way the stored data contradicts. A hold that was `ON_HOLD` throughout June and was cancelled in
August has an August transition reading `from_status = ON_HOLD`; §3.4 nonetheless judged June by
today's `CANCELLED` and dropped the hold from June's snapshot.

This is not backfill. No history is synthesised; the amendment reads a column already written.

### Resolution order

`active_as_of` resolves a hold's status at the cutoff in three tiers:

1. `to_status` of the **latest** transition strictly before the cutoff.
2. Otherwise `from_status` of the **earliest** transition at or after the cutoff.
3. Otherwise the hold's current `hold_status`.

Expressed as `func.coalesce(tier1, tier2, HoldEntry.hold_status)` over two correlated scalar
subqueries — the second ordered ascending, tie-breaking on `(transitioned_at ASC, transition_id
ASC)` for the same whole-second reason tier 1 orders descending. The existing composite index
`ix_hold_transition_hold_asof (hold_entry_id, transitioned_at, transition_id)` serves both
directions; no new index is required.

### Why tier 3 still exists

Two cases reach it. A hold with **no transitions at all** — every hold predating PR-C1 — behaves
exactly as it does today. And a hold whose earliest transition is its **creation row**, whose
`from_status` is `NULL` by construction: the hold did not exist before that instant, so there is no
prior status to report. That case is already excluded by the date arm, since PR-C1 stamps the
creation row at the hold's own `hold_date`; tier 3 is its correct resting place regardless.

### Effect on the boundary

The no-backfill boundary narrows rather than moves. Exactness still begins at a hold's first
recorded transition for tier 1, but tier 2 now extends *correct* answers backwards from that
transition for the one status it can prove. `hold_status_history_started_at` continues to report
where tier-1 exactness begins and its contract is unchanged.

### As-of-now behaviour must not move

For `as_of = today`, tier 2 can only match a transition dated in the future, which does not occur,
so the predicate reduces to tiers 1 and 3 — PR-C1's exact behaviour. This is asserted, not assumed:
the golden-master invariance test from PR-C1 must continue to pass unchanged.
