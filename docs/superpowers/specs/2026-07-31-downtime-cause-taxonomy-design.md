# Downtime Cause Taxonomy — Cycle 1 Design

**Date:** 2026-07-31
**Status:** Approved (user-reviewed brainstorm)
**Roadmap:** Cycle 1 of `docs/superpowers/specs/2026-07-31-reporting-data-capture-roadmap-design.md`; answers management question **Q2 — what impacts are causing downtime?** (`docs/reporting/reporting-capabilities-and-gaps.md` §4).

## 1. Problem

Downtime attribution today is four inconsistent vocabularies and one silent correctness bug:

1. `DowntimeReasonEnum` (`backend/schemas/downtime.py`): 7 values, enforced **only** on the Pydantic API path — the seeder writes `CHANGEOVER` and `PLANNED_MAINTENANCE` (not in the enum) straight through the ORM.
2. `root_cause_category` (`backend/orm/downtime_entry.py:49`): optional free text, edited as a free-text grid column, NULL in all seeded data.
3. `/api/reference/downtime-reasons` (`backend/routes/reference.py:104`): a hardcoded 9-item vocabulary (mechanical/electrical/…) unrelated to either field, consumed by `productionDataStore` → MyShift downtime dialog.
4. `useShiftForms.ts:139`: another hardcoded 7-label list for shift-form selects.
5. **Bug:** `backend/calculations/availability.py:86,129` filters `root_cause_category IN ("Breakdown", "Failure", "Equipment Failure", "Maintenance")` — values no vocabulary produces and no data contains, so the planned-vs-unplanned downtime distinction is dead in availability calculations.

## 2. Decisions (settled in this brainstorm)

1. **Field model:** the management taxonomy lives in `root_cause_category`; `downtime_reason` stays the operational what-happened field. Category auto-defaults from reason when the operator doesn't override.
2. **NPT structure:** the two-level taxonomy IS the `(root_cause_category, downtime_reason)` pair — category = management bucket, reason = NPT/operational bucket. No third field, no compound values.
3. **Storage:** static code-level enums + i18n labels (structural, cross-client, like `UserRole`). No catalog table; per-client custom values are a deferred extension.
4. **Adjacent fixes in scope:** availability phantom-filter bug, reference-endpoint vocabulary, seeder rogue values — all fixed this cycle (no-tech-debt bar). The `useShiftForms` hardcoded list consolidates too.
5. **Reporting this cycle:** minimal rollup only (Excel by-category block + `category` filter on the downtime listing); time-bucketed pivots wait for Cycle 4.

## 3. Vocabulary

### 3.1 Categories — new `DowntimeCategoryEnum` (level 1, management attribution)

| Value | Label (en) | Notes |
|---|---|---|
| `machine` | Machine | equipment, maintenance |
| `materials` | Materials | supply/material waits |
| `scheduling` | Scheduling | changeover/setup, plan-driven waits |
| `attendance` | Attendance | labor unavailability |
| `other` | Other | catch-all incl. facility events |
| `uncategorized` | Uncategorized | **legacy-only**: assigned by migration/back-compat, never offered in any UI select |

### 3.2 Reasons — `DowntimeReasonEnum` (level 2, NPT/operational), formalized

Existing 7 values unchanged: `EQUIPMENT_FAILURE`, `MATERIAL_SHORTAGE`, `SETUP_CHANGEOVER`, `QUALITY_HOLD`, `MAINTENANCE`, `POWER_OUTAGE`, `OTHER`. One addition: **`OPERATOR_UNAVAILABLE`** (the attendance category needs an operational reason).

### 3.3 Default mapping reason → category (single source of truth, backend constant; served to the frontend via the reference endpoint)

| Reason | Default category |
|---|---|
| `EQUIPMENT_FAILURE` | `machine` |
| `MAINTENANCE` | `machine` |
| `MATERIAL_SHORTAGE` | `materials` |
| `SETUP_CHANGEOVER` | `scheduling` |
| `OPERATOR_UNAVAILABLE` | `attendance` |
| `QUALITY_HOLD` | `other` |
| `POWER_OUTAGE` | `other` |
| `OTHER` | `other` |

Auto-default semantics: on create/update, if `root_cause_category` is absent/NULL, the backend applies the mapping from `downtime_reason`. An explicitly supplied valid category is never overwritten. `uncategorized` is accepted on input only for back-compat (CSV re-upload of legacy exports) — new UI entry always produces a real category.

### 3.4 Enforcement layers

- **Pydantic:** `root_cause_category: Optional[DowntimeCategoryEnum]` on create/update schemas; unknown values → 422 listing accepted values. `downtime_reason` already enum-typed.
- **ORM:** SQLAlchemy `@validates` on both `downtime_reason` and `root_cause_category` in `DowntimeEntry` (DB-agnostic; closes the seeder-style bypass). Raises `ValueError` on non-enum values; `root_cause_category=None` remains allowed at ORM level (auto-default happens in the route/service layer, and legacy code paths must not crash).
- **Physical column unchanged:** `String(100)`, nullable — no destructive DDL, MariaDB/SQLite portable.

## 4. Migration (Alembic, data-only, new revision)

Upgrade backfills `DOWNTIME_ENTRY` in two passes:

**Pass A — normalize `downtime_reason` (case-insensitive match):**

| Existing value | Becomes |
|---|---|
| `CHANGEOVER` | `SETUP_CHANGEOVER` |
| `PLANNED_MAINTENANCE` | `MAINTENANCE` |
| any valid enum value | unchanged |
| anything else | `OTHER` (original value preserved by appending `[legacy reason: <value>]` to `notes`) |

**Pass B — backfill `root_cause_category` (case-insensitive match on the current value):**

| Existing value (free text) | Becomes |
|---|---|
| `breakdown`, `failure`, `equipment failure`, `mechanical`, `electrical`, `maintenance`, `planned maintenance`, `machine` | `machine` |
| `material`, `material shortage`, `materials`, `supply` | `materials` |
| `changeover`, `setup`, `scheduling` | `scheduling` |
| `operator`, `labor`, `absenteeism`, `attendance` | `attendance` |
| `other` | `other` |
| NULL | default mapping from the row's (already-normalized) `downtime_reason` (§3.3) |
| anything else | `uncategorized` (original value preserved by appending `[legacy category: <value>]` to `notes`) |

Downgrade: no-op with an explanatory comment — original free text is not recoverable (preserved only in `notes` where it was overwritten). Executed with portable SQLAlchemy `UPDATE` statements (no dialect-specific SQL); covered by the existing SQLite + MariaDB CI migration lanes.

## 5. Adjacent fixes

### 5.1 `availability.py` planned-vs-unplanned (bug fix)

Both phantom `root_cause_category IN (...)` filters are replaced with reason-based definitions:
- **Planned downtime** = `downtime_reason IN (MAINTENANCE, SETUP_CHANGEOVER)`
- **Unplanned downtime** = all other reasons

The two call sites at `availability.py:86` and `:129` adopt these sets per their existing intent (the `:129` site, which today adds "Maintenance", is the planned-inclusive variant). Existing availability tests are updated to seed reasons instead of phantom categories; expected values re-derived and asserted exactly.

### 5.2 `/api/reference/downtime-reasons` (single source of truth)

Rewritten to serve the taxonomy: for each reason — `{id: <enum value>, label_key: <i18n key>, default_category: <category enum value>}` — plus a `categories` list `{id, label_key}` (excluding `uncategorized`). Response shape changes; both known consumers migrate in this PR:
- `productionDataStore.downtimeReasons` + MyShift downtime dialog (`ShiftDashboardDialogs.vue`): select binds enum ids, displays i18n labels.
- `useShiftForms.ts:139` hardcoded list + its `downtimeReasonToCode()` mapper: deleted; the composable consumes the store/reference data.
`frontend/src/services/api/kpi.ts:320` (`reasonsMap`) is audited and adapted if it reads the old shape. `openapi_surface.json` regenerated (response model change).

### 5.3 Seeder (`backend/scripts/_seed_operations.py`)

Seeds valid `(reason, category)` pairs: reason drawn from the real enum (rogue strings removed), category via the default mapping with a deterministic minority (~10%) of explicit overrides (e.g. `EQUIPMENT_FAILURE` attributed to `scheduling`) so the demo shows override capability. No `uncategorized` rows seeded — the demo story is a fully-adopted taxonomy; `uncategorized` visibility is exercised by tests instead.

## 6. Entry UI (`useDowntimeGridData.ts` + downtime entry screen)

- Both grid columns become select editors: reason (8 values), category (5 real values — `uncategorized` not offered but rendered if present).
- Reason change auto-fills the default category **unless** the user explicitly set a different category on that row in this session (dirty-tracking flag per row).
- `uncategorized` cells get the existing OOC-style highlight; the downtime screen header shows an "N uncategorized" count (visible only when N > 0) — this is the roadmap's completeness indicator.
- CSV upload (`csv_upload.py` downtime flow): values validated through the same Pydantic enums; error messages list accepted values. Legacy exports containing `uncategorized` re-import cleanly (§3.3 back-compat).
- All labels via i18n (en + es); keys pass the referenced-keys gate.

## 7. Reporting rollup (minimal)

- **Excel Downtime Analysis sheet** (`excel_generator.py`): adds a by-category subtotal block (category, events count, total minutes, % of total) above the existing detail listing. Categories render via their display labels; `uncategorized` appears when present.
- **Downtime listing** (`routes/downtime.py` list endpoint): gains optional `category` query filter (enum-validated).
- CSV export shape unchanged (`root_cause_category` column already exported).

## 8. Testing

- Unit: enum members, default-mapping completeness (every reason maps; property test that mapping targets are valid categories), auto-default semantics (absent → mapped; explicit → preserved), ORM validators reject invalid values.
- Migration: both passes asserted on seeded fixture rows (rogue reasons, phantom categories, NULLs, already-valid, unknown junk → notes preservation) — runs under the existing SQLite and MariaDB CI migration checks.
- Availability: updated tests derive planned/unplanned from reasons; exact expected values (no permissive assertions).
- Reference endpoint: response-shape test; characterization for both frontend consumers via their existing spec files.
- Frontend: composable unit tests for select options + auto-fill dirty-tracking; one Playwright guard — pick a reason on the downtime grid, assert category auto-fills, override it, assert it sticks.
- Gates: referenced-keys i18n, `openapi_surface.json` regen, coverage ≥75% backend / frontend thresholds, 7-check CI.

## 9. Delivery

Single PR on branch `feat/downtime-cause-taxonomy` (cohesive: capture + backfill + consumers must land together to avoid a half-state). Standard pipeline: plan → subagent-driven execution → /cross-review → PR → CI green → user-confirmed merge → deploy Render + VM (migration runs via `RUN_MIGRATIONS_ON_STARTUP`/entrypoint) → VM re-seed (`--reset`, with explicit `--client SAMPLE_REF` run) → live-verify.

## 10. Success criteria

- Concept register Q2: cause taxonomy **partial → have**; NPT categorization **partial → have** (re-graded in the living doc in this PR).
- Live on VM MariaDB: migration backfills real rows (spot-checked), grid selects + auto-fill work, availability planned/unplanned shifts explainably, Excel by-category block populated, `/api/reference/downtime-reasons` serves the taxonomy.
- No remaining hardcoded downtime vocabulary anywhere in the codebase (grep-verified: the four §1 sources are consolidated).

## 11. Out of scope

- Per-client custom vocabularies (deferred extension; revisit only on client demand).
- Flip-to-required for `root_cause_category` (separate small change per the roadmap's capture policy — with auto-default, completeness should sit near 100% immediately).
- Time-bucketed downtime pivots, cross-metric views (Cycle 4).
- Any change to `HoldEntry` reason catalogs (different subsystem, already healthy).
