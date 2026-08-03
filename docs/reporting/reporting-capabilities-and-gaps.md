# Reporting: Capabilities, Gaps, and Decisions

**Status:** Living document — updated as new client report samples arrive.
**Spec:** docs/superpowers/specs/2026-07-29-reporting-capability-and-gap-decision-design.md

## 1. Committed positions

**No carbon-copying of client Excel reports.** Every client's workbook differs in content, format, tags, colors, and headers — confirmed across two samples from two different clients (PGI's production/status/delivery workbook and Franklin Products' attendance workbook). The app observes the *concepts* behind these reports, never their layouts. Management explicitly requested this position, and it is treated as permanent: any future request to replicate a specific client's spreadsheet is out of scope by design.

**Data-first, not chart-first.** Reports exist to summarize data, and every on-screen summary must be downloadable as the underlying data behind it. Charts are optional garnish, never the deliverable — a configurable plotting or charting mechanism is explicitly not a product goal. This is why the Excel "Trend Charts" placeholder sheet is removed rather than built out (§3).

**No reports without underlying data (capture-first rule).** A report may only be built over metrics kpi-operations actually tracks. Concepts graded **missing** in the concept register (§4) — for example shipments, stock, billed hours, or cut quantities — are *capture-first*: adding the data capture itself is its own deliberate product decision, and is never a side effect of a reporting spec. Concepts already graded **have** or **partial** are welcome report additions today.

**Capture-first focus (management decision, 2026-07-30).** No further client report samples are coming — management chose this deliberately to avoid Excel reconstruction. The engagement shifts to **data capture** for the five key operations questions (§4): downtime cause taxonomy, justified-delay classification, and labor-hours accounting, followed by a pivot/summarization layer built once over the enriched data. Sequencing lives in §5; roadmap spec: `docs/superpowers/specs/2026-07-31-reporting-data-capture-roadmap-design.md`.

## 2. What works today — report catalog

Every endpoint below is verified present in `backend/tests/test_bootstrap/openapi_surface.json` (Step 1 of this task) and its role requirement is read directly from the `Depends(...)` guard on the route, not inferred. Guard functions live in `backend/auth/jwt.py`; the six-role enum and role-tier lists (`PLANNER_ROLES`, `SUPERVISORY_ROLES`, `CONTRIBUTOR_ROLES`) they check against live in `backend/orm/user.py`:

- **Authenticated** — `get_current_user` (`backend/auth/jwt.py`): any of the six roles (admin, poweruser, leader, supervisor, operator, viewer).
- **Supervisory tier** — `get_current_active_supervisor` (`backend/auth/jwt.py`): admin, poweruser, leader, supervisor (excludes operator and viewer).

### (a) PDF reports — type-aware via `kpis_to_include`

| Endpoint | Method | Formats | Key params | Role required | What it contains |
|---|---|---|---|---|---|
| `/api/reports/production/pdf` | GET | PDF | `client_id` (optional), `start_date`, `end_date` | Authenticated | KPIs: efficiency, performance, availability, OEE |
| `/api/reports/quality/pdf` | GET | PDF | `client_id` (optional), `start_date`, `end_date` | Authenticated | KPIs: FPY, RTY, PPM, DPMO |
| `/api/reports/attendance/pdf` | GET | PDF | `client_id` (optional), `start_date`, `end_date` | Authenticated | KPIs: absenteeism |
| `/api/reports/comprehensive/pdf` | GET | PDF | `client_id` (optional), `start_date`, `end_date` | Authenticated | All KPIs (`kpis_to_include=None`): efficiency, performance, availability, OEE, FPY, RTY, PPM, DPMO, absenteeism, on-time delivery |

### (b) Excel reports — type-aware via sheet selection (this PR)

| Endpoint | Method | Formats | Key params | Role required | What it contains (sheets) |
|---|---|---|---|---|---|
| `/api/reports/production/excel` | GET | Excel (.xlsx) | `client_id` (optional), `start_date`, `end_date` | Authenticated | Executive Summary, Production Metrics, Downtime Analysis |
| `/api/reports/quality/excel` | GET | Excel (.xlsx) | `client_id` (optional), `start_date`, `end_date` | Authenticated | Executive Summary, Quality Metrics |
| `/api/reports/attendance/excel` | GET | Excel (.xlsx) | `client_id` (optional), `start_date`, `end_date` | Authenticated | Executive Summary, Attendance |
| `/api/reports/comprehensive/excel` | GET | Excel (.xlsx) | `client_id` (optional), `start_date`, `end_date` | Authenticated | All five sheets: Executive Summary, Production Metrics, Quality Metrics, Downtime Analysis, Attendance |

Before this PR, all four Excel endpoints returned an identical six-sheet workbook regardless of type (including a "Trend Charts" placeholder sheet with no real chart data); availability was hardcoded to `85.0` (PDF) / `90.0` (Excel) instead of being computed. Both are fixed as of this PR — see §3.

### (c) Report catalog listing

| Endpoint | Method | Formats | Key params | Role required | What it contains |
|---|---|---|---|---|---|
| `/api/reports/available` | GET | JSON | none | Authenticated | Machine-readable list of the four report types (production, quality, attendance, comprehensive), their PDF/Excel endpoints, and the shared query parameters |

### (d) Email configuration and manual send

| Endpoint | Method | Formats | Key params | Role required | What it contains |
|---|---|---|---|---|---|
| `/api/reports/email-config` | GET | JSON | `client_id` (optional) | Authenticated | Current email report configuration (enabled, frequency, recipients, content toggles) for the client, or a default if none saved |
| `/api/reports/email-config` | POST | JSON | body: `EmailReportConfig` | Supervisory tier | Creates/overwrites email report configuration |
| `/api/reports/email-config` | PUT | JSON | body: `EmailReportConfig` | Supervisory tier | Updates an existing email report configuration (404 if none exists) |
| `/api/reports/email-config/test` | POST | JSON | body: `email` | Supervisory tier | Sends a test email to verify delivery configuration |
| `/api/reports/send-manual` | POST | JSON (triggers PDF generation + email) | body: `client_id`, `start_date`, `end_date`, `recipient_emails` | Supervisory tier | Generates a comprehensive PDF report on demand and emails it to the given recipients |

Note (gap, tracked in §3): the email configuration is stored in an in-memory dict (`_email_configs` in `backend/routes/reports/email_config.py`), not a database table, so it does not survive a process restart; the six `include_*` content toggles on `EmailReportConfig` are accepted and stored but never read by the generators; and there is no scheduler that honors the configured `frequency` (daily/weekly/monthly) or recipients.

### (e) Assumption variance report

| Endpoint | Method | Formats | Key params | Role required | What it contains |
|---|---|---|---|---|---|
| `/api/assumptions/variance` | GET | JSON | `stale_after_days` (default 365) | Authenticated | One row per active calculation assumption, with the catalog default, deviation magnitude, and an `is_stale` flag. Row *scope* (not route access) depends on role: admin/poweruser see assumptions across all sites; every other role sees only their own tenant's assumptions, per `AssumptionService.get_variance_report`. The route guard itself is `get_current_user` (any authenticated role), not an admin-only guard — access is gated by scope inside the service, not by the endpoint. |

### (f) CSV entity exports — the data-first backbone

| Endpoint | Method | Formats | Key params | Role required | What it contains |
|---|---|---|---|---|---|
| `/api/export/production-entries` | GET | CSV | `client_id`, `start_date`, `end_date`, `line_id` (all optional) | Authenticated | Production entries |
| `/api/export/work-orders` | GET | CSV | `client_id`, `start_date`, `end_date` (all optional) | Authenticated | Work orders |
| `/api/export/quality-inspections` | GET | CSV | `client_id`, `start_date`, `end_date` (all optional) | Authenticated | Quality inspection entries |
| `/api/export/downtime-events` | GET | CSV | `client_id`, `start_date`, `end_date` (all optional) | Authenticated | Downtime events |
| `/api/export/attendance` | GET | CSV | `client_id`, `start_date`, `end_date` (all optional) | Authenticated | Attendance entries |
| `/api/export/employees` | GET | CSV | `client_id` (optional) | Authenticated | Employee master data |
| `/api/export/products` | GET | CSV | `client_id` (optional) | Authenticated | Product master data |
| `/api/export/shifts` | GET | CSV | `client_id` (optional) | Authenticated | Shift master data |
| `/api/export/holds` | GET | CSV | `client_id`, `start_date`, `end_date` (all optional) | Authenticated | Hold entries |

These nine per-entity exports are the concrete expression of the data-first position (§1): every entity behind the PDF/Excel/summary reports above is independently downloadable as raw CSV, matching the CSV upload column format for round-trip compatibility.

## 3. Gap register — decisions

| Gap | Decision | Status |
|---|---|---|
| Excel ignores report type (identical 6-sheet workbook for all 4 types) | **Make real now** — PR item 1 | **DONE with this PR** — sheet selection implemented, see §2(b) |
| Placeholder availability values (85.0 / 90.0) | **Make real now** — PR item 2 | **DONE with this PR** — availability now computed from run/downtime hours via the same canonical formula (`calculate_availability_pure` in `backend/calculations`) the dashboard uses; the *formula* is shared, but the *inputs* differ by context — reports use `run_time_hours + downtime_hours` from `ProductionEntry`, `routes/kpi/dashboard.py` uses run-only hours plus `DowntimeEntry` minutes, and `routes/kpi/trends.py` uses `entries × 8h` — so reported and dashboard values will generally differ |
| Placeholder "Trend Charts" sheet | **Remove now** — PR item 3 (charts are explicitly not the product) | **DONE with this PR** — `_create_charts_sheet` removed from `excel_generator.py` |
| Email content toggles never consumed | **Defer** to report-subscriptions spec; hide/mark now (PR item 4) | **DONE with this PR** — the six `include_*` toggles were **removed from the dialog template** (not hidden behind a flag, not relabeled as inactive); the `EmailReportConfig` payload contract is unchanged, so the fields are still accepted and stored, just no longer offered in the UI (UI-visibility change) / functional wiring still deferred |
| Email config in-memory only | **Defer** — same spec | Deferred |
| Scheduler daily-only, ignores frequency/recipients | **Defer** — same spec | Deferred |
| Pivot/summarization layer | **Active lane — Cycle 4** (§5); the remaining-samples blocker was dissolved by the 2026-07-30 management decision | Sequenced (§5) |
| Downtime cause taxonomy | **Active lane — Cycle 1** (§5) — small, high leverage for Q2 | **DONE — Cycle 1 PR**: two-level (category, reason) taxonomy, auto-default, backfill migration, availability planned/unplanned fixed |
| Labor-hours accounting (OT tiers, direct/indirect, billed vs available) | **Active lane — Cycle 3** (§5) — prerequisite for full Q1 | Sequenced (§5) |
| Workbook replication | **Rejected permanently** — concepts, not layouts | Rejected (permanent, see §1) |

## 4. Concept register (living)

The register is organized under the five management questions the reporting effort is meant to answer. Each concept carries a readiness grade — **have**, **partial**, or **missing** — assessed against the ORM and endpoints at `main` @ `322c727`.

### Q1 — Are we efficient?

*"Are we making as much production as the allocated hours allow?"* SAM is the exchange rate that puts everything in hours: units × SAM = earned hours, compared against paid, attendance, capacity, and billed hours.

| Concept | Readiness | Notes |
|---|---|---|
| SAM per style | **have** | `WorkOrder.ideal_cycle_time` / `ProductionEntry.ideal_cycle_time` (decimal hours/unit; SAM minutes = ×60) |
| Unit quantities vs labor hours | **have** | `ProductionEntry.units_produced`, `run_time_hours`, `employees_assigned/present` |
| Units processed vs capacity allocated (hours) | **partial** | capacity planning module exists; no earned-vs-allocated comparison report |
| Operator attendance vs available hours to commit | **partial** | `AttendanceEntry.scheduled_hours/actual_hours` exist; no "available for efficiency" derivation |
| Shipped units vs billed hours | **missing** | no billed-hours concept anywhere in the model |
| OT tiers (Normal/Double/Triple) | **missing** | no overtime modeling; double/triple is Mexican labor law, structural not client-specific |
| Direct vs indirect labor | **missing** | `Employee` has free-text `department`/`position` only |
| Billed vs available-for-efficiency hours | **missing** | the Franklin sample's central distinction; the true Q1 denominator |
| Operator-level daily efficiency | **missing** | production is recorded at line level, not per operator (industry standard is per-operator daily, rolled up weekly) |
| Efficiency benchmarks | n/a | cite 40–55% / 65–75% / 80%+ tiers for context in reports |

### Q2 — What impacts are causing downtime?

Attribution across **machine / materials / scheduling / attendance / other**.

| Concept | Readiness | Notes |
|---|---|---|
| Downtime capture | **have** | `DowntimeEntry.downtime_reason` (required, indexed), `ProductionEntry.downtime_hours` |
| Cause taxonomy | **have** | controlled 5-category vocabulary over `root_cause_category` + 8-reason enum, auto-default mapping (Cycle 1) |
| NPT categorization | **have** | reason enum is the NPT level; (category, reason) pair queryable (Cycle 1) |

### Q3 — Are we producing to the expected quality bar?

| Concept | Readiness | Notes |
|---|---|---|
| Units subject to rework | **have**/**partial** | `rework_count` per entry (have); "as a function of the entire order" needs per-work-order rollup (partial) |
| Units started to meet order requirement (cut-to-ship ratio) | **missing** | model records output units, not started/issued units |
| Shipping late (OTD) | **have** | `planned_ship_date` vs `actual_delivery_date`; OTD KPI live |
| Justified vs unjustified lateness | **missing** | no classification field; PGI's Delivery Performance excludes justified delays |
| Skipping priorities | **partial** | `priority` + `DEMOTED` state exist; no priority-adherence metric |
| DHU (Defects per Hundred Units) | **partial** | `defect_count` stored; DHU computable but not reported |
| Estimated AQL from actuals | **missing** | not modeled; DHU is its computable precursor |

### Q4 — Is re-shuffling causing holes in production or downtime?

**Partial** — `DEMOTED` transitions are first-class in the workflow engine, so churn is countable; the missing piece is the *correlation*: demotions/re-sequencing linked to idle gaps and scheduling-category downtime. This is a metric-definition gap for the pivot layer, not a data-model hole. Style changeover time is adjacent (**partial** — `setup_time_hours` exists, no changeover report).

### Q5 — Are we keeping material on hold? What constraint, where, why?

**Have** (strongest area) — `HoldEntry` with catalog-backed `hold_reason` (`HOLD_REASON_CATALOG`), `hold_reason_category`, description; WIP-aging endpoints live (stalled / old / past-due triad shipped with the diagnostic-charts work). Open point: whether holds carry line/area attribution for the "where".

### Reportable today vs capture-first

Per the "no reports without underlying data" position (§1), the register splits two ways:

- **Reportable today** (data already tracked — welcome additions): DHU (from `defect_count`), rework as % of order (per-work-order rollup of `rework_count`), OTD, WIP triad (stalled/old/past-due), hold-reason/category breakdowns, demotion-churn counts and priority adherence (from `DEMOTED` transitions + `priority`), downtime by reason, per-type report sheets, real availability, earned-hours efficiency from `ideal_cycle_time` × units vs `run_time_hours`.
- **Capture-first** (no underlying data — requires a product decision to start tracking before any report exists): shipments (shipment #), stock/inventory, billed hours and rates, OT tiers, direct/indirect classification, cut/started quantities, material-batch traceability, justified-delay classification, operator-level production, plant/module hierarchy.

### Structural observations (cross-question)

- **Plant → Module/Cell → Line hierarchy**: the app models lines only; nothing above. Open modeling question.
- **Missing commercial/traceability fields** (from the PGI ledger): shipment #, material-batch (OB) references, customer-PO reference, garment size as a first-class field.
- Absence codes (U/V/…) map onto the existing `AbsenceType` enum — **have**.

### How to update this register

Each new client report sample gets analyzed the same way the two evidence samples in the spec were: identify every concept the client's report exposes, slot it under one (or more) of the five management questions above, and grade it have/partial/missing against the current ORM and endpoint surface. Grades get revised in place — a concept can move from missing to partial to have as capture work lands. Anything newly graded missing is not built directly; it is routed to the roadmap's deferred remainder (§5) as a capture-first item, since a report may never be the vehicle that introduces a new data capture.

## 5. Roadmap — active lane and deferred remainder

Sequenced per the approved roadmap spec (`docs/superpowers/specs/2026-07-31-reporting-data-capture-roadmap-design.md`, 2026-07-31). Every cycle still requires its own brainstorm→spec cycle before any build.

### Active lane (in order)

1. **Cycle 1 — Downtime cause taxonomy** (Q2; smallest, highest leverage): controlled vocabulary — **machine / materials / scheduling / attendance / other**, with NPT sub-buckets — over the existing free-form `root_cause_category` on `DowntimeEntry`; entry UI becomes a select; migration maps confidently-matchable free-form values, everything else defaults to `uncategorized`. **[DONE — this PR]**
2. **Cycle 2 — Justified-delay flag** (Q3): justified/unjustified classification plus reason on late work orders; delivery performance becomes reportable both gross and net-of-justified (the concept behind PGI's exclusion, never its layout).
3. **Cycle 3 — Labor-hours accounting** (Q1; the big capture): OT tiers (Normal/Double/Triple — Mexican labor law, structural), direct/indirect classification on `Employee`, billed vs available-for-efficiency hours. Expected 2 PRs — capture model + entry UI, then derived Q1 metrics; the split is decided in that cycle's spec.
4. **Cycle 4 — Pivot/summarization layer** (largest; built once, over the enriched data): pre-defined time buckets (week/month/quarter/year), pre-defined groupings/categorizations, cross-metric comparison on the common hours basis (units ↔ SAM-earned hours ↔ operators ↔ attendance hours), every summary downloadable as its underlying data. Expected 2–3 PRs; split decided in that cycle's spec.

**Capture policy (uniform across all cycles):** new capture fields ship optional or defaulted (e.g. `uncategorized`) and never block existing entry flows at introduction; each capture surface gets a completeness indicator; flip-to-required happens per field once completeness ≥ 90 % over a trailing 30 days AND management confirms the shop-floor workflow has adapted (the flip is its own small change); the demo seeder is updated in the same cycle that introduces a field.

### Deferred remainder

Parked until management asks or an active-lane cycle surfaces a hard dependency:

- **Report subscriptions** — persisted email config (DB table replacing the in-memory `_email_configs`), `include_*` toggles actually consumed by the generators, scheduler honoring the configured frequency (daily/weekly/monthly) and recipients.
- **Model extensions** *(capture-first)* — shipment #, material-batch traceability, cut-quantity capture, plant/module hierarchy, operator-level production. Same standing rule: capture first, report after.
