# Labor-Hours Metrics (Cycle 3 PR-B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Cycle 3's derived Q1 metrics — the labor-hours summary endpoint, the additive available-basis efficiency variant, and the Excel Labor Hours rows — plus the Q1 concept re-grades, per spec `docs/superpowers/specs/2026-08-05-labor-hours-accounting-design.md` §6 + §9.

**Architecture:** A new aggregation function in `backend/calculations/labor_hours.py` (beside PR-A's pure helpers, reusing its metadata sets) feeds a new `labor_hours_router` sub-module in `backend/routes/kpi/` (own `/api/kpi` prefix, registered in `__init__.py` per the documented sub-module pattern), the Excel summary rows, and nothing else. The efficiency variant is additive on the existing efficiency KPI response. This PR ADDS A ROUTE → `openapi_surface.json` MUST be regenerated.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, openpyxl, pytest. (No frontend changes beyond none — the dashboard consumes nothing new this PR; pivot UIs are Cycle 4.)

## Global Constraints

- Branch: `feat/labor-hours-metrics` (exists, on merged PR-A `86c135c`). PR-B ONLY: no new capture fields, no UI, no schema changes to attendance/employee write paths.
- All JSON leaves are numbers — no Decimal-to-string leakage (repo structural guard + #145 standing rule); coerce at the route boundary.
- Client scoping via `resolve_client_scope`; NEVER bare `scope.as_single()` (PR #144 footgun — guard on `client_ids is not None and len == 1` if single-client logic is needed; prefer `scope.filter()` for multi-safe aggregation).
- Efficiency variant is ADDITIVE — existing efficiency values byte-identical; entries without allocation data contribute full actual hours (spec §6, conservative default via PR-A's `available_for_efficiency_hours`).
- Excel rows zero-data guarded (no fake "0.0 At Risk" rows on empty windows — Cycle 2 lesson).
- Date filtering on DateTime columns uses `func.date(...)` (cast-to-Date structurally banned).
- pytest FOREGROUND from `backend/` with the Bash timeout PARAMETER set to 600000; exact expected values with derivation comments; one expected code per assertion; mypy gate blocking.
- Commits end with: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Aggregation function

**Files:**
- Modify: `backend/calculations/labor_hours.py` (append; PR-A's helpers unchanged)
- Test: `backend/tests/test_calculations/test_labor_hours.py` (extend)

**Interfaces:**
- Consumes: PR-A's `BILLABLE_CATEGORIES`/`PRODUCTIVE_CATEGORIES` (via labor_taxonomy), `available_for_efficiency_hours`, `effective_labor_class`.
- Produces (contractual for Tasks 2-3):

```python
def summarize_labor_hours(
    db: Session, client_ids: Optional[Sequence[str]], start_date: date, end_date: date
) -> dict:
    """Returns (all Decimal values — callers coerce to float at the boundary):
    {
      "totals": {"scheduled": D, "actual": D, "normal": D, "double": D, "triple": D,
                 "billed": D, "available_for_efficiency": D},
      "by_labor_class": {"direct": {"actual": D, "billed": D, "available_for_efficiency": D},
                          "indirect": {...}, "unclassified": {...}},
      "by_category": {<category>: D hours, ... only categories present},
      "entry_counts": {"total": int, "with_split": int, "with_allocations": int},
    }
    """
```

- [ ] **Step 1: Write the failing test**

```python
class TestSummarizeLaborHours:
    def test_summary_with_derivations(self, db_session):
        """Seed one client, 2 employees (E1 direct, E2 indirect), 3 entries:
        - A (E1, direct): scheduled 8, actual 10, split 8/2/0,
          allocations billed_production 7 + training 1
          -> billed 7, available 10-1=9
        - B (E2, indirect): scheduled 8, actual 8, unsplit,
          allocations billed_production 8 -> billed 8, available 8
        - C (E1 but labor_class_override='indirect'): scheduled 8, actual 8,
          split 8/0/0, NO allocations -> billed 0, available 8 (conservative)

        totals: scheduled 24, actual 26, normal 16, double 2, triple 0,
                billed 15, available 25
        by_labor_class: direct {actual 10, billed 7, available 9}   # only A
                        indirect {actual 16, billed 8, available 16} # B + C (override)
                        unclassified {actual 0, billed 0, available 0}
        by_category: {billed_production: 15, training: 1}
        entry_counts: {total 3, with_split 2, with_allocations 2}
        """
        # build via TestDataFactory (client, employees with labor_class, entries with
        # shift_date=datetime(2026, 8, 1, 6, 0), allocations via the ORM relationship),
        # then call summarize_labor_hours(db_session, ["LH-SUM-CL"], date(2026,8,1), date(2026,8,1))
        # and assert EVERY leaf above exactly (Decimal comparisons).

    def test_empty_window_returns_zeroed_totals(self, db_session):
        # no entries in range -> totals all Decimal 0, entry_counts total 0,
        # by_category {}, all three by_labor_class buckets zeroed

    def test_client_ids_none_means_all_clients(self, db_session):
        # two clients seeded; client_ids=None sums both; ["one"] filters
```

(Write these CONCRETE; the docstring math is the binding derivation.)

- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement** — one query for entries in range (`func.date(AttendanceEntry.shift_date)` between the dates; `client_id.in_(client_ids)` only when `client_ids is not None`), `lazy="selectin"` pulls allocations batched; one IN-query for the employees' labor_class (mirror PR-A's `_build_attendance_responses_batch` batching); pure-Python aggregation using PR-A's helpers per entry. No N+1.
- [ ] **Step 4: Run green + `pytest tests/test_calculations/ -q --no-cov`.**
- [ ] **Step 5: Commit** — `feat(labor): summarize_labor_hours aggregation (Q1 totals, class rollups, category totals)` + trailer.

---

### Task 2: `GET /api/kpi/labor-hours` route

**Files:**
- Create: `backend/routes/kpi/labor_hours.py`
- Modify: `backend/routes/kpi/__init__.py` (register `labor_hours_router` per the documented sub-module pattern — read the file's own docstring)
- Modify: `backend/tests/test_bootstrap/openapi_surface.json` (REGENERATED — the golden-master test fails and names the command; run exactly that)
- Test: `backend/tests/test_routes/test_labor_hours_kpi.py` (create; mirror the kpi-route harness used by test_kpi_routes_real.py)

**Interfaces:**
- Consumes: Task 1's `summarize_labor_hours`.
- Produces: `GET /api/kpi/labor-hours?start_date&end_date[&client_id]` — auth `get_current_user` + `resolve_client_scope`; passes `scope.client_ids` straight through (None = all for admin — multi-client-safe by construction, no as_single anywhere); response = Task 1's dict with EVERY Decimal coerced to float (reuse/mirror the `_coerce_decimal_leaves` idiom from routes/kpi/otd.py — nested dicts need a recursive variant; write `_coerce_nested(obj)` handling dict/Decimal leaves).

- [ ] **Step 1: Failing route tests** — (a) seeded Task-1 scenario via API → exact float leaves (`totals.billed == 15.0` etc., derivation comment referencing Task 1's math); (b) leader with two clients, no client_id → 200 aggregated across both (NOT 400 — the #144 regression class, pin it); (c) date-validation reuses the repo's `validate_date_range` idiom (reversed range → 400); (d) unauthenticated → 401.
- [ ] **Step 2: Run red.**
- [ ] **Step 3: Implement route + register router.**
- [ ] **Step 4: Regen surface** — `pytest tests/test_bootstrap/ -q` fails → run the named regen command → confirm ONLY the new route entry changed (`rtk proxy git diff backend/tests/test_bootstrap/openapi_surface.json | head -20`).
- [ ] **Step 5: Run green (route tests + bootstrap + `pytest tests/ -k "kpi" -q --no-cov`).**
- [ ] **Step 6: Commit** — `feat(labor): GET /api/kpi/labor-hours summary endpoint` + trailer.

---

### Task 3: Additive available-basis efficiency variant

**Files:**
- Modify: locate the PRIMARY efficiency KPI response first — `rtk proxy grep -rn "efficiency" backend/routes/kpi/dashboard.py backend/routes/kpi/efficiency.py backend/routes/kpi/calculations.py | grep -i "def \|percentage"` and read the candidates; the variant lands on the endpoint the KPI dashboard's efficiency card consumes (trace `frontend/src/stores/kpi.ts` / its api service for the efficiency fetch to identify it definitively — do NOT guess).
- Test: extend that endpoint's existing test module.

**Interfaces:**
- Consumes: Task 1's `summarize_labor_hours` (for the available-hours denominator over the same window/scope) OR PR-A's per-entry helper — choose the SAME data path the endpoint already uses for its scheduled-hours denominator, swapping the denominator source; document the choice.
- Produces: the response gains `efficiency_available_basis: Optional[float]` (None when no attendance/allocation data links to the window — never fabricate); ALL existing fields byte-identical.

- [ ] **Step 1: Failing tests** — seeded window where available < scheduled (one entry with training allocation): existing efficiency value asserted UNCHANGED (pin the exact pre-existing expected value from the module's current tests) AND `efficiency_available_basis` > the scheduled-basis figure (exact derivation: earned hours / available × 100, hand-math in comment); window with no allocation data → variant equals the entries' actual-hours basis per the conservative default; no attendance at all → variant None.
- [ ] **Step 2: Run red.** **Step 3: Implement (additive only).** **Step 4: Run the module + `pytest tests/ -k "efficiency" -q --no-cov` — zero changed expectations besides the new field.** **Step 5: Commit** — `feat(labor): additive available-basis efficiency variant` + trailer.

---

### Task 4: Excel Labor Hours rows

**Files:**
- Modify: `backend/reports/excel_generator.py` (`_fetch_kpi_summary_data` — follow the OTD-rows precedent from Cycle 2 exactly: single data-source call, rows appended, zero-data guard)
- Test: extend `backend/tests/test_calculations/test_report_availability.py` (the module holding the Cycle-2 Excel row tests)

**Interfaces:**
- Consumes: Task 1's `summarize_labor_hours` (single call, client-scoped — `[client_id]` when present; SKIP the block entirely when `client_id` is None, matching the OTD precedent).
- Produces: rows appended to the summary sheet's KPI table: `("Labor Hours — Billed", <billed>, ...)`, `("Labor Hours — Available", <available>, ...)`, `("OT Hours — Double", <double>, ...)`, `("OT Hours — Triple", <triple>, ...)` — value column float; status/target columns per the sheet's existing row idiom (read how OTD rows fill those cells; hours rows have no % target — use the idiom's neutral/blank convention, decide from the sheet's real shape and document). Guard: rows only when `entry_counts["total"] > 0`.

- [ ] **Step 1: Failing tests** — seeded scenario → exact cells (derivations); zero-attendance window → rows absent (exact assertion of what IS at those rows).
- [ ] **Step 2: Run red.** **Step 3: Implement.** **Step 4: Run `pytest tests/ -k "excel or report" -q --no-cov` green.** **Step 5: Commit** — `feat(labor): Excel summary Labor Hours rows (zero-data guarded)` + trailer.

---

### Task 5: Living-doc re-grade + full verification

**Files:**
- Modify: `docs/reporting/reporting-capabilities-and-gaps.md`

- [ ] **Step 1: Edits (read current text first, match verbatim):**
  - §4 Q1 rows → **have** with Cycle-3 notes: `OT tiers (Normal/Double/Triple)` missing→have ("captured 3-way split on AttendanceEntry; totals on /api/kpi/labor-hours (Cycle 3)"); `Direct vs indirect labor` missing→have ("Employee.labor_class + per-entry override; effective-class rollups (Cycle 3)"); `Billed vs available-for-efficiency hours` missing→have ("8-category hour-allocation ledger; billed & available derivations (Cycle 3)"); `Operator attendance vs available hours to commit` partial→have ("available_for_efficiency from allocations; additive efficiency variant (Cycle 3)").
  - §3 labor-hours gap row status → `**DONE — Cycle 3 (PR-A capture #165 + PR-B metrics, this PR)**` (match the row's current text first).
  - §5 Cycle 3 line: append ` **[DONE — this PR]**`.
- [ ] **Step 2: Full battery** — backend `pytest tests/ -q` (≥75%); frontend suites untouched but run `npm run test -- --run` once to prove no accidental coupling; grep sweep for any new string-literal category/class values outside sanctioned files.
- [ ] **Step 3: Commit** — `docs(reporting): re-grade Q1 labor concepts to 'have' (Cycle 3 shipped)` + trailer.

---

### Task 6: Cross-review and PR (controller-level)

- [ ] **Step 1:** `git diff --stat main...HEAD` — this plan + backend (calculations/routes/kpi/reports/tests/openapi surface) + living doc. Nothing else.
- [ ] **Step 2:** `/cross-review` for final HEAD.
- [ ] **Step 3:** Push; PR `feat(labor): labor-hours metrics — Q1 summary endpoint, efficiency variant, Excel rows (Cycle 3 PR-B)`; standard footer.
- [ ] **Step 4:** `gh pr checks <n> --watch` (explicit number) → 7/7 → merge per standing order → main verify → Render auto → VM deploy + live-verify §10-B (labor-hours endpoint totals match seeded math on MariaDB, efficiency variant present, Excel rows) → Cycle 3 complete; Cycle 4 (pivot layer) brainstorm next.
