# KPI Decimal→JSON-number Serialization Fix (Design)

**Date:** 2026-07-16
**Status:** Approved design → ready for implementation plan
**Context:** Found during the seed-credibility-polish (#143) live verification: the OTD trend endpoint returns each point's `value` as a JSON **string** (`"0.00"`) on MariaDB, not a number. A route-surface scan showed the same defect in 4 sibling KPI numeric fields.

## The bug

On MariaDB, a SQL aggregate over integer columns (`func.sum(...)`, `func.sum(case(...))`) is returned to Python as a `Decimal`. Dividing that `Decimal` and calling `round(Decimal, n)` yields a `Decimal`, which FastAPI/Pydantic serialize as a **string** (`"0.00"`). On SQLite the same aggregate comes back as `int`, so `int / int` is a Python `float` and serializes as a **number** — hence the inconsistency is **MariaDB-only**. The sibling trend endpoints avoid it by `float()`-casting in Python before the division.

The frontend `unwrapTrend()` coerces via `Number()`, so charts render correctly either way — this is a **correctness/consistency cleanup**, not a UI-visible bug.

## Scope — the whole class (5 sites)

Fix every KPI numeric field that divides a raw SQL-aggregate `Decimal` without a `float()` cast (leaving some emitting strings would repeat the half-fix pattern):

| File:line | Endpoint | Field |
|---|---|---|
| `backend/routes/kpi/trends.py:222` | `get_quality_trend` (`/api/kpi/quality/trend`) | `value` = `(r.passed / r.inspected) * 100` |
| `backend/routes/kpi/trends.py:394` | `get_otd_trend` (`/api/kpi/on-time-delivery/trend`) | `value` = `(r.on_time / r.total * 100)` |
| `backend/routes/kpi/trends.py:434` | `get_absenteeism_trend` (`/api/kpi/absenteeism/trend`) | `value` = `(r.absent / r.scheduled * 100)` |
| `backend/routes/kpi/otd.py:175` | `get_otd_by_client` (`/api/kpi/otd/by-client`) | `otd_percentage` = `(r.on_time / r.total_deliveries * 100)` |
| `backend/routes/quality/pareto.py:179` | `get_quality_by_product` (`/api/quality/kpi/by-product`) | `fpy` = `(r.passed / r.inspected) * 100` |

**Explicitly out of scope (already correct — do not touch):** throughput/availability/oee/performance/efficiency/ppm trends, dashboard trend points, attendance trend rate, attendance by_reason percentage — these all `float()`-cast (or use Python int division) before rounding.

## The change

At each of the 5 sites, `float()`-cast both operands of the division so the result is a Python `float` before `round(...)`, matching the sibling endpoints' pattern. Preserve the existing zero-guard exactly. Example (OTD trend):

```python
# before
"value": round((r.on_time / r.total * 100) if r.total > 0 else 0, 2)
# after
"value": round((float(r.on_time) / float(r.total) * 100) if r.total > 0 else 0, 2)
```

Casting **both** operands (not just wrapping the whole expression) also removes any latent integer-division ambiguity and reads identically to the already-correct siblings. The `else 0` branch stays an `int` `0` (a valid JSON number), unchanged.

No signature, response-shape, or field-name change. No frontend change. `round(float, n)` returns a Python `float`.

## Testing

- **Unit test per affected endpoint** asserting the returned numeric field is a Python `float` (not `Decimal`/`str`) in the JSON response — e.g. seed one day of data, call the endpoint, `assert isinstance(body[0]["value"], float)`.
- **Honest caveat (stated in the plan):** the defect is **MariaDB-only**; on the SQLite test runner the aggregate is already an `int`/`float`, so these tests **pass before and after** the fix. They therefore serve as a **contract/regression guard** (the field must be a JSON number), not a reproduction of the original bug.
- **Real proof = live verification on the VM (MariaDB)** post-deploy: `curl` each of the 5 endpoints and assert `value`/`otd_percentage`/`fpy` come back as JSON numbers, not `"…"` strings (the `"0.00"` strings were observed live before the fix).
- The `mariadb-portability` CI job and the full backend suite stay green; no OpenAPI change.

## Related Memory

[[seed-sample-client-feature]] (where the OTD Decimal-string was found), [[diagnostic-kpi-charts]] (the trend endpoints), [[holds-julianday-mariadb-bug]] (the MariaDB-vs-SQLite portability class this belongs to), [[verify-rigorously-not-sample]] (live-validate on the real DB).
