# Run 8 Audit — KPI Operations Platform (Opus 4.8)

**Date:** 2026-06-19
**Auditor:** Claude (Opus 4.8), audit-and-harden skill, 5 parallel read-only domain agents + independent re-verification of every Critical/High by direct read.
**Baseline:** Run 7 (Fable5) graded **A**; PR4 robustness slate (B, C1, C1b, C2, C3, C4) shipped; main-branch CI green.
**Scope:** Whole repo, analysis only — **no code changed**.

---

## Remediation status (this PR)

Stage 2 scope chosen by the maintainer: **gate integrity + quick wins**. Shipped in the accompanying branch (`harden/run8-gate-integrity`), each validated:
- **C-1** — 18 permissive status asserts tightened to single codes (15→403, 3→401); 224 affected tests pass.
- **C-2** — 5 tautological e2e assertions replaced with real contracts / honest `test.skip`; `check-skipped-tests.sh` extended with a tautology guard.
- **H-1** — MiniZinc CLI installed in CI `backend-tests` (solver suite validated locally: 195 passed).
- **H-2** — docker-build smoke now fails on any non-2xx (validated locally: all 10 endpoints 200).
- **H-3** — prod healthcheck → `/health/live`.
- **H-5** — auth fixtures `pytest.fail` instead of `skip`.
- **Quick wins** — demo creds, `main.py` version 1.1.0, python-jose→pyjwt doc, 5 stray `.bak` removed.

**Deferred (maintainer decision / follow-up):** M-1 (QR IDOR), M-2 (upload cap), H-4 (threadpool reports), M-3/M-4/M-5/M-7 (route refactors, pagination, store actions), L-tier, and C5 (schema mechanism, MariaDB go-live). The `operator1`-vs-`operator2` seeder divergence (two demo seeders with different user sets — `create_demo_users.py` vs `demo_seeder.py`) surfaced during the creds fix and is worth reconciling separately.

---

## Executive Summary

**Grade: B+** (the *codebase* is A-grade; the *test/gate-integrity layer* is B+, and on this team's honest-gates bar that governs the headline).

The application's security, architecture, and dependency posture remain genuinely strong — Run 7's A holds there. No Criticals in the classic sense (no RCE, no auth bypass, no secret leak, no SQL injection — all independently re-verified clean). What pulls the grade down is a cluster of **gate-integrity and test-honesty regressions**: tests that *cannot fail*, RBAC-denial tests that pass on a 500 crash, a CI smoke step that swallows every endpoint failure, and the core MiniZinc solver suite that never runs in any required check. For a team whose explicit bar is "honest gates / verify rigorously, not sample," these matter more than their raw count — they mean the green checkmark currently overstates real coverage.

The good news: nearly every finding is small and mechanical to fix. None require architectural change.

### Top risks
1. **Test-gate honesty** — 15 permissive `(403, 500)` asserts (explicitly forbidden by CLAUDE.md, the exact Phase B.2 pattern) + 5 tautological e2e assertions (`|| true`, `expect(true)`) including the auth-gate redirect test.
2. **CI coverage theatre** — 50 MiniZinc solver tests skip in CI (minizinc only in Dockerfile); docker-build smoke step `|| echo "WARN"` exits 0 on any broken endpoint.
3. **Prod compose is dead-on-arrival** — `docker-compose.prod.yml` healthcheck curls auth-gated `/health/ready` → permanent `unhealthy` → frontend never starts. (Render deploy path is unaffected; uses `/health/live`.)

### Top opportunities
- Restore the gates' teeth (1–2 line fixes each) so the A-grade code is backed by A-grade verification.
- Close the QR employee cross-tenant IDOR and add an upload-size cap — the only two real security Mediums.
- Doc/version drift cleanup (stale demo creds, `main.py` 1.0.0 vs 1.1.0, python-jose reference) — cheap honesty wins.

---

## Repo Map

- **Stack:** FastAPI 0.136 + SQLAlchemy 2.0 + PyJWT (HS256) backend; Vue 3.5 + Vuetify 4.1 + AG Grid (Community) + Pinia + vue-i18n frontend. PyMySQL/MariaDB target, SQLite for tests/e2e.
- **Scale:** ~86k LOC backend (609 py files, 180 test files); 373 TS/Vue files (94 unit specs, 16 Playwright e2e).
- **Entry/bootstrap:** `backend/main.py` (64 lines) → `backend/bootstrap/` (lifecycle, openapi, app_config, routers). ~45 route modules + consolidated `endpoints/csv_upload.py`.
- **CI:** `.github/workflows/ci.yml` + `e2e.yml`; 4 required checks (`backend-tests`, `frontend-lint-and-tests`, `docker-build`, `e2e-sqlite`); pre-commit (black/flake8/mypy/bandit/detect-secrets/eslint/vue-tsc); hash-pinned hermetic lockfiles; pip-audit + detect-secrets blocking.
- **Maturity:** Very high. 7 prior audit runs, honest coverage gate (81.88% / threshold 75), strict mypy, branch protection.

---

## Audit Report — Findings by Severity

> Severity reflects this repo's maturity bar. "Critical" here = violates an explicit project invariant or makes a required gate lie, not necessarily exploitable security.

### CRITICAL (gate / test integrity)

**C-1 — Permissive `(403, 500)` assertions reintroduced (FACT).**
15 occurrences of `assert response.status_code in (403, 500)` on RBAC-denial paths. The guard (`backend/auth/jwt.py:248`) raises a clean 403; the only correct code is 403. The `, 500` clause means a forbidden action that *crashes* the endpoint passes the test. This is precisely the pattern Phase B.2 removed (778 of them) and CLAUDE.md forbids at review.
Locations: `test_routes/test_equipment_routes.py:264,425,471`; `test_production_line_routes.py:247,454,463,471`; `test_production_line_bridge_routes.py:184,221,288`; `test_employee_line_assignment_routes.py:359,606,613,617`; `test_shift_routes.py:203`. Weaker `(401,403)` cousins: `test_health_routes.py:602,607`, `test_health_comprehensive.py:245`.

**C-2 — Tautological e2e assertions that can never fail (FACT).**
`frontend/e2e/auth.spec.ts:101` — the protected-route-redirect (auth-gate) test ends `(... || true).toBeTruthy()`. Also `auth.spec.ts:540` (`|| true`), and bare `expect(true).toBeTruthy()` at `auth.spec.ts:221,568` and `capacity-kpi-tracking.spec.ts:52`. The auth-gate test is the one that's supposed to prove unauthenticated users can't reach protected routes — it currently proves nothing. Note: `scripts/check-skipped-tests.sh` guards *skips* but not these tautologies — a gap in the gate itself.

### HIGH (gate integrity / availability)

**H-1 — MiniZinc solver suite (~50 tests) skips in every required check (FACT).**
`minizinc` is installed only in the `Dockerfile` (lines 31,36), not in `ci.yml` `backend-tests` or `e2e`. The `simulation_v2` operator-allocation / sequencing / bottleneck-rebalancing / planning-horizon tests — the core optimization logic — are unverified in CI. They pass locally/in Docker only.

**H-2 — docker-build smoke step swallows all endpoint failures (FACT).**
`ci.yml:222-231` pipes every endpoint check to `|| echo "WARN: ..."`, so the step exits 0 and prints "All workflow endpoints passed" regardless. Only the upstream token fetch can fail it. A broken work-orders/KPI/quality endpoint ships green. (The file even carries a comment at :101 acknowledging the `|| echo` can-never-fail shape.)

**H-3 — Prod compose healthcheck targets an auth-gated endpoint (FACT).**
`docker-compose.prod.yml:37` curls `/health/ready`, which requires `get_current_user` (`routes/health.py:252-256`) → 401 → container is permanently `unhealthy`; `frontend depends_on: condition: service_healthy` → frontend never starts. Dev compose, Dockerfile, and Render all correctly use the unauthenticated `/health/live` (`health.py:273`). One-line fix: point prod at `/health/live`.

**H-4 — Synchronous report generation blocks the event loop (FACT).**
`routes/reports/kpi_reports.py:65,111,168,214` and `reports/comprehensive_reports.py:60` call `PDFReportGenerator(db).generate_report(...)` / `ExcelReportGenerator(...)` synchronously inside `async def`. CPU + blocking-DB work runs on the event loop; on the single-worker uvicorn deployment (`Dockerfile:80`) one report request stalls the entire API until it finishes. Offload via `run_in_threadpool` or make the handlers non-async (`def`).

**H-5 — Auth fixtures `pytest.skip()` on login failure (FACT/JUDGMENT).**
`backend/tests/conftest.py:484,528` skip dependent tests when login fails. An auth regression would mass-*skip* (green) rather than fail the suite.

### MEDIUM

**M-1 — QR employee lookup cross-tenant IDOR (FACT).** `routes/qr.py:138-148` — the EMPLOYEE branch is the only one of four that omits `verify_client_access(...)` (WORK_ORDER:116, PRODUCT:127, JOB:135 all have it). Employee is tenant-scoped (`orm/employee.py:30`), and `_entity_to_dict` (`qr.py:31-49`) dumps the full ORM row (PII). Any authenticated user can read any employee across tenants.

**M-2 — No upload-size limit on 11 CSV/XLSX endpoints (FACT).** `endpoints/csv_upload.py` (lines 115,188,266,317,412,466,545,623,680,737,788) all `await file.read()` with no size guard. `Settings.MAX_UPLOAD_SIZE` (`config.py:93`) is defined but referenced nowhere — dead config. Authenticated memory-exhaustion DoS.

**M-3 — Fat route handlers with inlined business logic + duplicated query/serialize (FACT).** Root cause of the route→ORM coupling below. `work_orders.py:138-284` (`get_work_order_progress`, ~147 lines, 3 near-identical ORM→dict blocks), `predictions.py:113-246` (forecasting builder in a route module), `floating_pool.py:236-363`, `simulation_v2.py` handlers (100-128 lines each), `qr.py:89-180`. The `services/` layer exists and is used elsewhere — these are inconsistent holdouts.

**M-4 — DB commit without rollback handling (FACT, downgraded from High).** Many route handlers commit with no try/except rollback (`work_orders.py` 7 commits / 0 rollbacks; similar in `holds.py`, `simulation_scenarios.py`, `workflow.py`, `alerts/*`, `users.py`). `get_db` (`database.py:85-94`) is `try: yield / finally: db.close()` with **no explicit rollback** — SQLAlchemy discards the uncommitted txn on close, so per-request blast radius is limited, but a failed `commit()` leaves the session broken for any code that catches and continues. Inconsistent with `production.py`/`capacity/analysis.py` which handle rollback.

**M-5 — Unbounded list queries + N+1 (FACT).** No LIMIT/pagination on `holds.py:321`, `capacity/kpi_workbook.py:139-174` (6×), `alerts/config_history.py:50`, `alerts/generate.py:62,126,204,295`, `reference.py:32,51,71`; N+1 loop in `alerts/generate.py:204-250`.

**M-6 — Doc/version drift (FACT).** `backend/main.py:27,47` declares `1.0.0` (everything else — Dockerfile/package.json/README/CHANGELOG — says `1.1.0`; live `/docs` shows the wrong version). README ~130-137 + QUICKSTART ~160-167 list stale demo creds `supervisor1`/`operator1` vs actual `supervisor`/`operator`/`operator2` (`database/create_demo_users.py`) → new users fail login. `docs/architecture/README.md:50` still lists removed `python-jose`. README has contradictory metrics (endpoints 393 vs 456; tests 5,771 vs 6,906).

**M-7 — Frontend store-state mutation bypassing actions (FACT).** `SimulationV2View.vue` (2044 lines, 3× next-largest) writes `store.operations = …` / `store.demands = …` / `store.error = …` directly (lines 314,1782-1787,1932). `services/api/kpi.ts:155,203` swallow per-request errors with `.catch(() => ({data:{}}))` inside `Promise.all` → backend failure renders as zeros with no error surfaced.

**M-8 — 356 status-code-only route/api asserts (heuristic, JUDGMENT).** Assert the status code but never the response body — weak verification, though far less severe than C-1.

**M-9 — `db/migrations/` excluded from strict mypy (FACT).** `pyproject.toml` mypy `exclude` skips `db/migrations/` (incl. 2003-line `demo_seeder.py`); the `_archive/` exclude entry is stale (dir doesn't exist).

### LOW

- **L-1** Unsanitized `v-html` of `marked.parse()` output (`HelpCenter.vue:57`); DOMPurify not in the project. Safe today (build-time bundled in-repo docs) but the exact XSS→localStorage-token vector if any doc ever comes from the API.
- **L-2** Insecure-secret hard-fail gate keys on `ENVIRONMENT` which defaults to `development` (`config.py:56,70,299-300`) — forgetting `ENVIRONMENT=production` runs with default `SECRET_KEY` (warning only, fail-open).
- **L-3** Rate limiter is in-process `memory://` (`middleware/rate_limit.py:48`) → per-worker not global; `DISABLE_RATE_LIMIT` env (`:24,51`) fully disables, not tied to non-prod.
- **L-4** Unstructured logging; `LOG_LEVEL` ignored (`utils/logging_utils.py:39` hardcodes INFO despite `config.py:84`); no request-id correlation.
- **L-5** Single uvicorn worker, no gunicorn (`Dockerfile:80`); `main.py:62` comment falsely claims gunicorn. Compounds H-4.
- **L-6** 5 orphaned `.bak` files on disk (`routes/auth.py.bak`, `crud/{attendance,coverage,downtime,quality}.py.bak`) — gitignored/untracked, don't ship, but pollute grep.
- **L-7** ~61 icon-only `<v-btn icon>` without `aria-label` (`frontend/`); 64 `.catch(() => false)` soft-branches degrade some e2e tests to no-ops; unfrozen `datetime.now()` in tests (no freezegun).
- **L-8** `useHoldGridForms.ts:344` raw `fetch()` bypasses the axios token-injection + 401→logout interceptor; `filtersStore.ts:143-147`/`dualViewStore.ts:57` hydrate reactive state from unvalidated `JSON.parse(...) as T`.
- **L-9** Latent: `/api/auth/reset-password` (`routes/auth.py:255-285`) trusts any `type=password_reset` JWT, no single-use/blacklist; dead today (no issuer) — risk only if a reset-token issuer is added.

---

## Strengths (verified, not assumed)

- **Security core is clean:** SQL injection (only constant `text()` + metadata-keyed count queries), command injection / pickle / yaml.load / SSRF (zero hits), path traversal (export/QR are in-memory streams), JWT (single-algorithm HS256, jti DB revocation, exp set, sanitized errors), argon2id hashing with rehash migration, uniform authz guards ≥ mutations across all route files, CORS localhost-default + wildcard blocked in prod, `SECRET_KEY` fail-fast via `:?`.
- **Architecture:** correct dependency direction, no circular imports; services/crud/orm never import routes; consolidated `csv_upload.py` is clean; 0 bare `except:`, 0 TODO/FIXME markers in app code; strict mypy genuinely enforced (only 9 documented `# type: ignore`).
- **Frontend:** 0 `any`, 0 `@ts-ignore`, 1 false-positive `as any` (refutes the CLAUDE.md ColDef cascade worry); no eval/new Function; all 162 `v-for` keyed; route-level code splitting; ExcelJS out of main bundle.
- **Deps/Ops:** every security pin carries an inline CVE/GHSA rationale; non-root multi-stage Docker, hash-pinned hermetic install, `@sha256`-pinned bases, prod resource limits; pip-audit + detect-secrets blocking; all frontend majors current.
- **Testing (where it's good):** single pytest config with re-armed deprecation-as-error guards; coverage gate honestly wired (`fail_under=75`); dense 1:1 calculation-module coverage; no bracket-form `status_code in [..]` survivors; real e2e flows for auth/capacity/work-orders.

---

## Improvement Strategy

**Theme 1 — Restore gate honesty (highest leverage, lowest effort).** C-1, C-2, H-1, H-2, H-5. These are the findings that make the A-grade code look better-verified than it is. Mostly 1–2 line fixes + one CI dependency install. *Done signal:* every required check actually exercises what it claims; `git stash` the C-1/C-2 fixes and confirm the tests now fail; minizinc tests run in CI; smoke step fails on a broken endpoint.
  - *Trade-off:* fixing H-1 adds minizinc install time to CI (~30-60s). Worth it; the alternative is shipping untested solver logic.

**Theme 2 — Close the two real security Mediums.** M-1 (QR employee `verify_client_access`), M-2 (upload-size cap wiring `MAX_UPLOAD_SIZE`). *Done signal:* a cross-tenant employee QR lookup returns 403 (new test); an oversized upload returns 413 (new test).

**Theme 3 — Availability + correctness Mediums.** H-4 (threadpool reports), M-5 (pagination/eager-load), M-7 (store actions + surfaced errors). *Done signal:* report endpoints don't block concurrent requests (measurable); list endpoints bounded.

**Theme 4 — Honesty/doc drift (cheap).** M-6 (version, demo creds, python-jose, README metrics), L-6 (.bak cleanup), M-9 (mypy exclude). *Done signal:* `/docs` shows 1.1.0; README creds match `create_demo_users.py`.

**Explicitly deferred (do not fix now):** C5 schema-evolution mechanism (create_all vs alembic vs db/migrations) — accurately described, top deploy risk, settled at MariaDB go-live per existing decision. L-9 reset-token hardening — dead code, fix when an issuer is added.

---

## Task Plan

**Quick wins (each <1hr, independent):**
1. H-3 — prod healthcheck `/health/ready` → `/health/live` (1 line).
2. M-6 — `main.py` version `1.0.0` → `1.1.0`; fix README/QUICKSTART demo creds; drop python-jose from docs.
3. L-6 — delete 5 `.bak` files.
4. H-2 — remove `|| echo "WARN"` from `ci.yml:222-231` smoke step (or convert to an aggregate-fail).

**Milestone A — Gate integrity:** C-1 (replace 15 `(403,500)` with single `== 403`), C-2 (replace 5 tautologies with real assertions + extend `check-skipped-tests.sh` to catch `|| true`/`expect(true)`), H-1 (install minizinc in CI `backend-tests`), H-5 (fail instead of skip on fixture login failure).

**Milestone B — Security Mediums:** M-1 (QR employee `verify_client_access` + test), M-2 (enforce `MAX_UPLOAD_SIZE` → 413 + test).

**Milestone C — Availability/quality:** H-4 (threadpool reports), M-5 (pagination), M-7 (Pinia actions + error surfacing), M-3/M-4 (extract fat handlers to services, add rollback or centralize in `get_db`).

**Milestone D — Hygiene:** M-9 (mypy exclude), L-1 (DOMPurify), L-2/L-3/L-4 (config/rate-limit/logging hardening).

---

## Open Questions for the Human

1. **Scope of Stage 2:** restore gate integrity only (Milestone A + quick wins), or the full slate through Milestone D?
2. **Report location:** I followed the project convention (`_audit/RUN-8-OPUS-AUDIT.md`, local-only/gitignored). The skill's default is `docs/audit/` (committed). Keep local, or also commit a copy?
3. **H-3 prod compose:** is `docker-compose.prod.yml` actually used anywhere, or is Render the only prod path? (Affects severity — High if used, Low if vestigial.)
4. **M-3/M-4 fat-handler refactor:** in-scope now, or logged as a follow-up? It's the largest-effort theme and borders on "refactor" vs "harden."
