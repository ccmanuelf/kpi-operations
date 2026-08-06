# Labor-Hours Accounting — Cycle 3 Design

**Date:** 2026-08-05
**Status:** Approved (user-reviewed brainstorm)
**Roadmap:** Cycle 3 of `docs/superpowers/specs/2026-07-31-reporting-data-capture-roadmap-design.md`; the big Q1 capture (`docs/reporting/reporting-capabilities-and-gaps.md` §4): OT tiers, direct/indirect labor, billed vs available-for-efficiency hours — the Franklin sample's central distinction and the true Q1 denominator.

## 1. Problem

Q1 ("are we efficient?") divides earned hours by a denominator the model cannot currently express. `AttendanceEntry` records only `scheduled_hours`/`actual_hours`; there is no overtime modeling (Normal/Double/Triple is Mexican labor law — structural, not client-specific), no direct/indirect labor distinction (`Employee` has free-text `department`/`position`), and no way to say which present-hours were billed to the client or excluded from the efficiency base (training, meetings, idle). Every hours-based comparison management asks for stalls on these three gaps.

## 2. Decisions (settled in this brainstorm)

1. **OT: captured 3-way split**, not derived from LFT rules. Payroll/HR already computes the split; we record it. No legal-rule engine.
2. **Direct/indirect: employee-level default + per-entry override** (user overrode the YAGNI lean — floaters genuinely switch day-to-day). Effective class = override ?? employee default; NULL = unclassified.
3. **Billed/available: full-fidelity hour-allocation child table** (user chose maximal fidelity over the two-field shortcut), with a controlled 8-category vocabulary carrying static billable/productive metadata.
4. **Categories: 8 including absence-adjacent** (`paid_leave`, `medical`) — the allocation table is the complete intra-day hour ledger; its boundary with the day-level absence mechanism is pinned in §3.4.
5. **Delivery: 2 PRs** — PR-A capture (model → UI → seeders, working end-to-end), PR-B derived Q1 metrics. One spec (this document), one implementation plan per PR.

## 3. Data model

### 3.1 `ATTENDANCE_ENTRY` — OT split + override (4 new nullable columns)

| Column | Type | Meaning |
|---|---|---|
| `normal_hours` | Numeric(5,2) | worked hours paid at 1× |
| `double_hours` | Numeric(5,2) | OT at 2× (LFT) |
| `triple_hours` | Numeric(5,2) | OT at 3× (LFT) |
| `labor_class_override` | String(10) | per-day override of the employee's labor class |

**Split invariant:** all three NULL = unsplit (optional-first default). If ANY of the three is supplied, the submission is a complete split: absent members default to 0 and `normal + double + triple` must equal `actual_hours` exactly → otherwise **422** naming the rule. (A split with no `actual_hours` on the entry is likewise 422.)

### 3.2 `EMPLOYEE.labor_class` (1 new nullable column, String(10))

`direct` / `indirect` / NULL (unclassified). Existing free-text `department`/`position` untouched.

### 3.3 NEW table `ATTENDANCE_HOUR_ALLOCATION`

| Column | Type | Notes |
|---|---|---|
| `allocation_id` | Integer PK autoincrement | |
| `attendance_entry_id` | FK → ATTENDANCE_ENTRY, indexed, ON DELETE CASCADE | |
| `category` | String(30) | `HourCategoryEnum` value, validated |
| `hours` | Numeric(5,2) | > 0 |

Unique constraint on (`attendance_entry_id`, `category`). Written replace-on-write per entry (the API accepts the full list; no per-row PATCH surface).

### 3.4 Taxonomy — `backend/orm/labor_taxonomy.py` (Cycle 1/2 module pattern)

- `LaborClassEnum(str, Enum)`: `DIRECT = "direct"`, `INDIRECT = "indirect"`.
- `HourCategoryEnum(str, Enum)`: `BILLED_PRODUCTION = "billed_production"`, `UNBILLED_PRODUCTION = "unbilled_production"`, `TRAINING = "training"`, `MEETING = "meeting"`, `IDLE_WAIT = "idle_wait"`, `OTHER_NONPRODUCTIVE = "other_nonproductive"`, `PAID_LEAVE = "paid_leave"`, `MEDICAL = "medical"`.
- Static metadata: `BILLABLE_CATEGORIES = {billed_production}`; `PRODUCTIVE_CATEGORIES = {billed_production, unbilled_production}`.
- ORM `@validates` on `Employee.labor_class`, `AttendanceEntry.labor_class_override`, `AttendanceHourAllocation.category` (None allowed where nullable; invalid → ValueError), mirroring Cycles 1–2.

**Derived quantities (computed, never stored):**
- `billed_hours = Σ hours over BILLABLE_CATEGORIES`
- `available_for_efficiency_hours = actual_hours − Σ hours over (allocated ∖ PRODUCTIVE_CATEGORIES)` — i.e. the unallocated remainder counts as productive-unbilled, so missing capture can never inflate efficiency.
- `effective_labor_class = labor_class_override ?? employee.labor_class` (may be NULL = unclassified).

**Allocation invariant:** `Σ allocations ≤ actual_hours` → **422** otherwise.

**Absence boundary (pinned):** `paid_leave`/`medical` allocations represent *intra-day paid hours*. The day-level `is_absent`/`AbsenceType` mechanism is untouched and remains authoritative for whole-day absence classification. No reconciliation between the two is required or enforced.

### 3.5 Migration `0004_labor_hours_columns`

`down_revision = "0003_justified_delay"`. DDL: 4 `add_column` on ATTENDANCE_ENTRY, 1 on EMPLOYEE, `create_table` ATTENDANCE_HOUR_ALLOCATION with FK/index/unique. Downgrade drops in reverse. No data pass. Both CI migration lanes.

## 4. API (PR-A)

- **Attendance create/update** schemas gain the three split fields (`Optional[Decimal]`), `labor_class_override: Optional[LaborClassEnum]`, and `allocations: Optional[list[AllocationItem]]` where `AllocationItem = {category: HourCategoryEnum, hours: Decimal > 0}`. Update semantics: omitted = no change; supplied `allocations` list replaces the entry's allocations wholesale; empty list clears. Duplicate categories in one payload → 422.
- Invariants enforced in the attendance update path with exact codes: split-sum rule (§3.1) → 422; allocation-sum rule (§3.4) → 422; enum violations → 422 (Pydantic).
- **Attendance responses** gain: the four columns, `allocations` list, and derived `billed_hours`, `available_for_efficiency_hours`, `effective_labor_class`.
- **Employee admin** create/update gain `labor_class: Optional[LaborClassEnum]`; response carries it.
- **Authorization unchanged:** each field rides its host surface's existing guard (attendance entry = contributor tier as today; employee admin = its current planner/admin guard). No new tiers, no field-level carve-outs.
- CSV upload (attendance flow) accepts the three split columns + `labor_class_override` (allocations are NOT in CSV scope this cycle — the 1:N shape doesn't fit the flat row format; documented limitation).

## 5. Entry UI (PR-A)

- **Attendance grid** (`useAttendanceGridData` surface): three OT split columns (numeric editors), `labor_class_override` select (direct/indirect/— where — clears), and an **allocations dialog** per row (button cell: compact `Σallocated/actual` summary; dialog lists category selects + hour inputs with add/remove, validates client-side against the same rules, submits the full list). No low-contrast placeholders anywhere (empty cells for absent values — the Cycle 2 a11y lesson is a standing rule).
- **Employee admin** gains the `labor_class` select (3 options incl. Unclassified→null).
- **Completeness chips** on the attendance screen: `N without OT split`, `N unallocated` (visible when > 0) — the capture-policy indicators.
- i18n en + es, static keys (`labor.*` block); referenced-keys gate.

## 6. Derived Q1 metrics (PR-B)

- **`GET /api/kpi/labor-hours`** (client-scoped via `resolve_client_scope`, date-range): totals `{scheduled, actual, normal, double, triple, billed, available_for_efficiency}`, rollups by `effective_labor_class` `{direct, indirect, unclassified}`, and allocation totals by category. All JSON numbers (no Decimal leakage — standing rule).
- **Available-hours efficiency variant — REVISED 2026-08-06 (USER RULING, fix round 1):** the original design below shipped as a dashboard bolt-on and was live-proven 16 points off (average-of-averages + mismatched scheduled sources); it was reverted. The honest metric instead lives on `GET /api/kpi/labor-hours` as a TRUE ratio of SUMS over the same window/scope: `efficiency_available_basis = earned_hours / available_for_efficiency × 100`, where `earned_hours = Σ(units_produced × ideal_cycle_time)` over `ProductionEntry` rows in scope (`backend.calculations.labor_hours.earned_hours`; per-entry `ideal_cycle_time` resolves to the entry's own value, else its product's default — entries with neither are EXCLUDED, never guessed, and counted in the response's `excluded_entries` so the ratio can't silently look complete). `None` when the window has no attendance data at all, or `available_for_efficiency` is <= 0. Entries without allocation data still contribute their full actual hours toward `available_for_efficiency` (per §3.4's conservative default, unchanged). Existing `labor-hours` fields (totals/by_labor_class/by_category/entry_counts) unchanged; the reverted dashboard endpoint (`GET /api/kpi/dashboard`) is byte-identical to its pre-fix-round state.
  <details><summary>Original 2026-08-05 design (superseded)</summary>

  Available-hours efficiency variant (additive): the efficiency KPI response gains `efficiency_available_basis` alongside the existing scheduled-hours figure — same formula with `available_for_efficiency` as denominator, only where attendance links permit; entries without allocation data contribute their full actual hours (per §3.4's conservative default). Existing efficiency values unchanged.
  </details>
- **Excel comprehensive** gains Labor Hours rows (billed vs available vs actual; OT tier totals) — zero-data guarded (no fake rows on empty windows; Cycle 2 lesson).
- New route → `openapi_surface.json` regen (this cycle DOES add a path, unlike Cycles 1–2).
- No new screens; pivots remain Cycle 4.

## 7. Seeders (PR-A)

Deterministic, both seeders: OT splits on a fixed cadence (most days all-normal; every Nth entry a double-hours day; rare fixed triple), `labor_class` majority-direct with a fixed minority indirect + sparse per-entry overrides, allocations mostly `billed_production` with a rotating minority slot covering **all 8 categories across the seeded dataset — exact-set asserted in seeder tests** (the gcd-rotation lesson: coverage counters independent of selection-pattern moduli).

## 8. Testing

- Taxonomy/ORM validator tests; migration up/down (SQLite + MariaDB lanes); split & allocation invariants with exact 422s; replace-on-write semantics; derived-value tests with hand-math derivation comments; effective-class resolution (override/default/NULL matrix).
- Permission matrix: confirm the new fields ride existing guards (no new rows needed beyond host-surface coverage — assert one denial case per surface anyway).
- Frontend: composable unit tests (column defs, dialog logic in pure helpers, completeness counts); allocation-dialog validation; one Playwright guard (enter OT split + allocations on a row, save, derived summary updates); a11y gate must stay 0-violations.
- PR-B: metric endpoint derivations (exact values), efficiency-variant additivity (existing values byte-identical), Excel row assertions, openapi surface regen.
- Full suites green both PRs; coverage ≥75 %.

## 9. Delivery & success criteria

PR-A `feat/labor-hours-capture` (this branch) → full pipeline → user-confirmed merge → deploy Render + VM (migration 0004) → re-seed → live-verify capture (§10-A: split entry, allocation dialog, derived fields on API, completeness chips). Then PR-B `feat/labor-hours-metrics` → same pipeline → live-verify metrics (§10-B: labor-hours endpoint totals match seeded math, efficiency variant present, Excel rows).

Concept register Q1 re-grades (in PR-B, when the full story ships): OT tiers missing → **have**; direct vs indirect missing → **have**; billed vs available-for-efficiency missing → **have**; operator attendance vs available hours partial → **have**. §5 Cycle 3 line marked DONE.

## 10. Out of scope

- Operator-level production capture (deferred remainder — different concept).
- Pay rates / labor cost in currency (tiers give the multipliers; money needs rate capture — a future product decision).
- Allocation CSV round-trip (flat-format mismatch; documented).
- LFT rule automation of any kind.
- Flip-to-required for any new field (capture policy: separate later change).
- Time-bucketed labor pivots (Cycle 4).
