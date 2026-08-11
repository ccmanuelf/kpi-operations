# Audit Trail — Design Spec

**Date:** 2026-08-11
**Status:** Approved for planning
**Project:** A of two (A = audit trail backend, B = custom-dashboard widget system)

---

## 1. Problem

The system records **who called which endpoint**, but not **what changed**.

`backend/middleware/audit_log.py` is registered (`bootstrap/app_config.py:89`) and works
correctly — user attribution is real, set in `auth/jwt.py:220` alongside
`request.state.user_id`. But it is log-only by design: "no database writes, no
request-body capture". It emits lines like:

```
[AUDIT] POST /api/production | user=42 | status=201 | time=12ms
```

That answers "was this endpoint called". It cannot answer "who released this hold,
when, and what was the reason before they changed it" — because it records HTTP shape,
not semantic change, and writes to application logs rather than a queryable table.

There is precedent for domain-specific trails: `WORKFLOW_TRANSITION_LOG` exists with
140 rows, tracking work-order transitions. This design generalises that idea rather
than inventing it.

**Gap:** a queryable, persisted trail of entity-level change, with per-field
before→after values and durable actor attribution.

---

## 2. Decisions

Each was an explicit owner ruling during brainstorming.

| # | Decision | Rationale |
|---|---|---|
| D1 | **Capture at the SQLAlchemy ORM layer** (`before_flush`) | Cannot be bypassed by a new endpoint. Records real semantic change rather than HTTP shape. Verified safe: the codebase contains **no** `bulk_save_objects`, `bulk_insert_mappings`, or core `insert()` in application code, so ORM events have no blind spots. |
| D2 | **Audit human decisions only, via an allow-list + completeness guard** | Highest signal, bounded growth. The drift risk that makes "audit everything" attractive is closed by a test, not by discipline. |
| D3 | **Admin-only reads** | Audit history includes role and permission changes — the most sensitive data in the system. Easy to widen later; painful to narrow once relied upon. |
| D4 | **Keep indefinitely; no purge job** | At projected volume the table stays small for years. An audit trail that deletes its own history is worth less than one that grows. Revisit on measured evidence. |
| D5 | **Secrets redacted, enforced by guard** | `password_hash` is the only sensitive column today. A guard prevents a *future* one leaking silently. |

### Why the allow-list, quantified

Production row counts (59 tables, 8,014 rows) show volume is **machine-driven**:

| table | rows | nature |
|---|---:|---|
| `ATTENDANCE_ENTRY` | 2,880 | operational entry |
| `ATTENDANCE_HOUR_ALLOCATION` | 2,475 | **derived splits**, rewritten when attendance changes |
| `METRIC_CALCULATION_RESULT` | 1,269 | **cron-written** (`tasks/dual_view_calculation.py`, daily `CronTrigger`); already self-audits via its own `calculated_by` field |
| `capacity_calendar` | 360 | derived |

Auditing these would produce a permanent stream of "the scheduler recalculated things",
and one human attendance edit would cascade into many derived-row entries.

Counted against that, "audit everything" was seriously considered and rejected on three
measured grounds: daily scheduler noise, ~8,000 audit rows per `--reset` re-seed, and
`USER.password_hash` landing in a table readable by more people than `USER` itself.
Its one real advantage — nothing silently missed — is preserved by the completeness
guard below.

---

## 3. Architecture

New package `backend/audit/`:

### `context.py`
A `ContextVar[str | None]` holding the acting user. **No contextvar pattern exists in
this codebase today** — this introduces the first one, because ORM flush hooks have no
request object and therefore cannot read `request.state.user_id`.

- Set in `auth/jwt.py` at the point `request.state.user_id` is already assigned, so
  attribution has a single source of truth.
- Reset per request.
- Exposes `audit_suppressed()`, a context manager for deliberate bulk work.

### `capture.py`
A SQLAlchemy `before_flush` listener that walks `session.new`, `session.dirty` and
`session.deleted`, filters to allow-listed tables, computes per-field before→after
diffs from attribute history, applies redaction, and stages `AuditEntry` rows.

**`before_flush`, not `after_flush`**, for two reasons that matter:
old values are still present in attribute history before the flush completes; and
staged audit rows join the *same transaction*, so a rolled-back change can never leave
an audit entry, and a committed change can never lack one. Atomicity is inherent rather
than bolted on.

### `registry.py`
The single source the guards read:

- `AUDITED_TABLES` — the tables where a **person decides**. Initial set, by exact
  `__tablename__`:

  | table | why it is a human decision |
  |---|---|
  | `WORK_ORDER` | status transitions, dates, quantities |
  | `HOLD_ENTRY` | placing, releasing and reasoning about holds |
  | `USER` | account creation, role changes, activation |
  | `CLIENT` | tenant lifecycle |
  | `CLIENT_CONFIG` | per-tenant behaviour switches |
  | `EMPLOYEE` | workforce record changes |
  | `EMPLOYEE_CLIENT_ASSIGNMENT` | who works for which tenant |
  | `EMPLOYEE_LINE_ASSIGNMENT` | line staffing decisions |
  | `KPI_THRESHOLD` | the targets performance is judged against |
  | `HOLD_REASON_CATALOG` | taxonomy edits that reshape reporting |
  | `HOLD_STATUS_CATALOG` | taxonomy edits that reshape reporting |
  | `USER_CLIENT_ASSIGNMENT` | **access-control grant** — read by `middleware/client_auth.py` to decide which tenants a user may access |
  | `DEFECT_TYPE_CATALOG` | taxonomy edits that reshape reporting, same rule as the hold catalogues |
  | `ALERT_CONFIG` | per-client `warning_threshold` / `critical_threshold` / `enabled` — mirrors `KPI_THRESHOLD`; disabling an alert silently stops the system warning anyone |

  The catalogue tables are included because editing a taxonomy retroactively
  changes what every historical report means — a high-consequence, low-frequency
  human act.

  `ALERT_CONFIG` was added in the same way after the Task 2 *reviewer* flagged it
  (owner ruling, 2026-08-11): it mirrors the audited `KPI_THRESHOLD` — both are
  per-client threshold reference data, seeded together by
  `scripts/_seed_reference.py` — so auditing one and not the other was
  inconsistent.

  `USER_CLIENT_ASSIGNMENT` and `DEFECT_TYPE_CATALOG` were added during
  implementation (owner ruling, 2026-08-11) after the Task 2 implementer flagged
  them. Both close inconsistencies in the original 11: a `USER` role change was
  audited while the tenant-access grant conferring the same reach was not — in a
  codebase that has already shipped a cross-tenant authorization fix — and one
  taxonomy table was excluded while its two structural siblings were audited.

- `EXCLUDED_TABLES` — every other ORM table, each with a **stated reason**
  (derived, cron-written, or self-auditing). The completeness guard makes this
  exhaustive by construction: any table absent from both sets fails CI.
- `REDACTED_FIELDS` — field names never persisted in `changes`. Initially
  `{"password_hash"}`, the only sensitive column in the ORM layer today.

### Suppression
Narrow and explicit. The demo seeder (`scripts/seed_sample_client.py`, which uses
`session.add(...)` and would otherwise be captured) and the CSV bulk importers wrap
their work in `audit_suppressed()`. **Unsuppressed bulk writes are still captured**, so
the opt-out is a deliberate act at a known call site rather than an ambient default.

### Attribution without a user
Scheduler jobs, migrations and CLI writes record `actor=system` rather than failing or
guessing. Cron-written tables are excluded anyway, so this should be rare — and worth
seeing when it happens.

---

## 4. Data model

New table `AUDIT_ENTRY`, created by **Alembic revision `0005`** (Alembic is the single
schema-evolution mechanism; `create_all` is guarded against).

| column | type | purpose |
|---|---|---|
| `entry_id` | Integer PK, autoincrement | machine-generated; matches `SAVED_FILTER` / `USER_PREFERENCES` convention |
| `occurred_at` | DateTime(tz), indexed | when |
| `actor_user_id` | String(50), nullable | who; `NULL` ⇒ system |
| `actor_username` | String(100), nullable | **snapshot** — history stays readable after a user is renamed or deactivated |
| `table_name` | String(64), indexed | what kind of entity |
| `record_pk` | String(64) | which entity |
| `operation` | Enum(`INSERT`,`UPDATE`,`DELETE`) | what happened |
| `changes` | JSON | `{field: {old, new}}`, redacted |
| `client_id` | String(50), nullable, indexed | captured when the entity has one |
| `request_method`, `request_path` | String(8) / String(255), nullable | ties an entry to the existing request-level `[AUDIT]` log line |

**`record_pk` as a single string is safe:** every ORM table was checked and all have
**single-column** primary keys. Files with several `primary_key=True` lines
(`alert.py`, `saved_filter.py`, `user_preferences.py`, `calculation_assumption.py`)
contain multiple *tables*, not composite keys. PK types are mixed (`String` for
work orders / users / clients, `Integer` for employees / assignments), so values are
stringified and disambiguated by `table_name`.

**`actor_username` is snapshotted** because a foreign key alone would degrade audit
history exactly as users churn — precisely when it is most needed.

**`client_id` is captured despite admin-only reads.** One nullable column today is the
difference between widening access later via configuration versus a backfill migration
over historical rows whose tenant can no longer be reconstructed.

**Indexes:** `(table_name, record_pk)` — the "history of this entity" query, and the
widget's primary access path; `occurred_at` for recency; `actor_user_id` for
"what did this person do".

---

## 5. Read API

Both endpoints require `get_current_admin`.

### `GET /api/audit`
Paginated, ordered `occurred_at DESC`. Filters: `table_name`, `actor_user_id`,
`client_id`, and a date range.

**Date handling must go through the existing dialect abstraction**, never raw SQL:
`backend/db/dialects/` provides `get_date_diff_sql()` per dialect (sqlite / mysql /
mariadb) and `backend/db/sql_functions.py` registers portable compiled functions.
Bypassing these is how `holds.py` shipped SQLite-only `julianday()` to production —
green in CI, 500 on MariaDB. Range validation uses `validate_date_range()` from
`backend/utils/date_range.py`.

Boundary semantics follow the established convention: because `occurred_at` is a
`DateTime`, an inclusive end date must compare against the **next midnight**, not
against the date at midnight — the DateTime-vs-date boundary bug class already fixed
across 27 sites in this codebase.

### `GET /api/audit/{table_name}/{record_pk}`
One entity's full history. This is the question people actually ask.

Responses emit **JSON numbers, not stringified `Decimal`** — a MariaDB-only
serialization bug class already encountered in this codebase.

Adding routes requires regenerating `backend/tests/test_bootstrap/openapi_surface.json`
or the golden-master gate fails.

---

## 6. Testing

Tests target failure modes, not line coverage.

| area | assertion |
|---|---|
| Capture correctness | insert / update / delete each produce exactly one entry with accurate diffs; setting a field to its existing value produces **no** entry |
| Transactionality | a rolled-back change leaves **zero** audit rows — the property `before_flush` was chosen for, tested rather than assumed |
| Suppression | `audit_suppressed()` writes nothing; an **unsuppressed** bulk write still captures, so the opt-out cannot become ambient |
| Redaction | a password change records the field as changed but persists **neither** hash |
| Authorization | every non-admin role receives 403, pinned in the existing permission-matrix style |
| MariaDB portability | `JSON` column and both endpoints exercised in the `mariadb-portability` job, **importing the production query** rather than re-implementing its shape |

### Structural guards (both negative-tested)

1. **Table completeness** — every ORM table is either audited or excluded **with a
   reason**; a new table fails CI until classified.
2. **Redaction completeness** — no audited table exposes a column matching
   `password|token|secret|api_key|hash` outside `REDACTED_FIELDS`.

Each guard must be proven to fail: add a table and a fake secret column locally,
confirm each guard goes red, then remove them. **A guard that has never failed is not
known to work** — three green-while-dead gates were found in this codebase on
2026-08-11 alone (mocked PDF generation, a rate limiter disabled in tests, and coverage
silently dropping a file).

---

## 7. Scope boundaries

Explicitly **out** of Project A:

- No retention or purge job (D4).
- No UI. The `audit_log` widget belongs to Project B.
- No widening beyond admin (D3).
- **No backfill — owner ruling, 2026-08-11.** Retroactive reconstruction was raised
  explicitly and declined. The trail starts the day it deploys; changes made before
  that are permanently unrecoverable, and that is accepted.

  Two consequences worth carrying forward:
  - An empty result for a historical change is **correct behaviour**, not a bug. The
    read API should make this legible rather than returning a bare empty list — the
    entity-history endpoint reports the trail's start date alongside its results.
  - There is therefore value in deploying A1 sooner rather than later: every day
    without it is a day of change history that cannot be recovered afterwards.

---

## 8. PR sequence

### A1 — capture core
`backend/audit/` (context, capture, registry), `AUDIT_ENTRY` model, Alembic `0005`,
seeder and CSV-import suppression, both structural guards, capture / transactionality /
redaction tests. **No API surface**, so nothing user-visible can regress.

### A2 — read API
Both endpoints, admin authorization, permission-matrix tests,
`openapi_surface.json` regeneration, MariaDB portability coverage.

### Then: deploy + live verification
Deploy to the VM (`docker compose -f docker-compose.prod.yml`, never the bare file),
make a real change through the UI, and confirm the entry appears with correct
attribution, correct before→after values, and no secret material.

---

## 9. What follows — sequencing beyond Project A

**Owner ruling, 2026-08-11:** after A1 and A2 are merged, deployed and verified, work
continues with **Cycle 4 PR-C**, *not* Project B.

Order:

1. **A1 → A2 → deploy + live verify** (this spec)
2. **Cycle 4 PR-C** — reportable-today derivations: DHU, rework-%, transitions dataset,
   priority-adherence definition, changeover, Q4 correlation block, seeder enrichment,
   register re-grades. Each step verified, confirmed with the owner, and explained
   before moving on.
3. **Project B — custom-dashboard widget system** — `/my-dashboard` route, `WidgetGrid`
   mounted, 11 summary + drill-through widgets (en + es i18n, a11y contrast, coverage),
   including the `audit_log` widget consuming Project A's endpoints.

**PR-C is currently blocked on two owner rulings** and cannot start until they are made:

- **(a) Transitions-dataset scope.** Should the transitions dataset also fix the
  *historical-snapshot limitation* in `_active_as_of`? `hold_status` is current state,
  so past `as_of` dates are judged partly by today's status, affecting
  `/wip-aging/trend`. Status-transition history is the only real fix — and it is
  exactly what the transitions dataset would build. Fixing it here changes the
  dataset's shape; building it twice would be wasteful.
- **(b) `priority_adherence` denominator.** Deferred from PR-A explicitly "to PR-C
  spec" and still undefined.

**Consequence to keep visible:** placing PR-C ahead of Project B means the widget
system — and the `audit_log` widget with it — stays unfinished until after PR-C, even
though the owner's intent is to finish it entirely. This is a deliberate ordering
choice, not an oversight.

---

## 10. Context this design depends on

- `WidgetContainer` supplies widget chrome; `dashboardStore.ALL_WIDGETS` carries
  `minRole` for all 16 widgets — relevant to Project B, unblocked by Project A.
- 10 of 11 missing widgets already have backend data sources; `audit_log` was the sole
  gap, which this project closes.
- A `DASHBOARD_WIDGET_DEFAULTS` table already exists — widget defaults are persisted
  server-side.
