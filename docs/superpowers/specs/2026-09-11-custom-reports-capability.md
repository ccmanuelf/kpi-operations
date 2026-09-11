# Custom Reports — Capability Proposal

**Date:** 2026-09-11
**Status:** DECIDED 2026-09-11 (D1-D6 below) — ready for an implementation plan
**Scope note:** This proposes a reporting capability derived from the structure the product
actually has. It is explicitly **not** an attempt to reproduce the legacy Excel workbook,
which no longer describes what this system does. It also assumes **no email delivery** —
that remains deferred by decision, and nothing proposed here depends on it.

---

## 1. The finding that shapes everything else

The product already contains a **composable, tenancy-correct query engine** and a
**fixed-template document renderer**, and they are two separate stacks with no connection
between them.

| | Query engine (`/api/pivot`) | Document renderer (`/api/reports/*`) |
|---|---|---|
| Dimensions | 15 group-bys across 6 datasets, caller's choice | hardcoded per section |
| Time | 4 buckets (week/month/quarter/year) | a single start/end range, no bucketing |
| Measures | 40, declared in a registry | hardcoded per section |
| Tenancy | `resolve_client_scope` dependency | `client_id` passed by hand to each query |
| Output | JSON, CSV | PDF, Excel |
| Correctness | ratio-of-sums structural, hook datasets delegate to the canonical calculation services | recomputes its own aggregates inline |

Every document endpoint takes exactly `(client_id, start_date, end_date)` and nothing else
(`routes/reports/comprehensive_reports.py:31`, `:88`; `kpi_reports.py:35`, `:91`, `:142`,
`:196`; `production_reports.py:39`, `:97`). The report the caller gets is whatever those
eight functions were written to emit.

**Connecting those two stacks is the whole capability.** A "custom report" is a pivot query
plus a column selection plus a renderer — and two of those three already exist.

---

## 2. What exists, verified

### 2.1 The query engine — `backend/pivot/`

Declarative registry (`pivot/registry.py`), 6 datasets:

| dataset | path | group-bys | measures |
|---|---|---|---|
| `production` | SQL | client, line, product | units, earned_hours, excluded_entries, run_hours, downtime_hours, operators, efficiency_pct |
| `downtime` | SQL | client, category, reason, line | downtime_hours, events, share_of_window_pct |
| `quality` | SQL | client, style | inspected, passed, defective, defects, fpy_pct |
| `holds` | hook | client, reason_category, reason | holds, hold_days, avg_days_per_hold |
| `labor` | hook | client, labor_class | scheduled, actual, normal, double, triple, unsplit_actual, billed, available_for_efficiency, earned_hours, excluded_entries, efficiency_available_basis |
| `delivery` | hook | client, style, delay_reason | delivered, on_time, justified_late, net_on_time, otd_gross_pct, otd_net_pct |

40 measures, 15 group-by dimensions, 4 time buckets. Ratios are computed from sums by the
engine, not averaged from row ratios — that is structural and guarded
(`test_registry_guard.py`). Hook datasets mirror the canonical services verbatim
(`fetch_delivery` ↔ `calculations/otd.py::calculate_true_otd`, guarded by
`test_hooks_golden.py`), so a pivot number and a dashboard number cannot drift.

Two endpoints: `GET /api/pivot/{dataset}` (JSON) and `GET /api/pivot/{dataset}/csv`.
Both scope through `resolve_client_scope` and validate dataset / bucket / group_by against
the registry with 422s.

### 2.2 The definition store — `SAVED_FILTER`

`orm/saved_filter.py`: user-scoped (`user_id` FK, "not shared between users"), a free-form
JSON `filter_config`, a `filter_type` discriminator, `is_default` per type, usage counters,
plus a `FILTER_HISTORY` companion. `routes/filters.py` exposes **14 endpoints** — CRUD,
apply, set/unset default, duplicate, statistics, recent history. It is live in the UI
(`services/api/preferences.ts`, `components/filters/FilterManager.vue` on the KPI
dashboard).

`FilterType` already includes `CUSTOM = "custom"` (`schemas/filters.py:30`).

**A custom report definition can be stored today with no migration and no new table.**

### 2.3 The presentation surface — the Summaries screen

`views/PivotSummaries.vue` → `components/PivotViewPanel.vue` (74 lines) driven by
`composables/pivotPresets.ts`: 5 preset views (Q1 hours-basis, Q2 downtime, Q3
quality+delivery, Q4 downtime-by-line, Q5 holds/WIP), each with a bucket picker, a grouping
picker, an AG Grid, and a CSV download button. The presets are careful — they hide columns
that are structurally meaningless under a given grouping (a per-delay-reason OTD%, quality
measures under a delivery-side grouping).

What the user **cannot** do: choose measures, combine datasets beyond the two pairs the
presets hardcode, or save their own view.

### 2.4 The document renderers

`reports/pdf_generator.py` (ReportLab) and `reports/excel_generator.py` (openpyxl), reached
through 8 endpoints in 4 flavours × 2 formats. Real PDF/Excel output with headers, styled
tables, and an executive summary.

---

## 3. What is inert or wrong, verified

Each of these was confirmed by running the code, not by reading it.

### 3.1 Four of ten PDF sections print a falsehood

`generate_report` declares ten KPI sections (`pdf_generator.py:135-146`). Probed with
production, quality and attendance rows all present for the period:

```
RENDERS REAL DETAIL (6/10): efficiency, availability, performance, fpy, ppm, absenteeism
PRINTS 'No data available' (4/10): oee, rty, dpmo, otd
```

`oee`, `rty`, `dpmo` and `otd` fall through to
`"No data available for this period" / "Please ensure data has been entered for the selected
date range"` (`pdf_generator.py:568-573`) — a statement that is false, and that blames the
reader for a gap in the generator. All four have working calculation services:
`services/calculations/oee.py`, `calculations/fpy_rty.py`, `calculations/dpmo.py`,
`calculations/otd.py`. The dashboard already renders all four.

### 3.2 Every target is a literal, and most contradict the configured ones

`CLIENT_CONFIG` stores seven per-client targets (`orm/client_config.py:48-65`).
`KPI_THRESHOLD` is a second, per-metric threshold table. **Neither generator reads either
one** — grep for `ClientConfig`/`KPIThreshold` across `backend/reports/` returns nothing.

**Of the two stores, `KPI_THRESHOLD` is the live one and the one to read** (settled as part
of D1/D2). `CLIENT_CONFIG`'s seven target columns are read by nothing but their own CRUD
schemas — stored, echoed back, never judged against. `KPI_THRESHOLD` is consumed by
`routes/alerts/generate.py` and `events/handlers/notification_handlers.py`, is keyed
per-metric with `client_id` nullable so global-default inheritance is built in, and carries
`warning_threshold`, `critical_threshold` and `higher_is_better` — which is exactly the
three-state status and the direction the generator currently fakes with a hardcoded
`threshold = 0.95` heuristic (`pdf_generator.py:577`).

**And the admin is already setting targets the reports discard.** The one section of
`views/admin/AdminSettings.vue` that really persists is the KPI threshold editor, and it
writes `KPI_THRESHOLD` for ten keys including `oee`, `otd`, `availability` and `performance`.
So an admin sets a per-client OEE target today, it saves, alerts honour it — and the report
prints a literal.

The executive summary's five rows, as actually emitted, against the stored defaults:

| KPI | report literal | `CLIENT_CONFIG` default | agrees? |
|---|---|---|---|
| Efficiency | 85 | 85.0 | yes |
| Performance | 85 | 95.0 | **no** |
| First Pass Yield | 99 | 95.0 | **no** |
| PPM | 1000 | 10000.0 | **no** |
| Absenteeism | 5 | 3.0 | **no** |

So the "On Target / At Risk" column — and the red/amber/green status colour — judges every
client against numbers they never set, four times out of five in the wrong direction.

### 3.3 "Trend" is a threshold restatement

PDF: `"Trend": "Improving" if avg_value >= 85 else "Declining"` (`pdf_generator.py:498`) —
one period's value against a literal, which is a level, not a trend. Excel: an arrow column
at `F7` filled from `"trend"` keys that are either the same comparison
(`"↑" if avg_efficiency >= 85 else "↓"`) or a hardcoded `"→"` (six of them), and for PPM the
arrow **rises as the metric worsens** (`"↑" if ppm > 1000 else "↓"`, line 589), so the glyph
cannot be read consistently down the column.

`calculations/trend_analysis.py` already provides `analyze_trend`, `linear_regression`,
`calculate_trend_direction` and `determine_trend_direction`. None is used by either
generator.

### 3.4 Email config is process-local (and stays out of scope)

`routes/reports/email_config.py:26` — `_email_configs: dict = {}`, with the comment "in
production, use database table". Five endpoints read and write that dict; it is lost on
restart, not shared across workers, and the scheduler does not consult it.
`AdminSettings.vue:465` "saves" notification settings with a `setTimeout` and no API call.

**Recorded, not proposed.** Email delivery is deferred by decision. The honest move is to
stop *presenting* a setting that does nothing — see §6, decision D4.

---

## 4. The proposal

Make the document renderers **consumers of the pivot engine**, and let a saved definition
describe what to render.

```
  SAVED_FILTER(filter_type="custom")            ← definition, already storable
        │  { dataset, bucket, group_by, measures[], window, client scope }
        ▼
  pivot engine  (registry-validated, tenancy-scoped, canonical maths)
        │  rows + totals
        ├─► JSON      → AG Grid on the Summaries screen   (exists)
        ├─► CSV       → download                           (exists)
        └─► XLSX      → one new renderer                   (new)
```

A report definition is exactly the pivot query the engine already accepts, plus a column
selection and a display name. Nothing new needs inventing: the registry is the allow-list,
`resolve_client_scope` is the tenancy, the calculation services are the maths.

### Phase 1 — make the shipped reports honest *(no new capability)*

Independently shippable, and worth doing whatever is decided about the rest.

1. Read targets from `CLIENT_CONFIG` (falling back to the column defaults), so the status
   column means something. Pin it with a test asserting a client's configured target reaches
   the rendered cell.
2. Implement the four dead sections from their existing services, or drop them from
   `all_kpis`. Either way, stop printing "No data available" when data is present.
3. Replace "Trend" with `analyze_trend` over the bucketed series, or remove the column.
   A column that restates a threshold is worse than no column.

### Phase 2 — the render bridge

One renderer, `pivot result → XLSX`, behind one endpoint
(`GET /api/pivot/{dataset}/xlsx`, alongside the existing `/csv`). Same query params, same
scope dependency, same validation — the only new code is the workbook writer, and
`excel_generator.py` already has the styling conventions to reuse.

### Phase 3 — the builder

The Summaries screen gains: a measure picker (from the registry, per dataset), save / load /
delete of definitions through the 14 `SAVED_FILTER` endpoints that already exist, and a
"download as Excel" button beside the CSV one. The 5 presets stay as starting points.

This **retires the parallel stack** rather than growing it: new reporting capability lands in
the engine that already has the tenancy and the maths, and the fixed documents get fixed
rather than extended.

---

## 5. What this deliberately does not do

- **No PDF for custom reports.** An arbitrary N-column, M-row pivot paginates badly in
  ReportLab, and the result would be a worse CSV. PDF stays where it earns its keep: the
  fixed narrative reports. (Decision D3.)
- **No scheduling, no email.** Out of scope by standing decision.
- **No new definition table.** `SAVED_FILTER` + `filter_type="custom"` already fits.
- **No query language.** The registry stays the allow-list. A caller cannot express a
  measure or a dimension the engine hasn't declared, which is what keeps tenancy and
  ratio-of-sums structural rather than advisory.
- **Multi-dataset is a key-aligned union, not a join.** `usePivotView.ts:26`
  (`mergePivotRows`) unions rows on `(bucket_start, group_key)`, last-write-wins. An earlier
  draft of this document called free combination a "join planner"; that was too strong. What
  it actually needs is a group-by intersection rule and a measure-name collision rule — see
  D5/D6.
- **No new datasets.** Six is what the engine serves today. Adding a seventh is its own
  piece of work with its own golden-master guard.

---

## 6. Decisions — SETTLED 2026-09-11

| # | Decision | Answer |
|---|---|---|
| D1 | the four dead sections | **implement all four** (`oee`, `rty`, `dpmo`, `otd`) + add the missing `availability` summary row → 10/10 sections render, docstring becomes true |
| D2 | sequencing | **two PRs**: PR-A the judgement columns, PR-B the missing sections |
| D2b | the Trend column | **remove it in PR-A**; earn it back in Phase 2 from the bucketed series the renderer already receives |
| D3 | custom-report formats | **add XLSX, keep CSV, no PDF** |
| D4 | the inert admin UI | **remove all three fake sections** + Export button + the 5 email-config endpoints + the French locale option |
| D5 | definition scope | **free combination**, with a group-by intersection rule and measure-name namespacing |
| D6 | where the merge lives | **server-side**; `mergePivotRows` and the per-dataset fetch loop are deleted |

### PR sequence

**PR-A — the judgement columns. SHIPPED as `c979253`.** Targets read from `KPI_THRESHOLD`
(per-metric, with the `client_id IS NULL` global row as the fallback), and `warning_threshold` /
`critical_threshold` / `higher_is_better` replace the hardcoded `threshold = 0.95` heuristic and
the per-row `higher_better` literals. The Trend column is removed from both generators.

Scoping widened it in four ways, each fixed in the same PR:

* **The detail blocks had literals too**, and one block serves efficiency, performance AND
  availability off a single `"85%"` — so two of the three showed a target that was not theirs.
* **`_get_status_color` was dead.** Its one caller discarded the return value, so the PDF never
  coloured a status cell by the 0.95 band it implemented.
* **Removing the Trend data would not have removed the column.** Four places kept drawing
  Excel's column F: the alternating-row fill, `_apply_table_borders`, a reserved width, and a
  title banner merged across `A1:F1`. And Excel reads a blank Target cell as 0, so the variance
  formula rendered the measured value as its own variance — blanked with the target.
* **The configuration did not exist in the repository.** Nothing in `backend/seed/`, no
  migration, no bootstrap ever wrote a global row: Render had 0, the VM had 10 made by hand.
  Migration `0009_global_kpi_targets` supplies them, values copied from the VM so the two
  environments converge, insert-if-absent so no configured value is overwritten.

**The status scale** composes two questions, because neither answers the column alone: "meets
target?" (direction-aware) and "how bad is the miss?" (`calculations/alerts.py::
check_threshold_breach`, reused so a report and an alert cannot disagree about one number). With
no bands configured `check_threshold_breach` returns None above half of target, so asked alone it
would call 50% against an 85% target "no breach". Result: No Target / On Target / At Risk /
Warning / Critical / Urgent.

**One MariaDB-only defect, caught by running the migration against a throwaway MariaDB 11.4
rather than trusting that the SQL looked portable.** `alembic_version.version_num` is
`VARCHAR(32)`; the first revision id was 34 characters. SQLite does not enforce declared string
lengths, so it upgraded cleanly there — through nine migration tests that each ran a real
`alembic upgrade` — and failed on MariaDB at the migration's last statement, after the DDL had
implicitly committed. `0008` is 31 characters, so the cliff was one character away with nothing
watching it. `test_revision_ids_fit_the_version_column.py` now guards every migration.

**PR-B — the missing sections.** `oee`, `rty`, `dpmo` and `otd` detail sections wired to
`services/calculations/oee.py`, `calculations/fpy_rty.py`, `calculations/dpmo.py` and
`calculations/otd.py`; plus the `availability` executive-summary row that is currently absent
while its detail section renders. Gates: one per section asserting real seeded data reaches
the rendered cell, and a structural test asserting every key in `all_kpis` renders a detail
block — so a future section cannot be declared without being implemented.

**PR-C — the inert admin surface.** Remove the General, Notification and Data Retention
sections from `views/admin/AdminSettings.vue` with their three `setTimeout` save handlers and
the `exportData` no-op, the five `/api/reports/email-config` endpoints behind the process-local
`_email_configs` dict, and the `fr` option from the locale list. The KPI threshold editor stays
— it is real, and PR-A makes it matter. Needs an OpenAPI golden-master regen for the removed
routes.

**PR-D — the multi-dataset engine path (D5 + D6).** `run_pivot_multi(datasets, bucket,
group_by, …)`: reject a `group_by` outside the intersection of the chosen datasets'
`group_bys` with a 422 naming the intersection, union per-dataset rows on
`(bucket_start, group_key)`, and namespace a measure present in more than one dataset as
`<dataset>.<measure>`. `GET /api/pivot` accepts `datasets=a,b`. `mergePivotRows` and the
per-dataset fetch loop in `usePivotView.ts` are deleted, so Q1 and Q3 become one request.
Gates: the intersection rejection; a collision namespaced rather than overwritten (the hazard
`usePivotView.ts:13-25` documents); Q1 and Q3 byte-identical to their current client-merged
output. Needs live re-verification of all five presets.

**PR-E — the XLSX renderer (Phase 2).** `GET /api/pivot/xlsx`, same params and same
`resolve_client_scope` dependency as the JSON path. Header block naming client, period, bucket
and grouping; percent / number / count formats driven by the measure kind the presets already
declare; styled totals row. Trend returns here, computed by `analyze_trend` over the bucketed
series.

**PR-F — the builder (Phase 3).** The Summaries screen gains a measure picker from the
registry, a dataset multi-select, and save / load / delete of definitions through the existing
`SAVED_FILTER` endpoints with `filter_type="custom"`, plus a download-as-Excel button.
