# Reporting Capability Doc + Gap Decisions — Design

**Date:** 2026-07-29
**Status:** Approved design (brainstorm complete)
**Deliverable:** Management deliverable #2 — a reporting capability document plus a reasoned make-real vs document-and-defer decision for every known reporting gap, grounded in the client's real Excel reports and industry-standard apparel-manufacturing practice.

## 1. Purpose and explicit non-goals

Produce two things:

1. **A capability document** — `docs/reporting/reporting-capabilities-and-gaps.md` — cataloguing every working report/export, recording a decision per known gap, and establishing a living **concept register** that absorbs future client report samples.
2. **One "honest surface" PR** — small code changes that remove demo-embarrassing lies from the existing report generators. Everything larger is decided-and-deferred into named future specs.

Two positions are committed to in writing:

- **No carbon-copying of client Excel reports.** Every client's workbook differs in content, format, tags, colors, and headers (confirmed across two samples from two different clients). The app observes the *concepts* behind the reports, never the layouts. Management explicitly requested this.
- **Data-first, not chart-first.** Reports summarize data; every on-screen summary must be downloadable as underlying data. Charts are optional garnish, never the deliverable. Configurable plotting/charting mechanisms are explicitly not the goal.
- **No reports without underlying data.** A report may only be built over metrics kpi-operations actually tracks. Concepts graded **missing** in the register (e.g., shipments, stock, billed hours, cut quantities) are *capture-first*: adding the data capture is its own deliberate product decision, never a side effect of a reporting spec. Concepts derivable from data already tracked (**have**/**partial**) are welcome report additions.

## 2. Evidence base

### Sample 1 — `PGI - Production Report 2026.xlsx` (client: PGI)

- **Weekly production sheets (WK10–WK21)**: daily header block (operators, daily hours, total hours, units produced, efficiency % per day, holidays shaded) over a shop-order-granularity detail table (Shop Order #, Style, Size, PGI Order #, SAM in minutes, description, per-weekday quantity, weekly total). Efficiency = SAM-earned minutes ÷ (operators × hours × 60).
- **Shop Orders – Status ledger** (~1,577 rows): PGI Order #, Shop #, OB (material batch), Style, Size, Qty, Due Date, Status (Shipped/Cancelled), Shipment #, Ship Date, Delivery Status (**On Time / Justified delay**), free-text justification comments.
- **Delivery Performance scorecard**: totals for shop orders/garments exported, on-time count, late count, late-but-justified count → Delivery Performance % (justified delays do not count against the score).

### Sample 2 — `Sample_attendance_check.xlsx` (client: Franklin Products)

- Weekly per-employee attendance grouped by assembly line, with Plant → Module/Cell → Line hierarchy (Plant B, Module ASSY CELL 1,4,5), supervisor, shift.
- Per-day Normal + OT hour columns; absence codes (U, V); partial-day hours; per-employee hour totals split **Normal / Double / Triple** (Mexican labor-law OT tiers).
- **Direct vs indirect** labor classification per employee.
- Bottom blocks: **Billed Hours** (direct/indirect per day, weekly total with dollar amount) vs **Available Hours for Efficiency** (a smaller figure — the true efficiency denominator), plus Shifts Absent / Hours Absent.

### Industry-standard cross-check (web recon, 2026-07-29)

Standard apparel-manufacturing reports/metrics beyond the samples: **cut-to-ship ratio** and order-to-ship ratio, **DHU** (Defects per Hundred Units — the internal metric that feeds AQL, the buyer threshold), **operator-level daily efficiency reported weekly**, average style changeover time, NPT (non-productive time) categorization, man-to-machine ratio, line balancing/bottleneck reports, WIP reports. Efficiency benchmark tiers for context: 40–55% regional average, 65–75% well-managed, 80%+ world-class.

Sources: [Online Clothing Study — KPIs for garment manufacturers](https://www.onlineclothingstudy.com/2012/05/kpis-for-garment-manufacturers.html), [Scan ERP — 15 garment factory KPIs](https://scanerp.pro/blog/garment-factory-kpi-metrics-production-manager.html), [ORDNUR — KPI factors of garments](https://ordnur.com/industrial-engineering-ie/kpi-factors-of-garments/), [ORDNUR — WIP in garments manufacturing](https://ordnur.com/apparel/what-is-wip-wip-calculation-reducing-reporting-in-garments-manufacturing/), [Apparel Resources — quality measurement tools](https://apparelresources.com/business-news/manufacturing/improve-quality-levels-using-measurement-tools/), [Textile Industry — IE in apparel](https://www.textileindustry.net/industrial-engineering-ie-in-the-apparel/).

### Tenant mapping

Each customer (PGI, Franklin Products, …) maps 1:1 to a row in the app's `CLIENT` table; these reports are per-client (`client_id`-scoped) artifacts.

## 3. Organizing frame — five management questions

The concept register is organized under the five questions management wants the data to answer. Each concept carries a readiness grade: **have / partial / missing** (assessed against ORM + endpoints at `main` @ `322c727`).

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
| Cause taxonomy | **partial** | `root_cause_category` exists but free-form; no controlled vocabulary matching the five management categories |
| NPT categorization | **partial** | same field; industry NPT buckets would ride on the same taxonomy |

### Q3 — Are we producing to the expected quality bar?

| Concept | Readiness | Notes |
|---|---|---|
| Units subject to rework | **have**/**partial** | `rework_count` per entry (have); "as a function of the entire order" needs per-work-order rollup (partial) |
| Units started to meet order requirement (**cut-to-ship ratio**) | **missing** | model records output units, not started/issued units |
| Shipping late (OTD) | **have** | `planned_ship_date` vs `actual_delivery_date`; OTD KPI live |
| Justified vs unjustified lateness | **missing** | no classification field; PGI's Delivery Performance excludes justified delays |
| Skipping priorities | **partial** | `priority` + `DEMOTED` state exist; no priority-adherence metric |
| DHU (Defects per Hundred Units) | **partial** | `defect_count` stored; DHU computable but not reported |
| Estimated AQL from actuals | **missing** | not modeled; DHU is its computable precursor |

### Q4 — Is re-shuffling causing holes in production or downtime?

**Partial** — `DEMOTED` transitions are first-class in the workflow engine, so churn is countable; the missing piece is the *correlation*: demotions/re-sequencing linked to idle gaps and scheduling-category downtime. A metric definition for the pivot layer, not a data-model hole. Style changeover time is adjacent (**partial** — `setup_time_hours` exists, no changeover report).

### Q5 — Are we keeping material on hold? What constraint, where, why?

**Have** (strongest area) — `HoldEntry` with catalog-backed `hold_reason` (`HOLD_REASON_CATALOG`), `hold_reason_category`, description; WIP-aging endpoints live (stalled / old / past-due triad shipped with the diagnostic-charts work). Open point: whether holds carry line/area attribution for the "where".

### Reportable today vs capture-first

Per the "no reports without underlying data" position, the register splits two ways:

- **Reportable today** (data already tracked — welcome additions): DHU (from `defect_count`), rework as % of order (per-work-order rollup of `rework_count`), OTD, WIP triad (stalled/old/past-due), hold-reason/category breakdowns, demotion-churn counts and priority adherence (from `DEMOTED` transitions + `priority`), downtime by reason, per-type report sheets, real availability, earned-hours efficiency from `ideal_cycle_time` × units vs `run_time_hours`.
- **Capture-first** (no underlying data — requires a product decision to start tracking before any report exists): shipments (shipment #), stock/inventory, billed hours and rates, OT tiers, direct/indirect classification, cut/started quantities, material-batch traceability, justified-delay classification, operator-level production, plant/module hierarchy.

### Structural observations (cross-question)

- **Plant → Module/Cell → Line hierarchy**: the app models lines only; nothing above. Open modeling question.
- **Missing commercial/traceability fields** (from PGI ledger): shipment #, material-batch (OB) references, customer-PO reference, garment size as a first-class field.
- Absence codes (U/V/…) map onto the existing `AbsenceType` enum — **have**.

## 4. The capability document

`docs/reporting/reporting-capabilities-and-gaps.md`, management-readable, four sections:

1. **Catalog of what works today** — every report/export endpoint, how to run it, what it contains, formats, and required role: 4 PDF reports (type-aware via `kpis_to_include`), 4 Excel reports, `GET /api/reports/available`, email-config CRUD + `/test` + `POST /send-manual`, admin `GET /api/assumptions/variance` (JSON), and the 9 CSV entity exports under `GET /api/export/**` (the data-first backbone).
2. **Gap register with decisions** — the table in §6.
3. **Concept register** — §3 content, marked **living**: each future client sample is analyzed and slotted under one of the five questions with readiness updates. Endpoint references validated against `openapi_surface.json`.
4. **Deferred-spec queue** — ordered future work, each requiring its own brainstorm→spec cycle before any build:
   1. **Pivot/summarization layer** — pre-defined time buckets (week/month/quarter/year), pre-defined groupings/categorizations/pivots, cross-metric comparison on the common hours basis (units ↔ SAM-earned hours ↔ operators ↔ attendance hours), everything downloadable as data. Blocked on: remaining client samples + concept-register completion.
   2. **Report subscriptions** — persisted email config (DB table replacing in-memory `_email_configs`), `include_*` toggles actually consumed by generators, scheduler honoring frequency (daily/weekly/monthly) and recipients.
   3. **Downtime cause taxonomy** — controlled vocabulary (machine/materials/scheduling/attendance/other + NPT buckets) over the existing `root_cause_category` field.
   4. **Labor-hours accounting** *(capture-first)* — OT tiers (Normal/Double/Triple), direct/indirect classification, billed vs available-for-efficiency hours. Prerequisite for full Q1 coverage; requires new data capture, so it is a product decision before it is a reporting feature.
   5. **Model extensions** *(capture-first)* justified by future samples (justified-delay flag, shipment #, batch traceability, cut-quantity capture, plant/module hierarchy, operator-level production). Same rule: capture first, report after.

## 5. Honest-surface PR (one PR)

1. **Excel honors report type.** `ExcelReportGenerator.generate_report()` (backend/reports/excel_generator.py) gains a sheet-selection parameter mirroring the PDF generator's existing `kpis_to_include` pattern; the four Excel endpoints (comprehensive/production/quality/attendance) each pass their own sheet set. Comprehensive = all sheets (output unchanged). No route/URL changes.
2. **Real availability.** Replace placeholders — `85.0` (backend/reports/pdf_generator.py:462) and `90.0` (backend/reports/excel_generator.py:600) — with availability computed from run/downtime hours, **reusing the canonical formula in `backend/calculations`** so reports always agree with the dashboard.
3. **Remove the "Trend Charts" placeholder sheet** (excel_generator.py `_create_charts_sheet`) — data-first decision; no charts built.
4. **Email `include_*` toggles surfaced honestly** — hidden in the UI or labeled "not yet active", whichever is the smallest true change; decision recorded in the doc.

## 6. Decision register

| Gap | Decision |
|---|---|
| Excel ignores report type (identical 6-sheet workbook for all 4 types) | **Make real now** — PR item 1 |
| Placeholder availability values (85.0 / 90.0) | **Make real now** — PR item 2 |
| Placeholder "Trend Charts" sheet | **Remove now** — PR item 3 (charts are explicitly not the product) |
| Email content toggles never consumed | **Defer** to report-subscriptions spec; hide/mark now (PR item 4) |
| Email config in-memory only | **Defer** — same spec |
| Scheduler daily-only, ignores frequency/recipients | **Defer** — same spec |
| Pivot/summarization layer | **Future spec #1** — blocked on remaining samples + concept register |
| Downtime cause taxonomy | **Future spec** — small, high leverage for Q2 |
| Labor-hours accounting (OT tiers, direct/indirect, billed vs available) | **Future spec** — prerequisite for full Q1 |
| Workbook replication | **Rejected permanently** — concepts, not layouts |

## 7. Verification

- **Per-type Excel:** characterization test asserting the four endpoints produce distinct sheet sets and comprehensive retains all sheets.
- **Availability:** unit test that the report value equals the canonical `backend/calculations` result for a fixture with known downtime; a guard asserting no literal `85.0`/`90.0` placeholder remains in the generators.
- **Existing gates stay green:** OpenAPI route/tag golden master (no route changes), coverage ≥75%, all 4 required CI checks.
- **Doc accuracy:** every endpoint cited in the capability doc checked against `openapi_surface.json`.
- **Live verify:** after deploy, download a per-type Excel report from the VM (MariaDB) and confirm type-specific sheets + real availability figures.

## 8. Delivery pipeline

Spec (this document) → implementation plan (`superpowers:writing-plans`) → subagent-driven execution with per-task reviews → `/cross-review` → PR → 4-check CI green → user-confirmed merge → deploy Render + VM → live verification per §7.
