# B.1 — Permissive-Assertion Inventory (Categorized)

**Captured:** 2026-05-07 from `_audit/B1-permissive-inventory-raw.txt`

**Total assertions:** 778  
**Files affected:** 28  
**Distinct patterns:** 52

## Summary by category

| Category | Count | Files | Definition |
|---|---:|---:|---|
| Anti-pattern | 434 | 17 | 4+ codes in the list — test asserts nothing useful |
| Suspicious | 332 | 20 | 2-3 codes mixing success + error — likely masking fixture issues |
| Acceptable | 12 | 6 | known equivalent codes (e.g. `[200, 201]` for create idempotency) |

## Per-file totals (sorted by count)

| File | Total | Anti | Susp | OK |
|---|---:|---:|---:|---:|
| `backend/tests/test_api/test_main_endpoints.py` | 90 | 0 | 89 | 1 |
| `backend/tests/test_routes/test_low_coverage_routes.py` | 80 | 80 | 0 | 0 |
| `backend/tests/test_routes/test_additional_coverage.py` | 69 | 69 | 0 | 0 |
| `backend/tests/test_routes/test_routes_extended.py` | 67 | 22 | 40 | 5 |
| `backend/tests/test_routes/test_all_routes_comprehensive.py` | 58 | 20 | 38 | 0 |
| `backend/tests/test_routes/test_final_coverage.py` | 51 | 51 | 0 | 0 |
| `backend/tests/test_api/test_integration_comprehensive.py` | 51 | 25 | 26 | 0 |
| `backend/tests/test_api/test_predictions_routes.py` | 45 | 28 | 17 | 0 |
| `backend/tests/test_routes/test_kpi_extended.py` | 42 | 42 | 0 | 0 |
| `backend/tests/test_routes/test_kpi_routes_comprehensive.py` | 37 | 36 | 1 | 0 |
| `backend/tests/test_routes/test_analytics_routes.py` | 34 | 8 | 26 | 0 |
| `backend/tests/test_api/test_predictions_comprehensive.py` | 30 | 15 | 15 | 0 |
| `backend/tests/test_routes/test_qr_comprehensive.py` | 24 | 21 | 3 | 0 |
| `backend/tests/test_api/test_routes_comprehensive.py` | 24 | 1 | 22 | 1 |
| `backend/tests/test_api/test_analytics_comprehensive.py` | 21 | 4 | 17 | 0 |
| `backend/tests/test_api/test_all_endpoints.py` | 14 | 0 | 14 | 0 |
| `backend/tests/test_api/test_health_comprehensive.py` | 13 | 0 | 13 | 0 |
| `backend/tests/test_routes/test_capacity_routes_advanced.py` | 10 | 10 | 0 | 0 |
| `backend/tests/test_routes/test_kpi_routes_real.py` | 7 | 0 | 5 | 2 |
| `backend/tests/conftest.py` | 2 | 0 | 0 | 2 |
| `backend/tests/test_security/test_rate_limiting.py` | 2 | 1 | 1 | 0 |
| `backend/tests/test_edge_cases/test_auth_edge_cases.py` | 1 | 0 | 1 | 0 |
| `backend/tests/test_routes/test_production_routes_comprehensive.py` | 1 | 0 | 1 | 0 |
| `backend/tests/test_routes/test_reports_routes_real.py` | 1 | 0 | 1 | 0 |
| `backend/tests/test_api/test_comprehensive_api.py` | 1 | 0 | 1 | 0 |
| `backend/tests/test_api/test_reports.py` | 1 | 1 | 0 | 0 |
| `backend/tests/test_api/test_health_routes.py` | 1 | 0 | 1 | 0 |
| `backend/tests/test_db_routes/test_database_config.py` | 1 | 0 | 0 | 1 |

## Pattern frequency (top 25)

| Pattern | Count | Category |
|---|---:|---|
| `[200, 403, 404, 422]` | 229 | anti-pattern |
| `[200, 403]` | 114 | suspicious |
| `[200, 403, 404]` | 110 | suspicious |
| `[200, 400, 403, 404]` | 37 | anti-pattern |
| `[200, 201, 400, 403, 422]` | 34 | anti-pattern |
| `[200, 403, 404, 422, 500]` | 27 | anti-pattern |
| `[200, 400, 403, 404, 422]` | 25 | anti-pattern |
| `[403, 404]` | 24 | suspicious |
| `[200, 404, 422]` | 21 | suspicious |
| `[200, 403, 404, 500]` | 20 | anti-pattern |
| `[200, 204, 403, 404]` | 10 | anti-pattern |
| `[200, 400, 500, 501]` | 10 | anti-pattern |
| `[200, 403, 404, 405, 422]` | 9 | anti-pattern |
| `[200, 400, 404, 422]` | 9 | anti-pattern |
| `[200, 201, 403, 404, 422]` | 8 | anti-pattern |
| `[200, 403, 500]` | 8 | suspicious |
| `[200, 404]` | 7 | acceptable |
| `[200, 201]` | 5 | acceptable |
| `[200, 400, 403, 404, 405, 422]` | 5 | anti-pattern |
| `[403, 422]` | 5 | suspicious |
| `[400, 403, 404]` | 4 | suspicious |
| `[403, 404, 422]` | 4 | suspicious |
| `[200, 500]` | 4 | suspicious |
| `[200, 404, 500]` | 4 | suspicious |
| `[401, 404]` | 4 | suspicious |

## Categorization rationale

**Anti-pattern (4+ codes)** — `[200, 403, 404, 422]` is the dominant pattern (229 hits).
It says "this endpoint either succeeded, the user was forbidden, the resource was missing,
or the request was malformed." That covers nearly every reasonable outcome — the assertion
can only fail if the route is unreachable (5xx) or returns an unexpected code (e.g. 401).
The test loses its ability to catch the contract violations it was supposed to catch.

**Suspicious (2-3 codes, mixed success/error)** — `[200, 403]` (114 hits) and `[200, 403, 404]`
(110 hits) lead this category. These typically come from tests that were written without
knowing whether the test fixture user has access to the resource — the test passes either
if the request is allowed (200) or denied (403). The fix is to set up a fixture user with
known access (matches one specific outcome) and assert that outcome.

**Acceptable (known-equivalent codes)** — `[200, 201]` (5 hits) for create endpoints that
can either insert or upsert; `[200, 404]` (7 hits) for soft-delete idempotency. These are
legitimate and don't need tightening.

## B.2 work breakdown

- **Phase 1 (anti-pattern, 434 hits)**: highest priority. Replace each with the single
  expected status code based on the test's user role + input. If the strict assertion
  fails, that's a real route bug to fix.
- **Phase 2 (suspicious, 332 hits)**: tighten the fixture user's permissions so the
  outcome is deterministic, then assert the specific code.
- **Phase 3 (acceptable, 12 hits)**: add a comment explaining why the equivalence is
  acceptable (e.g. `# Idempotent: 200 if exists, 201 if created`).

**Estimated effort**: ~4-6 hours for the anti-pattern category, ~3-4 hours for suspicious,
~30 min for acceptable. Real bugs uncovered during tightening get fixed at root.
