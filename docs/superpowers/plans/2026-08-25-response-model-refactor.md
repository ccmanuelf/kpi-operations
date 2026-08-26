# Response-model refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the safety net, then convert `/api/kpi` as a measured pilot, so the Decimal-as-string class is closed by declared types rather than by call-site coercion.

**Architecture:** A capture harness records every route's response key set against a disposable seeded database. A frontend extractor records which fields the UI reads. Routes are then grouped by captured *shape* — not converted one at a time — because shapes repeat heavily (8 trend endpoints share one). A ratchet guard lands early with a shrinking allowlist.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2, pytest, Alembic.

**Spec:** `docs/superpowers/specs/2026-08-25-response-model-refactor-design.md`

## Global Constraints

- Permissive assertions are forbidden. Never `assert x in [...]`. One exact expected value per assertion.
- Every new or changed assertion needs a named single-line source change that breaks it, run, with real pasted output. A guard that only ever passes is treated as absent.
- Files stay under 500 lines.
- Never create or drop schema. Alembic is the single mechanism; this work adds no revisions.
- No `--no-verify`, no `SKIP=`.
- **No endpoint may change what it returns.** Field sets stay identical; only declared types change.
- The golden master compares **key sets, never value types** — changing a type is the goal.
- `/api/metrics/results` and `/api/floating-pool/simulation/insights` return numeric-looking strings deliberately. Their models keep `str`.
- Capture runs against a disposable database, never the VM. 52 of the 164 routes are mutations.
- Backend tests run from `backend/` with `pytest tests/ --no-cov -q`. Full suite is the controller's job, not the implementer's.

---

### Task 1: Capture harness

**Files:**
- Create: `backend/tests/contract/__init__.py`
- Create: `backend/tests/contract/capture.py`
- Test: `backend/tests/contract/test_capture_harness.py`

**Interfaces:**
- Produces: `capture_all(client) -> dict[str, list[str]]`, mapping `"GET /api/kpi/dashboard"` to a sorted list of dotted key paths.
- Consumes: `backend/tests/conftest.py`'s `clone_template_engine`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/contract/test_capture_harness.py
def test_capture_records_nested_keys_not_values():
    """The harness records SHAPE. Two responses differing only in values must
    produce an identical record, or the golden master churns on every reseed."""
    from backend.tests.contract.capture import shape_of

    a = {"total": 5, "nested": {"x": 1.5}, "rows": [{"id": "A", "v": 2}]}
    b = {"total": 9, "nested": {"x": 9.9}, "rows": [{"id": "B", "v": 7}]}

    assert shape_of(a) == shape_of(b)
    assert shape_of(a) == ["nested.x", "rows[].id", "rows[].v", "total"]
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `cd backend && python -m pytest tests/contract/test_capture_harness.py -v --no-cov`
Expected: FAIL, `ModuleNotFoundError: backend.tests.contract.capture`

- [ ] **Step 3: Implement `shape_of`**

```python
# backend/tests/contract/capture.py
"""Records the SHAPE of an API response — its key paths, never its values.

Values change on every reseed; shapes do not. A value-sensitive record would
churn constantly and be ignored within a week.
"""

from typing import Any, List


def shape_of(payload: Any, prefix: str = "") -> List[str]:
    """Sorted dotted key paths. A list contributes `name[]` and recurses into
    its FIRST element only — homogeneous collections are the norm here, and
    walking every row would make the record depend on how much data was seeded.
    """
    keys: List[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            child = shape_of(value, path)
            keys.extend(child if child else [path])
    elif isinstance(payload, list):
        if payload:
            child = shape_of(payload[0], f"{prefix}[]")
            keys.extend(child if child else [f"{prefix}[]"])
    return sorted(set(keys))
```

- [ ] **Step 4: Run, confirm pass**

Run: `cd backend && python -m pytest tests/contract/test_capture_harness.py -v --no-cov`
Expected: PASS

- [ ] **Step 5: Add the route walker**

Append to `capture.py`:

```python
def capture_all(client, routes) -> dict:
    """Exercise every route and record its shape.

    `routes` is a list of (method, path, kwargs) prepared by the caller, which
    owns id resolution — the harness deliberately does not guess ids, because a
    wrong id yields a 404 whose shape is recorded as if it were the real answer.
    """
    captured = {}
    for method, path, kwargs in routes:
        response = client.request(method, path, **kwargs)
        if response.status_code >= 400:
            captured[f"{method} {path}"] = [f"<status:{response.status_code}>"]
            continue
        try:
            captured[f"{method} {path}"] = shape_of(response.json())
        except ValueError:
            captured[f"{method} {path}"] = ["<non-json>"]
    return captured
```

- [ ] **Step 6: Prove a 404 is recorded as a status, not a shape**

```python
def test_an_error_response_is_recorded_as_a_status_not_a_shape():
    """A 404's body has keys too. Recording them as the route's shape would
    freeze `{"detail"}` into the golden master and pass forever after."""
    from backend.tests.contract.capture import capture_all

    class _Stub:
        def request(self, method, path, **kw):
            class R:
                status_code = 404
                def json(self): return {"detail": "Not Found"}
            return R()

    result = capture_all(_Stub(), [("GET", "/api/missing", {})])
    assert result == {"GET /api/missing": ["<status:404>"]}
```

Run: `cd backend && python -m pytest tests/contract/ -v --no-cov`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/tests/contract/
git commit -m "test(contract): shape-capture harness for the response-model refactor"
```

---

### Task 2: Route inventory with id resolution

**Files:**
- Modify: `backend/tests/contract/capture.py`
- Test: `backend/tests/contract/test_route_inventory.py`

**Interfaces:**
- Produces: `loose_routes(app) -> list[tuple[str, str, dict]]` — every loosely-typed `/api` route with a callable request prepared.
- Consumes: `shape_of`, `capture_all` from Task 1.

- [ ] **Step 1: Write the failing test**

```python
def test_every_loose_route_is_inventoried_and_none_is_silently_dropped():
    """164 loose routes, measured 2026-08-25 with the STRUCTURAL predicate. The
    count is pinned so a
    route that stops being enumerated — a decorator change, a router rename —
    fails here instead of quietly leaving the refactor's scope."""
    from backend.main import app
    from backend.tests.contract.capture import loose_routes

    routes = loose_routes(app)

    assert len(routes) == 164
    methods = {m for m, _, _ in routes}
    assert methods == {"GET", "POST", "PUT", "DELETE"}
```

- [ ] **Step 2: Run, confirm it fails**

Run: `cd backend && python -m pytest tests/contract/test_route_inventory.py -v --no-cov`
Expected: FAIL with `ImportError: cannot import name 'loose_routes'`

- [ ] **Step 3: Implement `loose_routes`**

```python
import typing
from fastapi.routing import APIRoute

def is_loose(response_model) -> bool:
    """True when the declared model cannot constrain a Decimal.

    STRUCTURAL, not a string match on the repr. An earlier draft of this plan
    used `str(model).startswith(...)`, which cannot see through a wrapper --
    `typing.List[dict]` tested as TYPED -- and silently dropped four live routes
    from the refactor's scope AND from the ratchet allowlist. Corrected before
    Task 2 shipped; see the spec's section 3 note.
    """
    if response_model is None:
        return True
    if response_model in (typing.Any, dict, list):
        return True
    origin = typing.get_origin(response_model)
    if origin is None:
        return False
    args = [a for a in typing.get_args(response_model) if a is not type(None)]
    if not args:
        return True
    return any(is_loose(a) for a in args)


def loose_routes(app) -> list:
    found = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api"):
            continue
        if not is_loose(route.response_model):
            continue
        for method in sorted(set(route.methods) - {"HEAD", "OPTIONS"}):
            found.append((method, route.path, {}))
    return found
```

- [ ] **Step 4: Run, confirm pass**

Run: `cd backend && python -m pytest tests/contract/test_route_inventory.py -v --no-cov`
Expected: PASS, 164 collected

- [ ] **Step 5: Mutation-prove the count pin**

Temporarily give one loose route a real `response_model` in its router, re-run, and paste the failure (`assert 163 == 164`). Restore, confirm `git diff HEAD` empty.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/contract/
git commit -m "test(contract): pin the 164-route refactor scope"
```

---

### Task 3: The ratchet guard

Landing this BEFORE any conversion, so every later task shrinks a visible number and no new loose route can be added meanwhile.

**Files:**
- Create: `backend/tests/contract/test_no_loose_response_models.py`

- [ ] **Step 1: Write the guard**

```python
def test_no_api_route_has_a_loose_response_model():
    """Ratchet. ALLOWLIST is the work remaining; it must only ever shrink.

    A route absent from both the allowlist and the converted set fails here —
    which is what stops a new loose route being added while this refactor is in
    flight, the failure mode that would make the whole exercise pointless.
    """
    from backend.main import app
    from backend.tests.contract.capture import loose_routes
    from backend.tests.contract.allowlist import ALLOWLIST

    still_loose = {f"{m} {p}" for m, p, _ in loose_routes(app)}
    unexpected = sorted(still_loose - ALLOWLIST)
    assert unexpected == []

    stale = sorted(ALLOWLIST - still_loose)
    assert stale == [], "these are converted — remove them from ALLOWLIST"
```

- [ ] **Step 2: Generate the allowlist**

```bash
cd backend && python -c "
from backend.main import app
from backend.tests.contract.capture import loose_routes
rows = sorted(f'{m} {p}' for m, p, _ in loose_routes(app))
with open('tests/contract/allowlist.py', 'w') as fh:
    fh.write('\"\"\"Routes still awaiting a response model. SHRINKS ONLY.\"\"\"\n\n')
    fh.write('ALLOWLIST = {\n')
    for r in rows:
        fh.write(f'    \"{r}\",\n')
    fh.write('}\n')
print(len(rows), 'routes')
"
```

- [ ] **Step 3: Run, confirm pass**

Run: `cd backend && python -m pytest tests/contract/test_no_loose_response_models.py -v --no-cov`
Expected: PASS

- [ ] **Step 4: Mutation-prove BOTH halves**

(a) Delete one entry from `ALLOWLIST`, re-run, expect failure naming that route in `unexpected`.
(b) Add a fictional entry `"GET /api/nope"`, re-run, expect failure in `stale`.
Restore after each; paste both failures.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/contract/
git commit -m "test(contract): ratchet guard on loose response models"
```

---

### Task 4: Frontend field extractor

**Files:**
- Create: `backend/tests/contract/frontend_usage.py`
- Test: `backend/tests/contract/test_frontend_usage.py`

**Interfaces:**
- Produces: `fields_read_by_frontend() -> dict[str, set[str]]`, endpoint path → field names the UI references.

- [ ] **Step 1: Write the failing test**

```python
def test_extractor_finds_a_known_field_the_ui_reads():
    """kpi.ts maps by_reason off the absenteeism response. If the extractor
    cannot see a field this obvious, it will not protect the subtle ones."""
    from backend.tests.contract.frontend_usage import fields_read_by_frontend

    usage = fields_read_by_frontend()

    assert "by_reason" in usage["/api/attendance/kpi/absenteeism"]
```

- [ ] **Step 2: Run, confirm it fails**

Run: `cd backend && python -m pytest tests/contract/test_frontend_usage.py -v --no-cov`
Expected: FAIL, module missing

- [ ] **Step 3: Implement the extractor**

```python
# backend/tests/contract/frontend_usage.py
import pathlib
import re

FRONTEND = pathlib.Path(__file__).resolve().parents[3] / "frontend" / "src"

# api.get('/kpi/dashboard') and friends. The leading /api comes from the axios
# baseURL, so endpoint literals in the client are written without it.
_ENDPOINT = re.compile(r"api\.(?:get|post|put|delete)\(\s*['\"`]([^'\"`]+)")

# d?.by_reason / data.total / response.data.rate -- the read forms this codebase
# actually uses, confirmed by reading services/api/kpi.ts.
_FIELD = re.compile(r"\b(?:d|data|res|response|result)\??\.(\w+)")


def fields_read_by_frontend() -> dict:
    usage: dict = {}
    for path in sorted(FRONTEND.rglob("*.ts")) + sorted(FRONTEND.rglob("*.vue")):
        text = path.read_text(encoding="utf-8")
        # Split on export boundaries so a field read in one function is not
        # attributed to an endpoint called in a different one.
        for block in text.split("export const ")[1:]:
            endpoints = _ENDPOINT.findall(block)
            if not endpoints:
                continue
            fields = set(_FIELD.findall(block))
            for endpoint in endpoints:
                key = endpoint if endpoint.startswith("/api") else "/api" + endpoint
                usage.setdefault(key, set()).update(fields)
    return usage
```

- [ ] **Step 4: Run, confirm pass, then record its blind spot**

Add to the module docstring, verbatim:

```
LIMITATION, stated rather than discovered later: a dynamic read — `row[key]`
where `key` is computed — is invisible to this extractor. The golden master is
the backstop for that case: it does not care why a field is read, only that it
is still sent. Do not treat a clean extractor run as proof no field is needed.
```

- [ ] **Step 5: Commit**

```bash
git add backend/tests/contract/
git commit -m "test(contract): frontend field-usage extractor"
```

---

### Task 5: Golden master, with a zero-diff proof

**Files:**
- Create: `backend/tests/contract/golden/api_shapes.json`
- Create: `backend/tests/contract/test_golden_master.py`

- [ ] **Step 1: Capture against a disposable seeded database**

Build the fixture: temp file → `upgrade_to_head(url)` → `seed(engine, client_ids=tuple(sorted(ALLOWLIST_CLIENTS)), profile_name="smoke", seed_value=1234, as_of=date(2026,8,25), reset=False)` → `TestClient(app)` with `get_db` overridden. Never the VM.

- [ ] **Step 2: Write the comparison test**

```python
def test_no_route_lost_a_field():
    """Compares KEY SETS, never value types. Changing a type is the point of
    this refactor -- "4" becoming 4 is success -- so a type-comparing golden
    master would fail on every intended change and be switched off within a day.
    """
    captured = capture_all(client, loose_routes(app))
    golden = json.loads(GOLDEN.read_text())

    for route, keys in golden.items():
        assert captured.get(route) == keys, f"{route} changed shape"
```

- [ ] **Step 3: THE PHASE-0 EXIT CRITERION — zero diffs on unmodified main**

Run: `cd backend && python -m pytest tests/contract/test_golden_master.py -v --no-cov`
Expected: PASS with zero differences.

A net that cannot report "nothing changed" cannot be trusted to report "something changed". If this does not pass cleanly on untouched code, STOP and fix the harness before any route is converted.

- [ ] **Step 4: Mutation-prove it detects a dropped field**

Give one route a response model declaring one FEWER field than it returns, re-run, paste the failure naming the route. Restore.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/contract/
git commit -m "test(contract): golden-master shapes for all 164 loose routes"
```

---

### Task 6: Cluster by shape, then model the trend family

The efficiency insight this plan is built on: routes repeat shapes. Measured 2026-08-25 against the VM, **8 trend endpoints share exactly one shape** — `("date", "value")`. Convert by shape, never one route at a time.

**Files:**
- Create: `backend/schemas/kpi_contracts.py`
- Modify: `backend/routes/kpi/trends.py`
- Modify: `backend/tests/contract/allowlist.py`

- [ ] **Step 1: Print the shape clusters for /api/kpi**

```bash
cd backend && python -c "
import json, collections
g = json.load(open('tests/contract/golden/api_shapes.json'))
c = collections.defaultdict(list)
for route, keys in g.items():
    if '/api/kpi' in route:
        c[tuple(keys)].append(route)
for keys, routes in sorted(c.items(), key=lambda kv: -len(kv[1])):
    print(len(routes), list(keys)[:6])
    for r in routes: print('   ', r)
"
```

- [ ] **Step 2: Write the model for the largest cluster**

```python
# backend/schemas/kpi_contracts.py
"""Response contracts for /api/kpi.

Declared types are what close the Decimal class: MariaDB hands back Decimal,
Pydantic renders Decimal as a JSON string under `Any`, and a declared `float`
coerces it instead. See docs/superpowers/specs/2026-08-25-response-model-refactor-design.md.
"""

from pydantic import BaseModel


class TrendPoint(BaseModel):
    """One point on any KPI trend series.

    Shared by 8 endpoints (absenteeism, availability, efficiency, oee,
    on-time-delivery, performance, quality, throughput-time) — measured, not
    assumed: all 8 returned exactly ("date", "value") on 2026-08-25.
    """

    date: str
    value: float
```

- [ ] **Step 3: Apply it to all 8 trend routes**

Add `response_model=List[TrendPoint]` to each of the 8 decorators in `routes/kpi/trends.py`.

- [ ] **Step 4: Build it with `extra="forbid"` first (spec D5)**

Before applying the model, give it `model_config = ConfigDict(extra="forbid")` and run the
golden master. A field the endpoint returns but the model omits then raises loudly instead of
being dropped silently — which is the precise failure this refactor must not cause. Once
green, **remove the setting**: a strict model in production turns a benign extra key into a
500. It is a development scaffold, not a shipped behaviour.

- [ ] **Step 5: Cross-check the frontend extractor (spec D3)**

```bash
cd backend && python -c "
import json
from backend.tests.contract.frontend_usage import fields_read_by_frontend
usage = fields_read_by_frontend()
golden = json.load(open('tests/contract/golden/api_shapes.json'))
for ep in ['/api/kpi/efficiency/trend', '/api/kpi/quality/trend']:
    read = usage.get(ep, set())
    sent = {k.split('.')[0].replace('[]', '') for k in golden.get('GET ' + ep, [])}
    print(ep, 'read-but-not-sent:', sorted(read - sent))
"
```

Anything listed is a field the UI reads that the endpoint never returns — a **pre-existing**
bug, not one this refactor caused. Report it to the controller; do NOT quietly add it to the
model, which would invent a field the backend has no value for.

- [ ] **Step 6: Run the golden master and the suite**

Run: `cd backend && python -m pytest tests/contract/ tests/test_routes/ --no-cov -q`
Expected: PASS. The golden master must report no shape change — same keys, coerced types.

- [ ] **Step 7: Shrink the allowlist**

Remove those 8 routes from `ALLOWLIST`. Re-run the ratchet guard; it must pass with `stale == []`.

- [ ] **Step 8: Commit**

```bash
git add backend/schemas/kpi_contracts.py backend/routes/kpi/trends.py backend/tests/contract/allowlist.py
git commit -m "feat(api): typed response model for the 8 KPI trend endpoints"
```

---

### Task 7: Convert the rest of /api/kpi, then STOP and measure

**Files:**
- Modify: `backend/schemas/kpi_contracts.py`, the remaining `backend/routes/kpi/*.py`, `allowlist.py`
- Create: `docs/superpowers/plans/2026-08-25-response-model-refactor-PILOT-MEASUREMENT.md`

- [ ] **Step 1: Convert the remaining /api/kpi routes, largest cluster first**

Same loop as Task 6 per cluster: model → apply → golden master → shrink allowlist → commit.

- [ ] **Step 2: Record the measurement — this is the task's real deliverable**

Write the pilot measurement file with: routes converted, distinct models needed, wall-clock per route, how many needed frontend-audit follow-up, and how many golden-master failures were real versus harness noise.

- [ ] **Step 3: THE REASSESSMENT GATE — do not continue without it**

The spec's D2 says all 164. The pilot exists to test whether that survives contact. With the measured per-route cost, state a recommendation:

- continue to all 164 as specified;
- narrow to the ~48 numeric-risk routes and allowlist the rest permanently;
- stop after `/api/kpi` and keep the AST guards for the remainder.

Present the number and the recommendation to the human partner. **Do not begin `/api/workflow` without an answer.** The whole point of leading with a pilot is forfeited if it rolls straight on.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-08-25-response-model-refactor-PILOT-MEASUREMENT.md
git commit -m "docs(plan): pilot measurement and reassessment for the response-model refactor"
```

---

## Gate outcome (Task 7 Step 3) — answered 2026-08-25

The human partner chose **all 140 remaining routes** (not the narrowed 107 the pilot
recommended, and not stop-after-kpi), and **fix `coverage_of()` first**. Spec D2 survives
contact. Spec §8's open question about `/api/export` + `/api/reports` is thereby answered:
they are in scope.

Measured surface at the gate — the numbers these tasks are sized from:

| bucket | count | what conversion buys |
|---|---:|---|
| explicit GET | 81 | closes a real Decimal leak; capturable with today's harness |
| explicit mutation (22 POST, 2 PUT, 2 DELETE) | 26 | closes a real leak; needs the D4 write-capture harness first |
| undeclared | 33 (25 DELETE, 7 GET, 1 POST) | closes **no bug** — already immune; OpenAPI accuracy only |

Spec §6 predicted the DELETEs would be trivial. Measured: 25 of 27 are undeclared and
already immune, so they need no bug work at all — only contract declarations, last.

**Sequencing rule for everything below:** one area (or named group) per task, per the pilot's
demonstrated cost variance. Each task ends with the allowlist strictly smaller and the golden
master green. Do not batch areas into one PR.

**The recurring hazard the pilot found, restated because it will bite again:** a route whose
fields are *conditionally present* — an auth-scope-gated addition, or a `try/except` fallback
with a narrower shape — needs `response_model_exclude_unset=True`. Without it, `Optional[X] =
None` fields serialize as explicit `null` keys the route never used to emit. mypy cannot catch
this; only the golden master's key-set comparison does. Check every route for it explicitly
rather than assuming clean.

---

### Task 8: Repair the second safety net (`coverage_of`)

**Files:**
- Modify: `backend/tests/contract/frontend_usage.py`
- Test: `backend/tests/contract/test_frontend_usage.py`

The pilot measured `coverage_of()` returning `COVERED` for 9 of 15 routes that had **zero**
real field overlap — pure bleed from unrelated code in the same file. Combined with the 8
trend routes already in `KNOWN_BLIND`, the entire 24-route pilot area ran on one net, not the
two spec D3 requires. It must not be relied on across ~100 more routes in that state.

- [ ] **Step 1: Write the failing test.** Assert that a route whose frontend-read fields do
      not intersect its own declared/captured field names reports `NO_FIELDS_FOUND`, not
      `COVERED`. Use a real measured case from the pilot: `GET /api/kpi/efficiency/by-product`
      reads `avg_efficiency` from bleed, while the route's real fields are `actual_output`,
      `efficiency`, `product_id`, `product_name` — zero intersection.
- [ ] **Step 2: Run it, confirm it fails** with the current `COVERED`.
- [ ] **Step 3: Implement.** Require the fields found to intersect the route's actual field
      names (available from the golden master entry) before reporting `COVERED`. Report a
      third state where the endpoint is genuinely unused by the frontend, so "nobody reads
      this" is distinguishable from "the extractor cannot see it".
- [ ] **Step 4: Re-measure the pilot's 24 routes** and record the corrected coverage. If the
      corrected reading is that few or none are genuinely covered, say so — that is a real
      finding about the frontend audit's value, not a failure of this task.
- [ ] **Step 5: Mutation-proof + commit.**

**Exit criterion:** no route can report `COVERED` on bleed. `KNOWN_BLIND` shrinks or is
justified per remaining entry.

---

### Tasks 9–14: Convert the 81 explicit GET routes, by area

Same loop as Tasks 6 and 7, one task per grouping. Measure the exact route list and its
golden entries at dispatch time (the pilot's method), rather than trusting a list written
here that may drift.

| Task | area(s) | total | explicit | GET | notes |
|---|---|---:|---:|---:|---|
| 9 | `/api/workflow` | 14 | 14 | 9 | densest remaining; 5 mutations deferred to Task 15 |
| 10 | `/api/reports` + `/api/export` | 20 | 20 | 18 | spec §8's "benefit close to zero" area — **verify first** whether these return `FileResponse`/`StreamingResponse`, for which a `response_model` is meaningless. Any that do get a documented allowlist exception, not an invented model. |
| 11 | `/api/quality` + `/api/jobs` | 17 | 15 | 15 | |
| 12 | `/api/floating-pool` + `/api/attendance` | 14 | 12 | 8 | `/api/floating-pool/simulation/insights` returns **deliberate** numeric-looking strings (spec §6) — its model must declare `str`. Nested three levels; cover the interior. |
| 13 | `/api/work-orders` + `/api/kpi-thresholds` + `/api/capacity` + `/api/data-completeness` | 16 | 14 | 10 | |
| 14 | the explicit-GET tail | rest | | | `/api/cache`, `/api/predictions`, `/api/my-shift`, `/api/alerts`, `/api/shifts`, `/api/v2`, `/api/defect-types`, `/api/filters`, `/api/client-config`, `/api/pivot`, `/api/products`, `/api/downtime-reasons`, `/api/inference`, `/api/import-logs`, `/api/onboarding` |

Per task: model from the captured key set → apply → golden master → check
`response_model_exclude_unset` need → shrink allowlist → frontend audit (now trustworthy
after Task 8) → commit.

---

### Task 15: Build the D4 write-capture harness

**Files:** `backend/tests/contract/capture.py`, `backend/tests/contract/test_golden_master.py`

The 26 explicit mutation routes cannot be converted safely without capturing what they
actually return. Spec D4: disposable seeded database, `alembic upgrade head`, seed, exercise,
discard — never against the VM.

- [ ] Extend the harness to issue real writes with valid bodies, resolving required fields
      from seeded rows.
- [ ] Capture mutation responses into the golden master.
- [ ] **Prove the harness detects change**, exactly as Task 5 did for reads: a deliberately
      dropped field must fail and name the route and key. A harness that records
      `<status:422>` for every mutation because it cannot build a valid body is the same
      false green Task 5 caught — check for it explicitly.
- [ ] Where a mutation's shape genuinely varies with the request, record a documented
      allowlist exception (spec §6) rather than inventing a model.

---

### Task 16: Convert the 26 explicit mutation routes

Depends on Task 15. `/api/auth` holds 4 of them and is security-sensitive — its responses
must not gain or lose fields, and no token/credential field may be added to a model.
`/api/metrics/results` returns **deliberate** str-of-Decimal values (spec §6); its model
declares `str` and must stay that way.

---

### Task 17: Declare the 33 already-immune routes

These close no bug — they are the OpenAPI-accuracy half of D1. 25 are DELETEs, which spec §6
predicted would be uniform; confirm that and use one shared model if so. Lowest priority;
do them last so the risk-bearing work lands first.

**Completion:** the ratchet allowlist is empty, and `test_no_api_route_has_a_loose_response_model`
passes with no exceptions beyond those documented per spec §6.

---

### Task 8b: Real path-parameter id resolution, and recapture (BLOCKS Task 9)

**Inserted 2026-08-25**, after measuring Task 9's work list. Runs before Task 9.

**Files:**
- Modify: `backend/tests/contract/capture.py`, `backend/tests/contract/test_golden_master.py`
- Regenerate: `backend/tests/contract/golden/api_shapes.json`

`capture_all`'s own docstring states the hazard exactly: *"the caller owns id resolution — the
harness deliberately does not guess ids, because a wrong id yields a 404 whose shape is
recorded as if it were the real answer."* But `loose_routes()` returns `(method, route.path,
{})` — the raw template — so the caller resolves nothing, and every path-param route was
captured by requesting a URL containing **literal braces**.

Measured across the golden master's 63 path-param entries: 32 `<status:404>`, 22
`<status:422>`, 1 `<status:400>`, and 8 recording a 200 shape captured for an entity whose id
is the literal string `{client_id}`.

**The 8 are worse than the 54.** A probe against a real seeded client:

```
GET /api/workflow/statistics/{client_id}/status-distribution
    literal braces : 200, 3 keys
    REAL client    : 200, 5 keys
    missing: by_status[].count, by_status[].percentage, by_status[].status
```

That golden entry is wrong, not thin — it omits an entire nested object. A model built from it
would drop those three fields from production responses, or reject real responses under
`extra="forbid"`. That is the bug class this refactor exists to remove, sitting inside the
instrument meant to detect it.

62 of the 140 remaining routes (44%) carry a path param, so this blocks most of the work ahead.

- [ ] **Step 1: Resolve ids from seeded rows.** For each path param, select a real id from the
      seeded database — `client_id` from the seeded clients, `work_order_id` from a seeded work
      order, and so on. Derive them; do not hardcode a list that will drift from the seed.
- [ ] **Step 2: Fail loudly on an unresolvable param.** A param the resolver cannot fill must
      raise, naming the route and the param — NOT fall through to a literal-brace request. The
      whole defect is that an unresolved param silently produced a recordable answer.
- [ ] **Step 3: Recapture the golden master.** Expect large, legitimate churn: ~54 entries move
      from a status placeholder to a real shape, and some of the 8 change. Every changed entry
      must be explained in the report — a diff this large is exactly where a real regression
      hides, so do not wave it through as "expected churn". Confirm no entry moves from a real
      shape to a status placeholder; that direction means resolution got worse.
- [ ] **Step 4: Prove it.** Assert that no captured route records a status placeholder purely
      because its id was unresolved, and that no golden key contains a literal `{`. Mutation:
      break one resolver and confirm the guard fires, naming the route.
- [ ] **Step 5: Recheck `coverage_of`.** Task 8's `_real_field_names` reads the golden master.
      Routes that had no field names now have them, so coverage readings change — re-measure and
      report the new number. Some `KNOWN_BLIND` entries may no longer be needed.
- [ ] **Step 6: Commit.**

**Exit criterion:** no golden key contains `{`; every path-param route records either a real
shape or a status explained by something other than an unresolved id (a genuine 422 from a
missing request body is fine and expected for mutations, which Task 15 handles).

---

### Task 8c: Cross-tenant authorization sweep and fix (own PR, off main)

**Found 2026-08-25** while building Task 8b's resolution map. Not part of the response-model
refactor; sequenced after Task 8b because that task builds the id resolution the sweep needs.
**Ships as its own PR branched from `main`, not on the refactor branch** — a security fix
buried in a 140-route contract diff is neither reviewable nor backportable.

**Confirmed exploitable**, verified behaviourally against a seeded DB:

```
attacker: role=supervisor, client_id_assigned=DEMO-HOURLY
GET    /api/shifts/3   -> 200, body client_id=DEMO-HYBRID    cross-tenant READ
DELETE /api/shifts/3   -> 204                                cross-tenant DELETE
GET    /api/shifts     -> correctly scoped
GET    /api/production-lines/1 -> 200, owner DEMO-PIECE      cross-tenant READ
```

`routes/shifts.py:42` (list) uses `resolve_client_scope`; the `GET/PUT/DELETE /{shift_id}`
routes in the same file do not. `crud/shift.py:164` filters on `shift_id` alone. Same class as
PR #144's uniform client-scope work — these were missed.

- [ ] **Step 1: Build a two-tenant fixture, independent of the seeder.** Insert rows directly
      for every client-scoped ORM model, for two distinct clients. Do NOT depend on demo seed
      data: `CoverageEntry`, `Alert`, `FloatingPool`, `SimulationScenario` and
      `CalculationAssumption` have zero rows in both profiles, and a security test that inherits
      the seeder's gaps is narrowed by every future seeder change.
- [ ] **Step 2: Probe every by-id route behaviourally.** For each, request tenant B's row as a
      user scoped to tenant A and assert the response is 403/404, never 200-with-B's-data.
      **Grep is not a substitute** — an earlier grep for scope markers in endpoint bodies gave
      139 candidates, of which the behavioural probe showed work-orders, holds, production,
      quality, downtime, defect-types and client-config all correctly return 403. They enforce
      scope in the CRUD layer, invisible to the grep. Probe behaviour, not text.
- [ ] **Step 3: Resolve the integer-PK correlation.** Both confirmed-vulnerable entities use
      sequential integer PKs; every confirmed-protected one uses a client-prefixed string PK.
      Determine whether protection is riding on id format rather than an explicit tenant check.
      If it is, that is a design gap — any future integer-PK entity ships unscoped by default —
      and needs a structural guard, not two point fixes.
- [ ] **Step 4: Fix every route the sweep confirms**, following the existing
      `resolve_client_scope` pattern.
- [ ] **Step 5: Pin it.** Extend `test_permission_matrix.py` so cross-tenant denial is asserted
      per route. Mutation-proof: remove one scope check and confirm the matrix fails naming the
      route.

**Exit criterion:** no by-id route returns another tenant's row to a scoped user, and a test
fails loudly if one ever does again.

---

### Task 8d: Seed the unseeded tables

Measured during Task 8c prep: `COVERAGE_ENTRY`, `ALERT`, `FLOATING_POOL`,
`SIMULATION_SCENARIO` and `CALCULATION_ASSUMPTION` have **zero rows in both the smoke and full
profiles** — the seeder never writes them. The Task 8b resolution map identifies 19 path params
blocked on the same gap.

Consequences beyond this refactor: those features have no demo data, and their routes cannot be
contract-captured. Sequenced last because the seeder was cut over in S1c and this is real work
against it, not a harness tweak. Task 8b's blocked manifest is this task's input.

---

### Task 10 — CORRECTED 2026-08-25, after measuring what these routes actually return

The Tasks 9–14 table sizes Task 10 as "`/api/reports` + `/api/export`, 20 routes, 20 explicit,
18 GET" and flags spec §8's open question ("benefit close to zero") as something to verify
first. Verified. The premise was wrong, and the answer is not "convert 18 routes".

Measured against the golden master and the route sources:

| what | count | truth |
|---|---:|---|
| `/api/export/*` + `/api/reports/*/pdf|excel` | **17** | annotated `-> Any`, actually return `StreamingResponse`/`FileResponse`. Golden entry `<non-json>`. **A response model is not low-value here, it is wrong** — there is no JSON body to model. |
| `GET /api/reports/available` | **1** | genuine JSON, 10 keys. The only convertible route in this area. |
| `POST /api/reports/send-manual`, `POST /api/reports/email-config/test` | 2 | `<status:422>`, no body sent. Task 16. |

**So spec §8's open question is answered by measurement, not judgement: these 20 routes contain
exactly one response model worth writing.**

The remaining 17 are not an allowlist exception to be tolerated — they are **mis-annotated**.
`-> Any` is a false statement about a route that returns a CSV stream, and it is what puts them
in the explicit-risk bucket. Annotating the real return type is truthful, fixes the OpenAPI lie
(D1's stated secondary goal), and moves them from "explicit, real Decimal risk" to "no response
model by nature". Verified: `-> StreamingResponse` yields `response_model=None` and leaves the
response byte-identical.

**The ratchet needs a principled scope rule, not 17 permanent allowlist entries.** A route that
returns a `Response` subclass has no JSON body and therefore cannot leak a Decimal — it never
reaches Pydantic's serializer. Excluding it is correcting the guard's domain, not weakening it.

Gate it two-sided against the golden master, whose `<non-json>` marker is the independent
evidence. All 29 `<non-json>` entries decompose into exactly three categories:

- 3 already annotated as a `Response` subclass
- 9 `DELETE` returning 204 No Content (`-> None`)
- 17 the mis-annotated export/report routes

So the gate is: **every route declared out-of-scope must record `<non-json>`, and every
`<non-json>` entry must be explained by exactly one of {`Response` subclass, 204 No Content}.**
An unexplained `<non-json>` is a route returning something unparseable that nobody declared —
which is a finding, not noise. The 204 taxonomy built here is Task 17's input.

Allowlist: 131 → **113** (17 scoped out, 1 converted).

**Do not let a route dodge the ratchet by claiming a return type it does not have.** The
two-sided gate is what prevents that: a route annotated `-> StreamingResponse` that actually
returns a dict would record real JSON keys in the golden master and fail.

---

## Tasks 11–14 REPLACED by R1–R5 — 2026-08-26, sized from a measured classification

A 10-agent sweep classified all 111 then-remaining routes. The Tasks 9–14 table grouped by
route COUNT, before anyone knew what the routes return. Measured:

| class | count | can it take a response model? |
|---|---:|---|
| `json_body` | **69** | yes — this is the real remaining work |
| `no_content_204` | 25 | no — all DELETEs, Task 17 / the scope rule |
| `needs_request_body` | 11 | not until Task 15's write-capture harness |
| `file_download` | 6 | no — Task 10's scope rule covers them |

**38% of what remained can never take a response model.** `/api/qr` (5 routes, all PNG) was
mis-sized exactly as `/api/export` was, and appeared in **no** Task 11–14 grouping — it has
since been scoped out (`f0092c9`). `/api/workflow` residue is 5 routes, all Task 16's.

### The new batches, weighted by cost rather than count

Weight: 1 base, **+2** conditional shape (needs `exclude_unset` + a registry entry + a forcing
test — the expensive part), **+1** no usable golden evidence, **+1** Decimal hazard.
69 routes, 130 total weight, five batches of 26 each. The old four were 26 / 8 / 13 / 33.

| batch | areas | routes | weight |
|---|---|---:|---:|
| **R1** | `/jobs` | 7 | 26 |
| **R2** | `/quality` 8, `/capacity` 2, `/pivot` 1 | 11 | 26 |
| **R3** | `/floating-pool` 4, `/work-orders` 5, `/attendance` 4, `/alerts` 2 | 15 | 26 |
| **R4** | `/cache` 4, `/kpi-thresholds` 3, `/predictions` 3, `/data-completeness` 3, `/my-shift` 2, `/shifts` 2, `/plan-vs-actual` 2 | 19 | 26 |
| **R5** | `/auth` 4, `/v2` 2, `/defect-types` 2, + 9 single-route areas | 17 | 26 |

**Order: R4 → R3 → R2 → R5 → R1.** R4 is evidence-backed with near-zero conditionals — the
most routes closed for the least risk. R1 is last and has a hard prerequisite.

### R1's prerequisite — seed JOB first

`/jobs` is 10% of the convertible routes and 20% of the weight: 6 of its 7 routes have a
conditional shape (the highest concentration anywhere) and 6 of 7 have **no golden evidence at
all**, every one `<blocked:job_id>`. `param_specs.py:285` already records why:

> `job_id` … *"JOB has zero seeded rows; named in `seed/cli.py`'s never-written list. Blocks 8
> of the 15 blocked routes — the highest route-count payoff of any single seeder gap."*

Seed JOB (a slice of Task 8d) **before** R1, so R1 works from evidence rather than source
reading. Do not discover this during R1.

### Two standing instructions for every remaining batch

**1. Declare `float`, never `Decimal`.** A model field typed `Decimal` *creates* the
string bug this refactor exists to remove. And the golden master compares key sets, never value
types, **by design** — so it is structurally blind to exactly that regression: a `Decimal`-typed
field would leave the whole suite green. These routes need a narrow value-type assertion of
their own; do not weaken the golden master to get one.

**2. The remaining Decimal risk is live, not hypothetical.** Of the allowlisted routes, ~80
carry an explicit loose `response_model` and route through Pydantic's serializer; only ~33 are
undeclared and therefore already immune. `GET /api/inference/cycle-time/{product_id}` emits
`"ideal_cycle_time":"0.034260326879026824"` on **SQLite today**. See the CONTROLLER CORRECTION
at the head of §6 in `remaining-route-classification.md` — that document's §6 originally claimed
the opposite, and anything quoting it uncorrected inherits the error.
