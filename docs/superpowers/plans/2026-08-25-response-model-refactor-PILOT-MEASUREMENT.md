# Response-model refactor — pilot measurement (Task 7)

**Scope measured:** the 15 `/api/kpi/*` routes named in the Task 7 controller addendum
(everything in `/api/kpi` except the 9 trend routes Task 6 already converted, and except
`/api/kpi-thresholds`, which is a different router — see Ruling 12). Together with Task 6's
9, this closes all 24 `/api/kpi` routes the design spec's §3 measured, i.e. the entire pilot
area (§5, Phase 1) is now done.

This file is Task 7's real deliverable per the plan: a measured per-route cost, so the
reassessment gate (plan Step 3) has a number to decide from instead of a feeling.

## 1. Per-route measurement

| # | Route | Group | Model(s) | Effort tier | Notes |
|---|---|---|---|---|---|
| 1 | `GET /api/kpi/availability` | A (golden) | `AvailabilityKPI` | Simple | Flat, all fields already `float()`/`int()`-cast in source; model is a direct transcription. |
| 2 | `GET /api/kpi/dashboard` | A (golden) | `DailyProductionSummary` | Simple | List, 5 flat keys, direct transcription. |
| 3 | `GET /api/kpi/efficiency/by-product` | A (golden) | `EfficiencyByProduct` | Simple | List, 4 flat keys. |
| 4 | `GET /api/kpi/efficiency/by-shift` | A (golden) | `EfficiencyByShift` | Simple | List, 5 flat keys. |
| 5 | `GET /api/kpi/performance/by-product` | A (golden) | `PerformanceByProduct` | Simple | List, 5 flat keys. |
| 6 | `GET /api/kpi/performance/by-shift` | A (golden) | `PerformanceByShift` | Simple | List, 5 flat keys. |
| 7 | `GET /api/kpi/late-orders` | A (golden) | `LateOrder` | Simple | List, 5 flat keys; source is `identify_late_orders`. |
| 8 | `GET /api/kpi/wip-aging/top` | A (golden) | `WipAgingTopItem` | Simple | List, 4 flat keys. Used as the mutation-proof route (§4). |
| 9 | `GET /api/kpi/otd` | A (golden) + **hard** | `OTDSummary`, `TrueOTDBreakdown`, `StandardOTDBreakdown`, `LateOrderCounts` | **Hard** | Golden only shows 7 base keys; source inspection found a 4-key ADDITIVE branch (`true_otd`/`standard_otd`/`late_counts`/`justified_by_reason`) that fires only when scope resolves to exactly one client. Naive `Optional[...] = None` fields serialize as explicit `null` on every response — a real key-set regression the golden master caught. Fixed with `response_model_exclude_unset=True`. See §3. |
| 10 | `GET /api/kpi/dashboard/aggregated` | A (golden), **the hard one** | `AggregatedDashboard` + 9 nested models | **Hard** | 40 nested keys across 7 sections, each with a `try`/`except` fallback shape (fewer keys + an `error` string) the golden capture never exercises. Same null-explosion bug as #9, same fix. See §3. |
| 11 | `GET /api/kpi/chronic-holds` | B (no evidence) | `ChronicHold` | Moderate | Golden entry `[]`. Model from `identify_chronic_holds` in `calculations/wip_aging.py`. |
| 12 | `GET /api/kpi/otd/by-client` | B (no evidence) | `OTDByClient` | Moderate | Golden entry `[]`. Model from `get_otd_by_client` in `routes/kpi/otd.py`. |
| 13 | `GET /api/kpi/otd/late-deliveries` | B (no evidence) | `LateDelivery` | Moderate | Golden entry `[]`. Model from `get_late_deliveries` in `routes/kpi/otd.py`. |
| 14 | `GET /api/kpi/labor-hours` | B (no evidence) | `LaborHoursSummary` + 4 nested models | Moderate–hard | Golden entry `<status:422>` (requires `start_date`/`end_date`). Model traced through `summarize_labor_hours` (`calculations/labor_hours.py`) plus the route's own `_coerce_nested`/`earned_hours` additions. `by_category` is a dynamic value-keyed map (`Dict[str, float]`), same treatment `capture.py`'s `MAP_FIELDS` already gives the identically-named field on `/api/alerts/dashboard`. |
| 15 | `GET /api/kpi/{metric}/cause` | B (no evidence), **converted, not allowlisted** | `KPICauseResponse` | Moderate | Golden entry `<status:422>` (path param + required `date`). Read all 7 driver functions in `kpi_cause_service.py` plus both fallback branches; the key set `{date, metric, kind, factor, value, unit, share}` is provably invariant across every metric. See §5. |

**Distinct models: 31** (15 top-level, one per route as instructed — the by-shift/by-product
and efficiency/performance pairs are deliberately NOT shared — plus 16 nested: 9 for
`AggregatedDashboard`'s sections, 3 for `OTDSummary`'s single-client-scope addition, 4 for
`LaborHoursSummary`'s totals/buckets/counts). All in `backend/schemas/kpi_contracts.py`
(408 lines after this task, was 26; file stays well under the 500-line guideline).

**Wall-clock, honestly:** this was one continuous session, not stopwatched per route, so the
table above reports effort *tiers* rather than fabricated minutes. The real signal is the
variance: 8 of 15 routes (Simple tier) were a direct transcription of a golden key list into
a flat or single-level-list model — comparable to Task 6's trend-route cost. 3 of 15
(Group B, Moderate) needed a full read of the underlying calculation function with zero
capture-time verification available. **2 of 15 (`otd`, `dashboard/aggregated`) cost roughly
as much as the other 13 combined** — nested nested nested structures plus a genuine,
non-obvious Pydantic serialization bug (§3) that would have shipped a silent regression had
the golden master not caught it. `{metric}/cause` (Moderate) additionally required reading
every one of 7 driver functions to safely justify converting it rather than allowlisting it
(§5). **The lesson for the reassessment: per-route cost is not uniform, and the outliers are
exactly the routes with nested or conditional response shapes — a pattern that recurs
elsewhere in this codebase (any route with a `try/except` fallback, any route whose shape
depends on auth scope) and should be assumed present, not treated as a `/api/kpi`
peculiarity.**

## 2. Golden-master failures: real vs. noise

**UPDATED post-review (reviewer finding F2):** the original cut of this section reported
"2 real, 0 noise" and closed the book too early. The gate itself carries a third,
genuinely-noise failure mode -- unrelated to any of the 15 conversions, but surfaced by
this task's own claim that the golden master is the pilot area's sole working safety net
(SS6). Corrected count: **2 real (found and fixed as part of the 15 conversions), 1 noise
(a pre-existing, time-of-day-flaky gate, found by the reviewer and fixed as a follow-up)**.

**The noise one, first, since it changes what "green" meant going into this report:**
`GET /api/shifts/active` (`backend/routes/reference.py::get_active_shift`, not one of the
15 -- it is a plain, still-`Optional[dict]`-loose allowlisted route) branches on
`datetime.now(tz=timezone.utc).time()`: whether a seeded shift is active, and therefore
whether the route returns a shift dict or 404, depends on the real wall-clock hour the
suite happens to run at. The committed golden entry is `["<status:404>"]`, captured during
a no-shift-active window; the seeded shift windows tile 16 of every 24 hours (see
`capture.ShiftActivePin`'s docstring for the exact windows), so for that majority of
the day a shift IS active and the gate fails with
`AssertionError: GET /api/shifts/active changed shape`. Reproduced live against this
task's own HEAD at 18:17 UTC (real time at the moment of the fix), confirming it is not
hypothetical. Pre-existing at the parent commit (`40f4a92`) too -- not introduced by this
task's 15 conversions -- but fixed here per this repo's rule that a finding surfaced
during a deliberate verification pass expands the current task rather than becoming
tech debt. Fixed by pinning only `backend.routes.reference`'s `datetime.now()` to a fixed
time-of-day (15:00 UTC, inside the dead zone common to every smoke-seeded shift) during
golden-master capture, via a new `ShiftActivePin` class in `capture.py`, plus a dedicated
`test_time_determinism.py` that captures the route at two real moments straddling the
shift boundary and asserts identical output -- mutation-tested twice (removing the
fixture's `time_pin.setattr(...)` line reproduced the live failure verbatim; a second
mutation inside `ShiftActivePin.now()` itself broke the new determinism test). Swept for
other routes reading the clock the same way: one other hit
(`routes/production.py:80`), not in the golden master's 164-route surface at all (already
has a real `response_model`, and is a POST the capture harness never sends a body to), so
no further routes needed the same treatment. Zero other golden entries changed when the
pin landed -- the full `test_no_route_lost_a_field` run stayed green across all 164
entries, confirming the pin is scoped correctly.

**The 2 real ones, both found and fixed as part of converting the 15:**

1. `GET /api/kpi/otd` — after applying `response_model=OTDSummary` (no `exclude_unset` yet),
   `test_no_route_lost_a_field` failed: `AssertionError: GET /api/kpi/otd changed shape`.
   Diffing showed 4 **extra** keys (`true_otd`, `standard_otd`, `late_counts`,
   `justified_by_reason`), all serialized as `null`. Root cause: these 4 fields are
   `Optional[...] = None` on the model to survive the route's conditional branch (only
   present in the source dict when `scope.client_ids` resolves to exactly one client), but
   Pydantic serializes every *declared* field by default regardless of whether the source
   dict actually set it — so under the admin auth the golden master was captured with
   (`scope.client_ids is None`, i.e. all clients, so the branch never fires), all 4 keys
   still appeared as explicit `null`. Confirmed by directly querying the route: before the
   fix the body carried `"true_otd": null` etc. even though the *original*, unconverted
   route never emitted those keys at all in that case.
2. `GET /api/kpi/dashboard/aggregated` — same failure, same root cause, worse: all 7 nested
   sections declare an `error: Optional[str] = None` field to survive their
   `SQLAlchemyError`/`Exception` fallback branch, and every one of them showed up as
   `"error": null` on the ordinary success path (confirmed 200, no exception, via a direct
   query — `logger.exception` never fired).

**Fix:** `response_model_exclude_unset=True` on both routes' decorators. This makes
serialization track *whether the source dict actually set the key*, not merely whether the
model declares a default — so a field genuinely absent from the returned dict is genuinely
absent from the JSON, and a field genuinely present (including the conditional/error-path
ones) still serializes with real content. Verified both branches directly:
`GET /api/kpi/otd` (no `client_id`) now returns exactly the 7 golden keys; `GET
/api/kpi/otd?client_id=SAMPLE_REF` (forces the single-client branch) returns all 11 keys with
real, correctly-typed content (`"percentage": 100.0`, not `"100.00"`). Same check for
`dashboard/aggregated`: success path has no `error` keys anywhere; the model still validates
if a fallback branch fires (verified by construction, not by forcing a live DB error).

**Zero noise failures traceable to the 15 conversions themselves** in the actual
`cd backend && pytest tests/contract/` run (14/14 green after the fix, at the time this
task's own conversion work was verified). One artifact worth naming so it isn't mistaken
for a third real failure from the 15: an ad hoc debugging script run from the repo root
(not `backend/`) reproduced the already-documented, pre-existing
`POST /api/predictions/demo/seed` import bug (missing `backend.` package prefix,
cwd-sensitive — see `test_golden_master.py`'s own module docstring). This is Task 5's
documented harness gotcha, not something this task's changes caused, and it does not
appear when running the real suite the documented way.

This is distinct from the time-of-day noise failure documented above the 2 real ones in
this section: that one is unrelated to any of the 15 routes and was found by the
reviewer, not by this task's own verification pass, hence the corrected "2 real, 1
noise" count at the top rather than a contradiction with "zero noise" here.

## 3. The bug this task found (worth generalizing)

**`response_model_exclude_unset` is required, not optional, on any route whose fields are
conditionally present in the source dict** — a client-scope-gated addition (`otd`) or a
`try/except` fallback with a narrower shape (`dashboard/aggregated`). Without it, a precise
model with `Optional[X] = None` fields *looks* correct (mypy is happy, the model captures
every field that can appear) but silently adds `null`-valued keys to responses that used to
omit them entirely — a real "endpoint changes what it returns" violation of this refactor's
core safety property, and one the type checker cannot catch. The golden master caught it
both times because it compares key sets, not because anyone anticipated the bug going in.
Any future route with a similar shape (auth-scope-gated fields, error-fallback shapes,
anything upstream of a `try/except`) needs the same treatment, and should be checked for it
explicitly rather than assumed clean by mypy + a passing golden master run with the
*success*-path evidence only.

## 4. Mutation proof (dropped a field, then restored)

Full detail and exact `AssertionError` text is in the Task 7 report
(`.superpowers/sdd/2026-08-25-response-model-refactor/task-7-report.md`). Three real,
reverted mutations, each producing the exact predicted failure:

1. Dropped `efficiency: float` from `EfficiencyByProduct` →
   `AssertionError: GET /api/kpi/efficiency/by-product changed shape`.
2. Re-added a just-converted route (`GET /api/kpi/otd`) to `ALLOWLIST` →
   `AssertionError: these are converted — remove them from ALLOWLIST`.
3. Bumped the pinned `loose_routes(app)` count from 140 to 141 →
   `AssertionError: assert 140 == 141`.
4. (Extra, not required but informative) Added an undeclared extra field to
   `wip-aging/top`'s response dict under the temporary `extra="forbid"` dev scaffold →
   flipped the route from a real shape to `<status:500>`, which tripped **two** golden-master
   assertions at once (`test_no_route_lost_a_field` and
   `test_status_only_routes_stay_under_the_measured_ceiling`, `79 <= 78` failing) — direct
   proof the dev-mode `extra="forbid"` scaffold (removed before commit, spec D5) actually
   rejects an undeclared field rather than silently accepting it.

## 5. Group B disclosure (no captured evidence)

Per the brief, disclosed explicitly and individually — these 5 models come from reading the
calculation/service source, not from a captured response:

- **`GET /api/kpi/chronic-holds`** — golden entry `[]` (no rows under the smoke seed).
  `ChronicHold` derived from `identify_chronic_holds` (`backend/calculations/wip_aging.py`).
- **`GET /api/kpi/otd/by-client`** — golden entry `[]`. `OTDByClient` derived from
  `get_otd_by_client` (`backend/routes/kpi/otd.py`).
- **`GET /api/kpi/otd/late-deliveries`** — golden entry `[]`. `LateDelivery` derived from
  `get_late_deliveries` (`backend/routes/kpi/otd.py`).
- **`GET /api/kpi/labor-hours`** — golden entry `<status:422>` (requires query params the
  harness doesn't supply). `LaborHoursSummary` derived from `summarize_labor_hours`
  (`backend/calculations/labor_hours.py`) and the route's own additions.
- **`GET /api/kpi/{metric}/cause`** — golden entry `<status:422>`. `KPICauseResponse`
  derived from every driver function in `backend/services/kpi_cause_service.py`, not
  allowlisted (see below).

**A sixth, partial disclosure the brief did not anticipate:** `GET /api/kpi/otd` is Group A
(the golden master captured 7 real keys), but its additive 4-key branch
(`true_otd`/`standard_otd`/`late_counts`/`justified_by_reason`) has **zero captured evidence**
under the committed golden master — the admin auth it was built with resolves to all clients,
never the single-client branch that emits those keys. That sub-shape is Group-B-style source
inspection (verified live against a forced single-client request in §2/§3, not just read),
grafted onto an otherwise Group-A route.

**`{metric}/cause` was converted with a real model, not allowlisted**, which differs from
the brief's suggested "141 with cause deliberately retained" outcome. Justification: the
brief's caution ("if its shape is genuinely variable, a precise model may be wrong") is
based on the route's own docstring warning that payloads vary by metric. Reading the
dispatch table and all 7 driver functions plus both fallback branches (unknown metric,
driver returns `None`) shows the **key set** is invariant — every path returns exactly
`{date, metric, kind, factor, value, unit, share}` — only the *values* vary by metric, which
is exactly the kind of variation this whole refactor is designed to tolerate (type coercion,
not key churn). `kind`/`factor` are `Optional[str]` (`None` only on the two fallback
branches), `unit` is always a real `str` (empty string on fallback, never `None`),
`value`/`share` are `float | None` on the `CauseResult` dataclass itself. **Allowlist ends at
140, not 141.**

## 6. Frontend-audit follow-up: needed for all 15, and the extractor itself misreported

All 15 routes needed a manual, from-source verification pass — the automated
`frontend_usage.coverage_of()` extractor gave **zero trustworthy signal** for any of them,
which extends (previously undocumented for this cluster) the same failure mode
Task 4/`KNOWN_BLIND` already found for the 8 trend routes:

| Route | `coverage_of()` | Real overlap with the route's actual fields |
|---|---|---|
| `availability` | `NO_FIELDS_FOUND` | — (honest zero) |
| `dashboard` | `COVERED` | **2/5** real (`avg_efficiency`, `avg_performance`); `date`/`entry_count`/`total_units` missed |
| `dashboard/aggregated` | `NO_FIELDS_FOUND` | — (honest zero; also unused by the frontend at all — no call site found anywhere under `frontend/src`) |
| `efficiency/by-product` | `COVERED` | **0/4** — pure bleed (`avg_efficiency` ≠ `efficiency`) |
| `efficiency/by-shift` | `COVERED` | **0/5** — pure bleed |
| `late-orders` | `NO_FIELDS_FOUND` | — (honest zero) |
| `otd` | `COVERED` | **0/7** — pure bleed |
| `performance/by-product` | `COVERED` | **0/5** — pure bleed (`avg_performance` ≠ `performance`) |
| `performance/by-shift` | `COVERED` | **0/5** — pure bleed |
| `wip-aging/top` | `COVERED` | **0/4** — bleed from the sibling `/wip-aging` endpoint's fields in the same file |
| `chronic-holds` | `NO_FIELDS_FOUND` | — (honest zero) |
| `otd/by-client` | `COVERED` | **0/5** — pure bleed |
| `otd/late-deliveries` | `COVERED` | **0/5** — pure bleed |
| `labor-hours` | `NO_FIELDS_FOUND` | — (honest zero) |
| `{metric}/cause` | `NO_FIELDS_FOUND` | — (honest zero) |

**Named per the task's own warning:** `coverage_of()` returns `"COVERED"` whenever
`fields_read_by_frontend()` found *any* field name at all for that endpoint's literal, with
no check that the fields found are actually the endpoint's real fields. If the extractor
were completely broken (matched nothing meaningful anywhere), 6 of 15 routes would report
exactly what they report today (`NO_FIELDS_FOUND`) and the other 9 would *still* report
`COVERED` off pure bleed from unrelated code in the same file — the check would look
identical to a working one. This is the same failure class `KNOWN_BLIND` already documents
for the trend cluster (a false "10/10" reading 0/10 real protection), just not previously
measured for these 15. It is not this task's file to fix (`frontend_usage.py`/`coverage_of`
is shared infrastructure, out of Task 7's scope), but it means: **the golden master is the
only safety net that actually works for this entire pilot area (24/24 `/api/kpi` routes)**,
not one of two nets as spec D3 intends. Worth a follow-up task on `coverage_of()` itself
(require the found fields to intersect the route's own declared field names) before relying
on it anywhere else.

## 7. Re-measured explicit/undeclared split

Measured directly from `route.response_model` on the live `FastAPI` app object (not
estimated), both before and after this task, using a disposable git worktree at the parent
commit (`40f4a92`) to get a clean, uncontaminated baseline:

| | Total loose | Explicit (`response_model` is `Any`/`dict`/`list`/a loose wrapper) | Undeclared (`response_model is None` — already immune) |
|---|---:|---:|---:|
| Before Task 7 (= after Task 6, commit `40f4a92`) | 155 | **122** | **33** |
| After Task 7 (this task) | 140 | **107** | **33** |

**This corrects the brief's stated starting baseline of "124 explicit / 31 undeclared."**
Independently re-measuring at the pre-Task-7 commit gives 122/33, not 124/31 — a real
discrepancy from whatever produced the brief's numbers, not a rounding difference. It is
reported here rather than silently reconciled. The post-Task-7 numbers are internally
consistent with this corrected baseline: all 15 converted routes were confirmed explicit
before conversion (each read individually; none was `response_model is None`), so 122 − 15 =
107 explicit and 33 undeclared unchanged — exactly what was measured.

**Mechanism, verified via `fastapi.dependencies.utils.get_typed_return_annotation`:** a
function with literally no `->` annotation gets `response_model = None` (immune — FastAPI
serializes via `jsonable_encoder`, which renders `Decimal` as a JSON number). Any concrete
loose annotation (`-> Any`, `-> list`, `-> dict[str, Any]`, or an explicit
`response_model=Any`) is NOT `None` and routes through Pydantic's own serializer, which
stringifies `Decimal` under `Any`/`dict`/`list`. This is the exact mechanism spec §2
describes; the "undeclared" bucket is the routes for which the bug was already structurally
impossible, and the "explicit" bucket is where D2's payoff (closing a real Decimal-leak
risk) actually lives.

## 8. Reassessment (plan Step 3 — see the Task 7 report for the recommendation)

The measured numbers above (107 real-risk routes remaining, 2-of-15 outlier cost concentrated
in nested/conditional shapes, and a frontend safety net now shown unreliable for an entire
adjacent cluster) feed directly into the recommendation in
`.superpowers/sdd/2026-08-25-response-model-refactor/task-7-report.md`. This file stops at
measurement, per plan Step 2; the decision itself belongs in the report and to the human
partner, per plan Step 3.
