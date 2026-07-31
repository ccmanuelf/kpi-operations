# E2E Sweep Remediation — Design

**Date:** 2026-07-30 · **Status:** Approved by user ("fix until 100/100, no tech debt, even pre-existing")
**Evidence base:** `.gstack/qa-reports/qa-report-vm-kpi-operations-2026-07-30.md` (health 55/100, 20 issues + observations, all with live evidence from VM prod @ `38721b6`) + targeted API probes.
**Goal:** every issue and observation from the sweep fixed and live-validated on the VM; seed data refreshed to current date; sweep re-run confirms no findings remain.

## Ground rules

- No deferrals: every ISSUE-001…020 and every listed observation gets fixed in this slate.
- Root-cause fixes, not symptom patches (e.g. proxy-scheme config, not just one trailing slash).
- Class scoping per the #145 lesson: when a bug is an instance of a class, enumerate and fix the whole class.
- Validation = the original failing evidence re-checked live on the VM after deploy (plus Render where applicable).

## Fix matrix

### G1 — Backend correctness

| Issue | Root cause (verified) | Fix |
|---|---|---|
| 001 OEE trend 500 (Critical) | `oee = (availability/100)*(performance/100)*(quality/100)*100` mixes float and Decimal; MariaDB feeds Decimal where SQLite feeds float (traceback captured from kpi-backend logs) | Normalize inputs at the boundary: coerce all three operands via `Decimal(str(x))` (or float consistently) in the OEE trend path; **class sweep**: grep `backend/calculations/` + `backend/routes/kpi/` for arithmetic mixing DB-sourced values with float literals and normalize each site; regression test with `Decimal` inputs |
| 012 https→http 307 downgrade (Critical) | uvicorn/gunicorn builds redirect Location from internal scope; forwarded proto not honored behind Caddy (`location: http://…` captured) | Infra root fix: enable proxy-header trust in the backend server config used by the VM compose stack (`--proxy-headers` / `FORWARDED_ALLOW_IPS` for gunicorn+uvicorn workers) so scheme propagates; verify Caddy sends `X-Forwarded-Proto` (it does by default). Belt-and-braces: align the quality store's call to the canonical trailing-slash path. **Class sweep**: audit every frontend API path against backend route slash expectations; align all slash-less callers |
| 002/013 `client_id` 422 class (High) | `/api/production-lines/`, `/api/shifts` (+ shared `fetchReferenceData`) hard-require `client_id`; admin-tier users send none (422 bodies captured) | Make `client_id` optional using the established `resolve_client_scope` dependency (uniform client-scope authz pattern already used on ~40 endpoints): admin/poweruser default to all-clients, scoped roles to their scope. Entry screens and filters then work for every role. Tests: per-role permission cases |
| 011 Decimal-as-string on entity/KPI endpoints (Medium) | Entity list serializers (production entries, wip-aging response `average_aging_days: "74.7"`, OTD trend per memory) never got the #145 JSON-number treatment | **Class sweep** per #145 lesson: enumerate every response schema field backed by a `Numeric` column across entity + KPI endpoints; apply the same JSON-number serialization; guard test asserting no quoted numerics in sampled responses (SQLite CI can't catch it — write the guard against schema config, and validate live on MariaDB) |
| 008 Alerts summary vs list (High) | Summary computes breaches on the fly; list reads a persisted alerts store that is empty (unfiltered list `[]` vs summary 9) | Single source of truth: make the list derive from the same breach computation as the summary (or persist computed breaches at check time — pick whichever the existing "Check Now" flow half-implements; investigate then unify). Counts and list must never disagree; test asserts summary total == unfiltered list length |
| 020 Admin DB config 401s (High) | Providers/status calls rejected while admin session valid — either the frontend store bypasses the authed axios instance or the routes use a stricter/different dependency; investigate first | Fix whichever side is wrong so an admin session loads the screen; add a route-level test for admin access |

### G2 — Frontend wiring & UX

| Issue | Fix |
|---|---|
| 016 WorkOrders client filter → dead `/api/v1/admin/clients` | Point to the live `/api/clients`; remove the stale versioned path everywhere (grep for `/api/v1/`) |
| 019 VarianceReport 404 | Point the store to `/api/assumptions/variance` (curl-verified 200) |
| 003 WIP card 0.0days | Fix frontend field mapping to consume `average_aging_days` (works once G1-011 emits numbers; add explicit mapping test); card badge semantics must follow lower-is-better correctly |
| 004 OTD control chart ±200 axis | Clamp control limits to the metric's valid domain [0,100] before charting |
| 005 Chart.js Filler warnings | Register the `Filler` plugin where charts use `fill:` |
| 006 Register button on prod | Gate the button on demo-mode: use the existing config surface (entrypoint-injected meta / config endpoint — follow the backend-wake-origin pattern) so non-demo deployments hide it |
| 014 Grid header clipping | Set sensible `minWidth`/ellipsis (`headerClass` or suppress cut-off) via the central `useAGGridBase` so ALL grids inherit the fix |
| 015 Unknown routes blank | Add a catch-all 404 route with a proper not-found view |
| 017 Capacity OTD 0.00% | Investigate the screen's own OTD computation ("textbook values" strip); wire it to the real OTD source (`/api/kpi/otd` returns 30.43%) or compute correctly from workbook data |
| Obs: Settings threshold fields blank | Investigate load path; saved/global thresholds must display |
| Obs: ES date formatting | Localize grid/date renderers via the active i18n locale |
| Obs: Quality y-axis over-zoom | Pad the y-domain so management-readable |
| Obs: PvA completion bar text overlap | Fix the 50.0% red-bar label collision |

### G3 — MyShift honesty (Issue 007, High)

Remove the fabricated mock fallback (WO-2024-*, fake activity timestamps, hardcoded Today's Summary). Wire to real data for the logged-in user's assignments; when the user has no line/shift mapping (verify_bot case), render an honest empty state ("No work orders assigned to your shift"). The screen must never invent records. Status rings and quick-action tiles either bind to real data or collapse into the empty state.

### G4 — Help content (Issue 018, High)

Ship `docs/user-guide/` content in the frontend image (build-stage copy) so `/docs/user-guide/index.json` serves real JSON on the VM; make the HelpCenter loader fail loudly when it receives HTML instead of JSON (SPA-fallback detection) instead of silently rendering "No matches found". Verify Render still works.

### G5 — Seed/demo data refresh (user-mandated)

- Re-seed so the data window ends **today** (relative dates — the seeder's window must roll with the seed date, not pin to July 17): "Today's Summary" non-zero (Issue 009).
- Diversify `performance_percentage` vs `efficiency_percentage` (small realistic deltas; Issue 010).
- Fix SHIPPED work orders with `actual_quantity=0`/0% progress (observation).
- Populate client contact fields (observation).
- Keep all existing credibility properties from #143 (OTD OOC dips, chronic holds, guaranteed cause-demo shapes).
- Apply on the VM via the prod-safe `seed_sample_client --reset` re-seed; verify dashboard leads non-zero.

### G6 — CSP inline theme script (observation)

Whitelist the theme-restore snippet via its sha256 hash in the CSP header (nginx/Caddy config or index.html CSP meta — wherever `script-src 'self'` is set), or move the snippet to a tiny external file. Console must be clean of CSP errors on every navigation; pre-hydration dark restore must work.

## Delivery

One branch `fix/e2e-sweep-remediation`, subagent-driven execution with per-task reviews, whole-branch final review, /cross-review, ONE PR, 4-check CI green, merge, deploy Render + VM (incl. compose/env changes and re-seed), then **validation sweep**: re-check every issue's original failing evidence live on the VM; the engagement closes only when every check passes (target 100/100 on the same rubric — remaining deductions must be zero).

## Out of scope (explicitly)

Nothing from the sweep. (The downtime cause taxonomy and other *capability* gaps remain in the reporting deferred-spec queue — they are product features, not sweep defects; the sweep observation about empty attribution columns is data/feature, not a bug, and is queued in the reporting plan.)
