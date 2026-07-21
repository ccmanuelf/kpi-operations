# Reporting-Wiring Fix — KPIDashboard Report Buttons (Design)

**Date:** 2026-07-21
**Status:** Approved design (root-caused via systematic-debugging, running-app-verified) → ready for implementation plan
**Type:** Bug fix + test-gap closure. Part of deliverable #2 (reporting); the reporting **design-gap** items (Excel-per-type, email content toggles, in-memory config, daily-only scheduler, placeholder values) are explicitly deferred to a later brainstorm informed by the client's real Excel reports.

## The bug (root cause, verified against the running app)

The KPIDashboard **Export PDF / Export Excel / Email** buttons are dead — they call backend paths that were never implemented. Verified against the live Render demo (unauthenticated probe distinguishes a missing route (404) from an existing one (401/403/405/422)):

| Live UI action | Frontend calls (`useKPIReports.ts`) | After `/api/v1`→`/api` rewrite | Backend | Probe |
|---|---|---|---|---|
| Export PDF | `GET /reports/pdf` | `/api/reports/pdf` | not defined | **404** |
| Export Excel | `GET /reports/excel` | `/api/reports/excel` | not defined | **404** |
| Email send | `POST /reports/email` | `/api/reports/email` | not defined | **404** |
| *(target)* Comprehensive PDF | — | `/api/reports/comprehensive/pdf` | defined | 401 (exists) |
| *(target)* Comprehensive Excel | — | `/api/reports/comprehensive/excel` | defined | 401 (exists) |
| *(target)* Manual email | — | `POST /api/reports/send-manual` | defined | 405 on GET (exists, POST-only) |

**Root cause:** `frontend/src/composables/useKPIReports.ts` was written against report endpoints that don't exist. The real endpoints (`comprehensive/pdf`, `comprehensive/excel`, `send-manual`) exist and their **request contracts already match** what the composable sends (`{client_id,start_date,end_date}` for the downloads; `{client_id,start_date,end_date,recipient_emails}` for email — `send-manual`'s `ManualReportRequest` ignores the extra `include_excel` field, Pydantic v2 default).

**The `/api/v1` prefix is NOT the cause** — `backend/bootstrap/app_config.py::APIVersionMiddleware` rewrites `/api/v1/...`→`/api/...`; probe proved `/api/v1/reports/comprehensive/pdf`→401 (reaches a real route). The prefix is a red herring.

**Why it shipped green (the test gap the user flagged):** `frontend/src/services/__tests__/reports.spec.ts` **asserts the broken paths** — e.g. `exportPDF` "calls GET `/reports/pdf`", `getDailyReport` "calls GET `/reports/daily/:date`". The unit suite verified the *wrong* contract, so it stayed green while the buttons 404'd. And no e2e test exercises the report buttons end-to-end. Both gaps must be closed, not just the paths.

## Scope of the fix

### 1. Repoint the three live composable functions (`useKPIReports.ts`)
- `downloadPDF`: `GET /reports/pdf` → `GET /reports/comprehensive/pdf`
- `downloadExcel`: `GET /reports/excel` → `GET /reports/comprehensive/excel`
- `sendEmailReport`: `POST /reports/email` → `POST /reports/send-manual`

Params are unchanged (they already match). Blob handling, filenames, snackbars unchanged.

### 2. Null-client guard on the email path
The comprehensive **PDF/Excel** endpoints accept an omitted `client_id` (= all clients), so those buttons work with or without a selected client — no change needed. But `send-manual`'s `ManualReportRequest.client_id` is a required non-null `str`; posting `client_id: null` (the "All Clients" state) would 422. Fix: in `sendEmailReport`, if no client is selected, do **not** call the API — show a clear warning (i18n) telling the user to select a client first, mirroring the existing `selectClientFirst` pattern already used elsewhere in the dashboard. (PDF/Excel remain all-clients-capable.)

### 3. Fix the second broken button, remove dead code + fix the tests that lock in the bug
- **Correction found during execution:** `exportExcel` is NOT dead. `DashboardView.vue` (the home page, route `/`) calls `api.exportExcel()` from its "Export to Excel" button → `/reports/excel` → **404**, silently falling back to CSV. This is a **second live instance** of the same bug. Decision (user-approved): **repoint `exportExcel` → `/reports/comprehensive/excel`** (real Excel workbook, consistent with the KPIDashboard fix) and fix its misleading `production_entries_*.xlsx` download name → `KPI_Report_*.xlsx`.
- Delete the genuinely-unused, wrong-path helpers in `services/api/reports.ts`: `getDailyReport`, `getWeeklyReport`, `getMonthlyReport`, and `exportPDF` — confirmed **no callers** anywhere in `src/` (only their own tests). Keep the working helpers: `exportExcel` (repointed), `getEmailReportConfig`, `saveEmailReportConfig`, `updateEmailReportConfig`, `sendTestEmail`, `triggerManualReport`.
- Rewrite `reports.spec.ts`: remove the describe-blocks for the 4 deleted helpers (they assert 404 paths); update the `exportExcel` test to assert `/reports/comprehensive/excel`; keep the email-config + `triggerManualReport` tests.
- E2e (Task 3) gains a guard for the home-page DashboardView Excel button too.

### 4. Add the missing regression guards
- **Unit (composable):** new `useKPIReports.spec.ts` mocking the `api` module, asserting `downloadPDF`→`/reports/comprehensive/pdf`, `downloadExcel`→`/reports/comprehensive/excel`, `sendEmailReport`→`/reports/send-manual` with the expected params, and that `sendEmailReport` short-circuits (no API call) when no client is selected.
- **E2E (Playwright, the guard that would have caught this):** a test that logs into the demo, opens the KPIDashboard report menu, clicks **Export PDF** and **Export Excel**, and asserts a **successful download / non-404 response** (intercept the `**/reports/comprehensive/*` responses and assert `status < 400`, or assert the browser download event fires). Add an email-flow assertion that the request goes to `**/reports/send-manual` and returns non-404. This runs in the `e2e-sqlite` job so the class can't silently regress.

## Explicitly out of scope (deferred to the post-pictures brainstorm)
- Excel endpoints ignoring report type (all 4 emit identical workbooks).
- Email content toggles (`include_*`) that are stored but never consumed by generators.
- In-memory-only email config (not persisted across restart).
- Daily-only APScheduler that ignores the saved frequency/recipients.
- Placeholder report values (availability 85/90, downtime impact 0, "charts will be embedded here").
- A report-type selector on the dashboard (the button maps to Comprehensive per the approved decision).

These are real, but they are **design decisions** best made against the client's actual Excel reports, not folded into this wiring fix.

## Testing / success criteria
- The three dashboard buttons perform their action against a real, existing endpoint (no 404).
- `sendEmailReport` with no client selected shows a "select a client" warning and makes **no** failing API call.
- New composable unit test is genuinely red before the path fix and green after (reviewer rebuilds the pre-fix state to confirm).
- New Playwright e2e test fails against the pre-fix code (404) and passes after — the guard the user asked for.
- `reports.spec.ts` no longer asserts any non-existent path; dead helpers gone; no remaining callers.
- Full frontend suite (`npm run test`), lint, typecheck, build green; `e2e-sqlite` green. No backend change (backend endpoints already correct).

## Related
Root-caused during this session; endpoint inventory from the reporting-subsystem Explore pass. Memory: [[login-cold-start-ux]] (Render demo probe method), [[verify-rigorously-not-sample]] (running-app verification + genuine red→green), [[frontend-script-setup-testing]] (composable unit-test pattern — test the composable, not the component internals).
