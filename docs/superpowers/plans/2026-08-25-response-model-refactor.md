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
Expected: PASS, 160 collected

- [ ] **Step 5: Mutation-prove the count pin**

Temporarily give one loose route a real `response_model` in its router, re-run, and paste the failure (`assert 159 == 160`). Restore, confirm `git diff HEAD` empty.

- [ ] **Step 6: Commit**

```bash
git add backend/tests/contract/
git commit -m "test(contract): pin the 160-route refactor scope"
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
git commit -m "test(contract): golden-master shapes for all 160 loose routes"
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

The spec's D2 says all 160. The pilot exists to test whether that survives contact. With the measured per-route cost, state a recommendation:

- continue to all 160 as specified;
- narrow to the ~48 numeric-risk routes and allowlist the rest permanently;
- stop after `/api/kpi` and keep the AST guards for the remainder.

Present the number and the recommendation to the human partner. **Do not begin `/api/workflow` without an answer.** The whole point of leading with a pilot is forfeited if it rolls straight on.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-08-25-response-model-refactor-PILOT-MEASUREMENT.md
git commit -m "docs(plan): pilot measurement and reassessment for the response-model refactor"
```
