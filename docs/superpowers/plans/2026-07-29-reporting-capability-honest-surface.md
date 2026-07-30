# Reporting Capability Doc + Honest-Surface PR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the reporting capability document plus the "honest surface" fixes: type-aware Excel reports, real availability values, no placeholder Charts sheet, no cosmetic email toggles.

**Architecture:** One pure availability formula in `backend/calculations/availability.py` reused by both report generators; a sheet-selection parameter on `ExcelReportGenerator.generate_report()` mirroring the PDF generator's existing `kpis_to_include` pattern; a template-only edit removing the dead checkboxes from `EmailReportsDialog.vue`; a new management-readable doc at `docs/reporting/reporting-capabilities-and-gaps.md` derived from the approved spec.

**Tech Stack:** FastAPI + SQLAlchemy 2 (backend), openpyxl (Excel), reportlab (PDF), Vue 3 `<script setup>` + Vuetify 4 (frontend), pytest / vitest.

**Spec:** `docs/superpowers/specs/2026-07-29-reporting-capability-and-gap-decision-design.md` — read it before starting any task; the capability doc (Task 7) is derived from its §2, §3, §4, §6.

## Global Constraints

- Branch: `feat/reporting-capability-honest-surface` (already exists, spec committed on it).
- **No route/URL/OpenAPI changes.** The golden-master gate `backend/tests/test_bootstrap/` (openapi_surface.json) must pass untouched.
- Backend verify: `pytest tests/` from `backend/` — coverage gate ≥75%. Frontend verify: `npm run test`, `npm run lint` from `frontend/`.
- No permissive assertions (`status_code in [...]`) — one expected code per assertion.
- Each test asserts exact expected values; no `assert x > 0`-style hedging where the fixture value is known.
- Commit after every task with the message given in the task. All commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Do not touch: email persistence, scheduler, report subscriptions — explicitly deferred by the spec.

---

### Task 1: Pure availability helper

**Files:**
- Modify: `backend/calculations/availability.py` (append function)
- Test: `backend/tests/test_calculations/test_availability_pure.py` (create)

**Interfaces:**
- Produces: `calculate_availability_pure(scheduled_hours: Decimal, downtime_hours: Decimal) -> Decimal` — the formula Tasks 2 and 3 import. Availability % = (scheduled − downtime) ÷ scheduled × 100, clamped to [0, 100]; returns `Decimal("0")` when scheduled ≤ 0.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_calculations/test_availability_pure.py`:

```python
"""Unit tests for the pure availability formula (honest-surface PR)."""

from decimal import Decimal

from backend.calculations.availability import calculate_availability_pure


class TestCalculateAvailabilityPure:
    def test_normal_case(self):
        # 8h scheduled, 1h downtime -> 87.5%
        result = calculate_availability_pure(Decimal("8"), Decimal("1"))
        assert result == Decimal("87.5")

    def test_zero_downtime_is_100(self):
        assert calculate_availability_pure(Decimal("9.5"), Decimal("0")) == Decimal("100")

    def test_zero_scheduled_is_0(self):
        assert calculate_availability_pure(Decimal("0"), Decimal("0")) == Decimal("0")

    def test_negative_scheduled_is_0(self):
        assert calculate_availability_pure(Decimal("-1"), Decimal("0")) == Decimal("0")

    def test_downtime_exceeding_scheduled_clamps_to_0(self):
        assert calculate_availability_pure(Decimal("4"), Decimal("5")) == Decimal("0")

    def test_matches_canonical_formula(self):
        # Same math as calculate_availability(): (scheduled - downtime) / scheduled * 100
        scheduled, downtime = Decimal("8.0"), Decimal("2.5")
        expected = (scheduled - downtime) / scheduled * 100
        assert calculate_availability_pure(scheduled, downtime) == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_calculations/test_availability_pure.py -v`
Expected: FAIL — `ImportError: cannot import name 'calculate_availability_pure'`

- [ ] **Step 3: Implement**

Append to `backend/calculations/availability.py`:

```python
def calculate_availability_pure(scheduled_hours: Decimal, downtime_hours: Decimal) -> Decimal:
    """
    Pure availability formula: (scheduled - downtime) / scheduled * 100.

    Same math as calculate_availability() above, decoupled from the DB so the
    report generators can reuse it. Clamped to [0, 100]; 0 when nothing scheduled.
    """
    if scheduled_hours <= 0:
        return Decimal("0")
    availability_pct = ((scheduled_hours - downtime_hours) / scheduled_hours) * 100
    return min(max(availability_pct, Decimal("0")), Decimal("100"))
```

(`Decimal` is already imported in this module.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_calculations/test_availability_pure.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/calculations/availability.py backend/tests/test_calculations/test_availability_pure.py
git commit -m "feat(calculations): pure availability formula for report generators"
```

---

### Task 2: Real availability in the Excel generator

**Files:**
- Modify: `backend/reports/excel_generator.py` — `_fetch_production_data` (lines ~564–604: add run/downtime sums to the grouped query; replace the `90.0` literal)
- Test: `backend/tests/test_calculations/test_report_availability.py` (create)

**Interfaces:**
- Consumes: `calculate_availability_pure` from Task 1.
- Produces: `_fetch_production_data` rows whose `"availability"` key is computed as run ÷ (run + downtime) × 100. Scheduled time = `run_time_hours + downtime_hours` (the line was scheduled for both).

- [ ] **Step 1: Write the failing guard test**

Create `backend/tests/test_calculations/test_report_availability.py`:

```python
"""Guards that the report generators use real availability, not placeholders."""

from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"


class TestNoPlaceholderAvailability:
    def test_excel_generator_has_no_hardcoded_availability(self):
        src = (REPORTS_DIR / "excel_generator.py").read_text()
        assert '"availability": 90.0' not in src
        assert "calculate_availability_pure" in src

    def test_pdf_generator_has_no_hardcoded_availability(self):
        src = (REPORTS_DIR / "pdf_generator.py").read_text()
        assert "[85.0] * len" not in src
        assert "calculate_availability_pure" in src
```

- [ ] **Step 2: Run to verify the Excel half fails**

Run: `cd backend && pytest tests/test_calculations/test_report_availability.py::TestNoPlaceholderAvailability::test_excel_generator_has_no_hardcoded_availability -v`
Expected: FAIL (the `90.0` literal is present, the helper is not imported)

- [ ] **Step 3: Implement**

In `backend/reports/excel_generator.py`:

a. Add imports at the top of the module (with the other imports):

```python
from decimal import Decimal

from backend.calculations.availability import calculate_availability_pure
```

b. In `_fetch_production_data`, extend the grouped query's select list (after the `performance` line):

```python
                func.sum(ProductionEntry.run_time_hours).label("run_hours"),
                func.sum(ProductionEntry.downtime_hours).label("downtime_hours"),
```

c. Replace the placeholder in the returned dict comprehension. Old:

```python
                "availability": 90.0,  # Placeholder - calculate from downtime
```

New (compute above the dict if a comprehension gets awkward — a plain loop building the list is fine):

```python
                "availability": float(
                    calculate_availability_pure(
                        Decimal(str((r.run_hours or 0))) + Decimal(str(r.downtime_hours or 0)),
                        Decimal(str(r.downtime_hours or 0)),
                    )
                ),
```

- [ ] **Step 4: Run the guard + existing Excel route tests**

Run: `cd backend && pytest tests/test_calculations/test_report_availability.py::TestNoPlaceholderAvailability::test_excel_generator_has_no_hardcoded_availability tests/test_api/test_reports.py -v`
Expected: the excel guard PASSES; the pdf guard still FAILS (that's Task 3); all existing report route tests PASS.
(If running the whole file, use `-k excel` to scope to the Excel guard.)

- [ ] **Step 5: Commit**

```bash
git add backend/reports/excel_generator.py backend/tests/test_calculations/test_report_availability.py
git commit -m "fix(reports): Excel availability computed from downtime, not 90.0 placeholder"
```

---

### Task 3: Real availability in the PDF generator

**Files:**
- Modify: `backend/reports/pdf_generator.py` — `_fetch_kpi_details` (line ~462)

**Interfaces:**
- Consumes: `calculate_availability_pure` from Task 1; the guard test from Task 2.

- [ ] **Step 1: Verify the failing guard**

Run: `cd backend && pytest tests/test_calculations/test_report_availability.py -v`
Expected: excel guard PASS, pdf guard FAIL.

- [ ] **Step 2: Implement**

In `backend/reports/pdf_generator.py`:

a. Add imports at the top of the module:

```python
from decimal import Decimal

from backend.calculations.availability import calculate_availability_pure
```

b. In `_fetch_kpi_details`, replace:

```python
                else:
                    # Calculate availability from downtime
                    values = [85.0] * len(entries)  # Placeholder
```

with:

```python
                else:
                    values = [
                        float(
                            calculate_availability_pure(
                                Decimal(str(e.run_time_hours or 0)) + Decimal(str(e.downtime_hours or 0)),
                                Decimal(str(e.downtime_hours or 0)),
                            )
                        )
                        for e in entries
                    ]
```

(`entries` are `ProductionEntry` rows; `run_time_hours` is non-nullable, `downtime_hours` is nullable — the `or 0` covers both uniformly.)

- [ ] **Step 3: Run guard + PDF route tests**

Run: `cd backend && pytest tests/test_calculations/test_report_availability.py tests/test_api/test_reports.py tests/test_routes/test_reports_routes_real.py -v`
Expected: ALL PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/reports/pdf_generator.py
git commit -m "fix(reports): PDF availability computed from downtime, not 85.0 placeholder"
```

---

### Task 4: Remove the "Trend Charts" placeholder sheet

**Files:**
- Modify: `backend/reports/excel_generator.py` — delete `_create_charts_sheet` (lines ~406–419) and its call in `generate_report` (line ~74)
- Modify: `backend/routes/reports/comprehensive_reports.py:103` — remove the `- Trend Charts` docstring bullet
- Test: `backend/tests/test_api/test_reports_sheet_selection.py` (create — this file grows in Task 5)

**Interfaces:**
- Produces: comprehensive Excel workbook with exactly these sheets, in order: `Executive Summary`, `Production Metrics`, `Quality Metrics`, `Downtime Analysis`, `Attendance`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_api/test_reports_sheet_selection.py`:

```python
"""Characterization tests: Excel report sheets per report type (honest-surface PR)."""

from io import BytesIO

from openpyxl import load_workbook


def _sheets(test_client, auth_headers, report_type: str) -> list[str]:
    response = test_client.get(f"/api/reports/{report_type}/excel", headers=auth_headers)
    assert response.status_code == 200
    return load_workbook(BytesIO(response.content)).sheetnames


class TestComprehensiveSheets:
    def test_comprehensive_has_all_data_sheets_and_no_charts(self, test_client, auth_headers):
        assert _sheets(test_client, auth_headers, "comprehensive") == [
            "Executive Summary",
            "Production Metrics",
            "Quality Metrics",
            "Downtime Analysis",
            "Attendance",
        ]
```

(Reuse the `test_client` / `auth_headers` fixtures exactly as `backend/tests/test_api/test_reports.py` does.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest tests/test_api/test_reports_sheet_selection.py -v`
Expected: FAIL — sheet list ends with `'Trend Charts'`.

- [ ] **Step 3: Implement**

In `backend/reports/excel_generator.py`:
- Delete the line `self._create_charts_sheet(wb, client_id, start_date, end_date)` from `generate_report`.
- Delete the whole `_create_charts_sheet` method.

In `backend/routes/reports/comprehensive_reports.py`, remove the docstring line `    - Trend Charts`.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_api/test_reports_sheet_selection.py tests/test_api/test_reports.py -v`
Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/reports/excel_generator.py backend/routes/reports/comprehensive_reports.py backend/tests/test_api/test_reports_sheet_selection.py
git commit -m "fix(reports): drop placeholder Trend Charts sheet (data-first decision)"
```

---

### Task 5: Excel honors report type (sheet selection)

**Files:**
- Modify: `backend/reports/excel_generator.py` — `generate_report` signature + sheet dispatch
- Modify: `backend/routes/reports/production_reports.py:126`, `backend/routes/reports/kpi_reports.py:111` (quality), `backend/routes/reports/kpi_reports.py:214` (attendance)
- Test: extend `backend/tests/test_api/test_reports_sheet_selection.py`

**Interfaces:**
- Consumes: sheet names fixed in Task 4.
- Produces: `generate_report(self, client_id, start_date, end_date, output_path=None, sheets: Optional[Sequence[str]] = None)`. Sheet keys: `"summary"`, `"production"`, `"quality"`, `"downtime"`, `"attendance"`. `sheets=None` → all five (comprehensive endpoint stays call-compatible, no change there). Endpoint sets: production → `["summary", "production", "downtime"]`; quality → `["summary", "quality"]`; attendance → `["summary", "attendance"]`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_api/test_reports_sheet_selection.py`:

```python
class TestPerTypeSheets:
    def test_production_excel_sheets(self, test_client, auth_headers):
        assert _sheets(test_client, auth_headers, "production") == [
            "Executive Summary",
            "Production Metrics",
            "Downtime Analysis",
        ]

    def test_quality_excel_sheets(self, test_client, auth_headers):
        assert _sheets(test_client, auth_headers, "quality") == [
            "Executive Summary",
            "Quality Metrics",
        ]

    def test_attendance_excel_sheets(self, test_client, auth_headers):
        assert _sheets(test_client, auth_headers, "attendance") == [
            "Executive Summary",
            "Attendance",
        ]

    def test_all_four_types_produce_distinct_sheet_sets(self, test_client, auth_headers):
        sheet_sets = {
            report_type: tuple(_sheets(test_client, auth_headers, report_type))
            for report_type in ("comprehensive", "production", "quality", "attendance")
        }
        assert len(set(sheet_sets.values())) == 4
```

- [ ] **Step 2: Run to verify the new tests fail**

Run: `cd backend && pytest tests/test_api/test_reports_sheet_selection.py -v`
Expected: `TestComprehensiveSheets` PASSES; all four `TestPerTypeSheets` tests FAIL (every type currently returns all five sheets).

- [ ] **Step 3: Implement the generator parameter**

In `backend/reports/excel_generator.py`:

a. Extend the typing import already present to include `Sequence` (e.g., `from typing import Any, Dict, List, Optional, Sequence` — match whatever the existing line has and add `Sequence`).

b. Replace the `generate_report` signature and sheet-creation block:

```python
    def generate_report(
        self,
        client_id: Optional[str],
        start_date: date,
        end_date: date,
        output_path: Optional[Path] = None,
        sheets: Optional[Sequence[str]] = None,
    ) -> BytesIO:
        """
        Generate KPI Excel report.

        Args:
            client_id: Client ID (None for all clients)
            start_date: Report start date
            end_date: Report end date
            output_path: Optional file path to save Excel file
            sheets: Sheet keys to include ("summary", "production", "quality",
                "downtime", "attendance"). None = all sheets (comprehensive).

        Returns:
            BytesIO containing Excel data
        """
        sheet_builders = {
            "summary": self._create_summary_sheet,
            "production": self._create_production_sheet,
            "quality": self._create_quality_sheet,
            "downtime": self._create_downtime_sheet,
            "attendance": self._create_attendance_sheet,
        }
        selected = list(sheet_builders) if sheets is None else [key for key in sheet_builders if key in set(sheets)]

        wb = Workbook()

        # Remove default sheet
        wb.remove(wb.active)

        for key in selected:
            sheet_builders[key](wb, client_id, start_date, end_date)

        # Save to buffer or file
        buffer = BytesIO()
        wb.save(buffer if not output_path else str(output_path))
        buffer.seek(0)

        return buffer
```

(Iterating over `sheet_builders` keeps canonical sheet order regardless of the order callers pass.)

- [ ] **Step 4: Pass per-type sheet sets from the three endpoints**

In `backend/routes/reports/production_reports.py` (~line 126), change the call to:

```python
        excel_buffer = ExcelReportGenerator(db).generate_report(
            client_id=client_id, start_date=start, end_date=end, sheets=["summary", "production", "downtime"]
        )
```

In `backend/routes/reports/kpi_reports.py` quality endpoint (~line 111):

```python
        excel_buffer = ExcelReportGenerator(db).generate_report(
            client_id=client_id, start_date=start, end_date=end, sheets=["summary", "quality"]
        )
```

In `backend/routes/reports/kpi_reports.py` attendance endpoint (~line 214):

```python
        excel_buffer = ExcelReportGenerator(db).generate_report(
            client_id=client_id, start_date=start, end_date=end, sheets=["summary", "attendance"]
        )
```

The comprehensive endpoint (`backend/routes/reports/comprehensive_reports.py:117`) stays unchanged — `sheets=None` default means all.

- [ ] **Step 5: Run the full report test set**

Run: `cd backend && pytest tests/test_api/test_reports_sheet_selection.py tests/test_api/test_reports.py tests/test_routes/test_reports_routes_real.py tests/test_bootstrap/ -v`
Expected: ALL PASS (including the OpenAPI golden master — no routes changed).

- [ ] **Step 6: Commit**

```bash
git add backend/reports/excel_generator.py backend/routes/reports/production_reports.py backend/routes/reports/kpi_reports.py backend/tests/test_api/test_reports_sheet_selection.py
git commit -m "feat(reports): Excel honors report type via sheet selection (mirrors PDF kpis_to_include)"
```

---

### Task 6: Remove cosmetic email content toggles from the UI

**Files:**
- Modify: `frontend/src/components/dialogs/EmailReportsDialog.vue` (template lines ~96–134)

**Interfaces:**
- Consumes: nothing from other tasks (independent).
- Produces: dialog without the six dead checkboxes. The `config` object in the script KEEPS all six `include_*: true` fields — the POST/PUT payload contract with the backend is unchanged; only the controls disappear (they were never consumed by the generators — spec §6 defers them to the report-subscriptions spec).

- [ ] **Step 1: Remove the template block**

In `frontend/src/components/dialogs/EmailReportsDialog.vue`, delete this contiguous block (the "Report Content Options" comment, the label, and all six `v-checkbox` elements — keep the `v-divider` above it and the "Test Email Section" divider below it):

```html
            <!-- Report Content Options -->
            <v-label class="text-body-2 mb-2">{{ $t('reports.reportContent') }}</v-label>
            <v-checkbox
              v-model="config.include_executive_summary"
              :label="$t('reports.executiveSummary')"
              hide-details
              density="compact"
            />
```

…through…

```html
            <v-checkbox
              v-model="config.include_predictions"
              :label="$t('reports.forecastsPredictions')"
              hide-details
              density="compact"
              class="mb-4"
            />
```

Also delete the now-orphaned `<v-divider class="my-4" />` that sat directly above the removed block (avoid double dividers — after the edit there must be exactly one divider between the recipients combobox and the Test Email Section).

Do NOT touch the `config` defaults in the script block (lines ~217–222) — the payload stays identical.

- [ ] **Step 2: Verify no dangling references**

Run: `cd frontend && grep -n "include_" src/components/dialogs/EmailReportsDialog.vue`
Expected: only the script-block default assignments remain (`include_executive_summary: true`, etc.); zero template (`v-model`) references.

(The i18n keys `reports.reportContent`, `reports.executiveSummary`, etc. stay in both locale files — the referenced-keys gate checks that referenced keys resolve, not that every key is referenced.)

- [ ] **Step 3: Run frontend gates**

Run: `cd frontend && npm run lint && npm run test`
Expected: lint clean; all vitest suites pass (the only consumer test, `views.spec.ts:114`, mocks this dialog entirely).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dialogs/EmailReportsDialog.vue
git commit -m "fix(reports): remove email content toggles that were never consumed by generators"
```

---

### Task 7: Capability document

**Files:**
- Create: `docs/reporting/reporting-capabilities-and-gaps.md`

**Interfaces:**
- Consumes: the approved spec `docs/superpowers/specs/2026-07-29-reporting-capability-and-gap-decision-design.md` (§2 evidence, §3 concept register, §4 doc plan, §6 decision register) and `backend/tests/test_bootstrap/openapi_surface.json` (endpoint verification).

- [ ] **Step 1: Verify the endpoint catalog against the OpenAPI surface**

Run: `grep -oE '"/api/[^"]*(report|export|assumption)[^"]*"' backend/tests/test_bootstrap/openapi_surface.json | sort -u`

Record the exact list — every endpoint row in the doc's catalog MUST appear in this output (adjust to the file's actual JSON shape; the point is: no endpoint may be cited in the doc that the surface does not contain).

- [ ] **Step 2: Write the document**

Create `docs/reporting/reporting-capabilities-and-gaps.md` with exactly these five sections, populating them from the spec (do not invent content not present in the spec or the verified endpoint list):

```markdown
# Reporting: Capabilities, Gaps, and Decisions

**Status:** Living document — updated as new client report samples arrive.
**Spec:** docs/superpowers/specs/2026-07-29-reporting-capability-and-gap-decision-design.md

## 1. Committed positions
<The three positions from spec §1, verbatim in intent: no carbon-copying client
workbooks; data-first not chart-first; no reports without underlying data
(capture-first rule). One short paragraph each.>

## 2. What works today — report catalog
<One table per group, columns: Endpoint | Method | Formats | Key params | Role required | What it contains.
Groups: (a) PDF reports x4 (type-aware via kpis_to_include: production=[efficiency, performance, availability, oee],
quality=[fpy, rty, ppm, dpmo], attendance=[absenteeism], comprehensive=all);
(b) Excel reports x4 (type-aware via sheet selection as of this PR:
production=Summary+Production+Downtime, quality=Summary+Quality,
attendance=Summary+Attendance, comprehensive=all five sheets);
(c) GET /api/reports/available; (d) email config CRUD + /test + POST send-manual
(note: config is in-memory, scheduler is daily-only — see gap register);
(e) admin GET /api/assumptions/variance (JSON); (f) the 9 CSV entity exports
under /api/export/** — the data-first backbone. Every row verified against
openapi_surface.json in Step 1.>

## 3. Gap register — decisions
<The table from spec §6, verbatim, plus one status column updated for this PR:
the four make-real/remove-now rows marked DONE with this PR, the defer rows
pointing at their named future spec.>

## 4. Concept register (living)
<Spec §3 in full: the five management questions, each concept with
have/partial/missing grade and notes; the reportable-today vs capture-first
split; the structural observations. Add a final subsection "How to update
this register": each new client sample gets analyzed, its concepts slotted
under a question, grades revised, and capture-first items routed to the
deferred-spec queue.>

## 5. Deferred-spec queue
<Spec §4 item 4 list, verbatim: pivot/summarization layer (blocked on samples
+ register), report subscriptions, downtime cause taxonomy, labor-hours
accounting (capture-first), model extensions (capture-first).>
```

Style: management-readable prose, tables for enumerable facts, no unexplained jargon; en only (project docs are English).

- [ ] **Step 3: Self-check the doc**

- Every endpoint cited appears in the Step 1 output.
- Every gap from spec §6 appears in §3 of the doc with a decision.
- No "TBD"/placeholder text.
- The four honest-surface items are marked as shipped in this PR.

- [ ] **Step 4: Commit**

```bash
git add docs/reporting/reporting-capabilities-and-gaps.md
git commit -m "docs(reporting): capability catalog, gap decisions, living concept register"
```

---

### Task 8: Full verification sweep

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite with coverage gate**

Run: `cd backend && pytest tests/`
Expected: ALL PASS, coverage ≥75% (gate enforced by config).

- [ ] **Step 2: Full frontend gates**

Run: `cd frontend && npm run lint && npm run test`
Expected: clean lint, all tests pass, coverage thresholds met.

- [ ] **Step 3: Grep sweep for leftovers**

Run: `grep -rn "Trend Charts\|\[85.0\] \* len\|\"availability\": 90.0" backend/reports/ backend/routes/reports/`
Expected: zero matches.

- [ ] **Step 4: Confirm branch is clean and pushed**

```bash
git status --short
git push -u origin feat/reporting-capability-honest-surface
```

Then hand off to the standard pipeline: `/cross-review` → PR (production_reports/kpi_reports/excel_generator/pdf_generator/availability/EmailReportsDialog/doc) → 4-check CI green → user-confirmed merge → deploy Render + VM → live verification (download production vs quality Excel from the VM, confirm distinct sheets + non-placeholder availability values).
