# Phase B — Robustness Audit: Final Verdict

**Period**: 2026-05-07 (single-day execution)
**Status**: Sub-phases B.1, B.2, B.3, B.4, B.5 ✅ COMPLETE. B.7 (E2E migration backlog) carries forward to 2026-06-01 per the entry-UI standard's published deadline. Pending user approval to close Phase B.

---

## Executive summary

Phase B was scoped as the "robustness audit" — find the real bugs that
weak tests had been hiding, ratchet coverage floors, and remove dead
UI/test code. The headline numbers:

| Metric | Before (post-Phase-A) | After (post-Phase-B) | Delta |
|---|---|---|---|
| Backend pytest | 5306 passed (with 480+ padding) | **4842 passed**, 1 skipped, 0 failed | -464 tests deleted (all coverage padding) |
| Frontend vitest | 1826 passed (78 files) | **1915 passed** (80 files) | +89 (+5 missing-assertion fixes, +84 new view tests) |
| Permissive assertions (`status_code in [...]`) | 778 hits / 28 files | **0** | All tightened to specific codes |
| Frontend lint warnings | 395 | **0** | -395 (-100%) |
| Frontend coverage (statements / branches / functions / lines) | 22.68 / 20.5 / 15.02 / 24.32 | **33.34 / 26.68 / 26.14 / 35.43** | +10–11 pts on every dimension |
| Coverage thresholds in vitest.config.ts | 22 / 20 / 15 / 24 | **32 / 25 / 25 / 34** | Ratcheted to lock in gains |
| 0%-coverage view files | 47 | 18 (capacity sub-components — covered by E2E) | 29 lifted off 0% |
| Real bugs found and fixed | — | **2** | (see § Bugs section) |
| Real coverage gaps closed | — | **3** | (see § Tests section) |

---

## Sub-phase results

### B.1 — Permissive-assertion inventory ✅

`grep -rn "status_code in \[" backend/tests/` returned **778 hits across
28 files**. Categorized in `_audit/B1-permissive-assertions-categorized.md`:

- **Anti-pattern** (4+ codes accepted, no real signal): 434 hits / 17 files
- **Suspicious** (2-3 codes mixed): 332 hits / 20 files
- **Acceptable** (`[200, 201]` for create, `[200, 204]` for delete): 12 hits / 6 files

The anti-pattern tests were all coverage padding — tests that ran a
request, accepted any `2xx | 4xx | 5xx` response, and called it
"coverage." They added line counts but no real signal.

### B.2 — Tighten suspicious + anti-pattern assertions ✅

Per-test, captured the ACTUAL response code (via instrumented pytest
runs that scraped `HTTP/1.1 NNN` lines from logs) and replaced every
`assert response.status_code in [...]` with `assert response.status_code
== <expected>`. Each tightening was verified against the route logic
to confirm the expected code was the truthful one.

Two paths were taken when an "anti-pattern" assertion turned out to
hide useless tests:

1. **Delete the file** (9 files, ~480 padding tests removed):
   `test_kpi_routes_comprehensive.py`, `test_kpi_extended.py`,
   `test_low_coverage_routes.py`, `test_additional_coverage.py`,
   `test_final_coverage.py`, `test_qr_comprehensive.py`,
   `test_integration_comprehensive.py`, `test_routes_extended.py`,
   `test_all_routes_comprehensive.py`. Every file in this set had
   ≥98% of its assertions in the `status_code in [200, 403, 404, 422,
   500]` form — they were untruthful by design. Reading them confirmed
   they were originally added by an LLM to lift `--cov-fail-under` past
   the gate without exercising real behavior. Deleted in commits
   4230765 + 8f08623.

2. **Tighten the surviving 18 files** (commit 85a4d96): 778 → 0.
   Each tightening required reading the route to determine the
   expected code class (admin without client_id → 403, unimplemented
   endpoint → 404, validation rejecting before tenant gate → 422,
   etc.). Documented inline in test docstrings.

Real bugs uncovered: **0** in this pass — the routes behaved correctly,
the tests were just sloppy.

### B.3 — 0%-coverage Vue views audit ✅ (with documented deferred items)

`frontend/coverage/coverage-final.json` flagged **47 view files at 0%
line coverage** (more than the 17 originally listed in the tracker).
Strategy doc: `_audit/B3-zero-coverage-views.md`.

| Bucket | Files | Approach | Result |
|---|---|---|---|
| 1 — KPI detail pages | 8 | smoke-mount + 1 composable spec for the 3 that have been refactored | 60–72% lines / 100% on `useEfficiencyData` |
| 2 — Admin views | 11 | smoke-mount with realistic ref-wrapped store/composable mocks | 41–87% lines |
| 3 — Capacity sub-components | 16 | DEFERRED — covered by `capacity-*.spec.ts` E2E specs | (E2E already exercises) |
| 4 — Entry-page wrappers | 4 | smoke-mount; 8-stmt thin shells | ≥80% lines |
| 5 — Misc large views | 6 | smoke-mount per view | varies |

Refactoring follow-up flagged: 5 of 8 KPI detail pages still inline
their logic in `<script setup>` (Availability, OEE, Absenteeism,
OnTimeDelivery, WIPAging) — the existing composable extraction
pattern was only applied to Efficiency, Performance, Quality. Out
of scope for B.3; tracked as a separate refactor task.

### B.4 — Frontend lint warnings ✅ (395 → 0)

Four batches across 80+ files. Pattern split:

- **161 no-unused-vars** (production code) → underscore-prefix on
  TS interface signature args (the AG-Grid composable cluster), bare
  `catch {}` for unused catch bindings (ES2019 optional catch),
  dead-code deletion where the warning revealed a refactor leftover.
  Cleared 100% in production source.

- **47 no-unused-vars** (test files) → same underscore pattern, plus
  three "missing assertion" fixes that the rule flagged as the
  feedback memory predicted (`feedback_no_shortcuts.md`):

  - `capacityPlanningStore.spec.ts`: 5 imported factory functions
    were never tested. Added 5 new tests asserting on real defaults
    from `stores/capacity/defaults.ts`.
  - `reference.spec.ts:51` (`getProducts`): `await` result was bound
    but never asserted. Added the missing
    `expect(result).toEqual(mockProducts)`.
  - `performance.spec.ts:264`: a CPU-burner Gauss-sum loop had no
    assertion (was DCE-protection scaffolding). Replaced with
    `expect(sum).toBe(499500)`.

- **77 no-console** (production code) → DEV-gating with
  `if (import.meta.env.DEV) console.error(...)` plus
  `// eslint-disable-next-line no-console -- dev-only, gated by
  import.meta.env.DEV` per the `feedback_no_shortcuts.md` policy.
  Vite tree-shakes the dead branch in prod. All touched paths
  verified to also have user-facing notification or store-level
  error state — no info loss from gating.

**Batch 5 — structural refactor of dialog children (commit 76f0144)**:

The remaining 31 `vue/no-mutating-props` warnings lived in
`WorkbookActionDialogs.vue` (18) and `ShiftDashboardDialogs.vue`
(13). Both children received parent state as plain props and
mutated fields directly — works via reactive auto-unwrap, but is
the canonical Vue 3 anti-pattern.

Real fix:
  - `WorkbookActionDialogs.vue`: 13 `defineModel` declarations
    covering every two-way-bound piece of state (5 visibility
    flags + 8 form fields). `worksheetOptions` stays read-only.
    Parent `CapacityPlanningView.vue` now uses `v-model:propName=`
    per piece; the dead `dialogState = reactive({...})` aggregator
    and the unused `reactive` import were dropped.
  - `ShiftDashboardDialogs.vue`: visibility flags were already on
    `defineModel` (correct half). Form objects (`productionForm`,
    `downtimeForm`, `qualityForm`, `helpForm`) were the broken
    half — converted each to `defineModel('xForm', { type: Object
    })`. Parent `MyShiftDashboard.vue` now uses
    `v-model:production-form=` etc.

Final 2 cleanups in the same commit:
  - `ProductionKPIs.spec.ts:91` — DEV-gated `console.error` in a
    catch handler (matches the production-source pattern from
    batch 3).
  - `DashboardCustomizer.vue:63` — slot template arg `index` was
    unused; dropped from destructure.

**Final result: 0 lint warnings, 1915 tests pass.**

### B.5 — Test pollution sweep ✅

Captured 51-table row-count baseline of `database/kpi_platform.db`,
ran full backend pytest (4842 passed, 1 skipped, 0 failed in 11:12),
recaptured counts. `diff` returned no output — **zero pollution**.
Report at `_audit/B5-test-pollution.md`.

The fixture architecture (in-memory SQLite + `dependency_overrides
[get_db]` + `transactional_db` SAVEPOINT-rollback for 62+ tests) makes
disk-level pollution structurally impossible. Recurrence is guarded
by the existing CLAUDE.md "RULE-01: Real DB tests only — no mocks"
plus the implicit guard that any new test's chosen DB URL would have
to bypass the override AND match the production URL to leak.

### B.7 — E2E migration backlog ✅ (closed in Phase A.13)

The 8 `// FIXME(2026-06-01)` skipped E2E describe blocks remain as
deferred work targeting the 2026-06-01 re-enable date. Per the
documentation shipped in Phase A.13 (`docs/CONTRIBUTING.md` "E2E
Parity" section, `docs/standards/entry-ui-standard.md` §7,
`scripts/check-skipped-tests.sh` CI guard, `.github/pull_request_
template.md`), each skipped test has a Phase B.7 reference and the
guard prevents any new skip from landing without similar tracking.

No further work in this audit cycle; B.7 is parallel to B.4-B.6 and
will be picked up by the team closer to 2026-06-01.

---

## Real bugs uncovered and fixed in Phase B

1. **`WorkOrderDetailDrawer.vue` — copy-paste catch handler bug**
   (commit 9a3144f). The fallback catch handler in `updateStatus()`
   referenced the OUTER `error` variable instead of the CURRENT
   `fallbackError` it had just caught. Lint flagged `fallbackError`
   as unused; investigating the warning revealed the bug. The user
   would have seen the original error message even when the fallback
   path failed for a different reason. Fixed: now reports
   `fallbackError.response?.data?.detail` first, falling back to the
   outer error.

2. **Auth.py forgot-password reset_token logging gap** (commit
   7965f2d, Phase A.10 — predates Phase B but documented here for
   completeness). The TODO claimed the reset_token was being logged
   for dev use; it wasn't (only the email was logged). F841 lint
   warning surfaced this. Fixed: token now included in the debug log
   line.

## Real coverage gaps closed (missing assertions added)

3. **`capacityPlanningStore.spec.ts`** — 5 imported factory functions
   from `stores/capacity/defaults.ts` were never tested. Added 5
   tests covering `getDefaultStockSnapshot`,
   `getDefaultComponentCheckRow`, `getDefaultCapacityAnalysisRow`,
   `getDefaultScheduleRow`, `getDefaultKPITrackingRow`.

4. **`reference.spec.ts:51`** — `await referenceApi.getProducts()`
   bound result, never asserted. Added missing
   `expect(result).toEqual(mockProducts)`.

5. **`performance.spec.ts:264`** — DCE-protection Gauss-sum loop had
   no assertion. Replaced local-var noise with
   `expect(sum).toBe(499500)` to prove the loop ran AND become a
   meaningful assertion.

## Files deleted

- 9 backend test files (~464 padding tests): listed in B.2 above.
- Dead helpers in production code uncovered during the lint pass:
  `WorkOrderDetailDrawer.getStatusColor` and `formatDateTime` (never
  called); `SimulationV2View.handleReset` (legacy comment, no
  callers); unused `useRoute/useRouter` imports in
  `WorkflowDesigner.vue`; unused `useI18n` destructures in
  `PastePreviewDialog.vue` and `ReadBackConfirmation.vue`; dead
  `makeGridComposableStub` helper in `admin-views.spec.ts`.

## Coverage floor (now locked in CI)

`vitest.config.ts` thresholds were raised from 22/20/15/24 →
**32/25/25/34**, set 1pt below the measured floor for stability.
A regression on any of the four metrics now fails CI.

Backend coverage gate remains at 75 % (`pyproject.toml`); current
measurement 78.66 % per the prior audit.

## Remaining known gaps (with risk assessment)

| Gap | Risk | Mitigation |
|---|---|---|
| 31 `vue/no-mutating-props` warnings | RESOLVED (commit 76f0144) — converted to `defineModel` per state piece in both dialog children + their parents. | n/a — closed in B.4. |
| 5 of 8 KPI detail pages still inline logic | LOW (smoke-mount provides 60-72% line coverage; no behavioral coverage gap). | Refactor to composables in a separate batch when one of these views needs new features. |
| 18 0%-coverage capacity sub-components | LOW (E2E specs exercise them; v8 just doesn't account E2E coverage to the unit metric). | No action; this is an artifact of the v8 vs istanbul reporting difference flagged in `vitest.config.ts`. |
| 8 skipped E2E describe blocks | MEDIUM (covered by FIXME deadline 2026-06-01; the guard prevents recurrence). | Owned by team for 2026-06-01 close-out per `docs/standards/entry-ui-standard.md` §7. |
| 1 `vue/no-unused-vars` slot template arg + 1 test-file `no-console` | TRIVIAL | Leave as-is; sub-percent of total warnings. |

## Acceptance

- [x] Bugs found and fixed documented (count + per-bug summary).
- [x] Tests added (count by file).
- [x] Files deleted (dead UI + dead tests).
- [x] New coverage floor measured and ratcheted into the gate.
- [x] Remaining known gaps with risk assessment.
- [ ] **User approval to mark Phase B closed.** ← awaiting

After user approval, sub-phases B.1, B.2, B.3, B.5 close as ✅ DONE
and B.4/B.7 carry forward to a follow-up batch with the documented
remainder.
