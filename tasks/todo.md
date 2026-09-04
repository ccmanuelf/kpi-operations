# Tasks

## WORKING ORDER (agreed 2026-09-03)

1. ~~cross-tenant attendance fix~~ — DONE, see below
2. full e2e browser validation
3. `_get_calendar_data` divides by the shift count twice
4. custom-reports capability — propose from the structure and features the
   system ACTUALLY has. Explicitly NOT an attempt to reproduce the legacy
   Excel, which no longer relates to what the product does.
5. issue #278 — a catalog assumption that can never take effect
6. the lower-value findings below
7. unauthenticated SMTP — **DEFERRED BY DECISION**, not an open task. There is
   no authorization to enable email notifications, so the connection attempt
   is unreachable in practice. Revisit only if email is ever turned on; the
   finding stays recorded below so the deferral is a choice on record rather
   than an oversight.


## RESOLVED: `kpi-detail-views.spec.ts` flake — root-caused and fixed 2026-09-04

UPDATE 2026-09-03, second sighting — and it rules something out. The first was
during the vite 8 work, which made vite 8 a candidate cause. This one happened
on a branch containing no vite change at all (the part-opportunities import
fix), so the bundler is not implicated. Still ~1 in 15, still passes in
isolation, and still not reproducible on demand: six consecutive full runs
after the failure were all green, so the assertion error remains uncaptured.

RESOLUTION 2026-09-04, fourth and fifth sightings. The rate rose to ~1 run in
2, which made it measurable at last. It was never state left behind by another
spec — it was a timeout, and the earlier "assertion error" reading was wrong.

Evidence. Running the full suite with `--testTimeout=30000 --reporter=verbose`
timed each test in the file:

    Efficiency.vue    7727ms   <-- first dynamic import in the file
    Performance.vue    406ms
    Quality.vue        153ms
    Availability.vue    77ms   (the rest, 77-252ms)

Every view test did `await smokeMount(() => import('@/views/kpi/X.vue'))`, so
the FIRST one paid the cold transform of the entire dependency graph all 8 KPI
views share, inside the default 5s per-test timeout. Under full-suite
contention that exceeds 5s; on an idle machine it squeaks under. That is why it
never reproduced in isolation — an isolated run has no contention — and why it
was always Efficiency.vue, the first one.

Fix: static imports, which are hoisted to module load and are NOT billed against
the per-test timeout. This required also wrapping `apiMock` in `vi.hoisted`,
since the hoisted `vi.mock` factory closes over it and static imports would
otherwise evaluate first and hit the TDZ. That is precisely why the file used
dynamic imports in the first place, and it is what `admin-views.spec.ts` — same
shape, never flaked — already does.

Result: Efficiency.vue 7727ms -> 124ms under identical full-suite load, now 40x
inside the timeout rather than 1.5x over it. Four consecutive full runs green,
against roughly one failure in two beforehand. The race is removed at the
source, not widened.

Seen while validating the vite 8 bump: `KPI detail views — smoke mount >
Efficiency.vue mounts without errors` failed once, then passed 14 consecutive
full-suite runs and 3 of 3 in isolation. I could not reproduce it again to
capture the assertion error, so the cause is NOT established and nothing has
been changed.

What is known:

  * the Efficiency case is the only one in that file asserting more than
    `wrapper.exists()` -- it also checks `.v-container` exists;
  * `<v-container>` is Efficiency.vue's unconditional root element (line 2),
    so the obvious "render has not settled yet" explanation does NOT hold;
  * `smokeMount` awaits the dynamic import but never awaits a tick after
    `shallowMount`, and `onMounted(() => initialize())` starts async work --
    a plausible but UNCONFIRMED source of cross-test interference;
  * the mechanism is bundler-independent, so attributing it to vite 8 is not
    supported. It was not shown to be pre-existing either: that would need
    ~15+ full runs on the previous vite to compare fairly, which was not done.

Worth pinning down because docs/CONTRIBUTING.md states zero tolerance for
flaky tests. The cheap first step is to make the failure reproducible --
run the file repeatedly under `--sequence.shuffle` or with a fixed seed --
before changing anything.


## RESOLVED (#277, 2026-09-02) — the dual view showed a zero delta on every client and metric

`aggregate_oee_inputs` sums `downtime_hours`, `setup_time_hours` and
`maintenance_hours` off PRODUCTION_ENTRY, and `units_reworked` off
QUALITY_ENTRY. The seeder wrote NONE of the four (0 across 4160 / 4088 rows),
so three of the six assumption rules operated on zeros, standard equalled
site-adjusted exactly, and OEE read 99.5% for every client.

Seeding the split fixed both at once. Verified on the VM against MariaDB:

    DEMO-PIECE   standard=92.84  site_adjusted=94.68  delta=1.84
    DEMO-HOURLY  standard=92.60  site_adjusted=94.42  delta=1.82

FPY gained a delta too (98.41 -> 98.73), which follows from `units_reworked`
making `scrap_classification_rule` live.

Note the seeder writes PRODUCTION_ENTRY.downtime_hours as the shift's recorded
stoppage PLUS its planned components, while DOWNTIME_ENTRY keeps only the
unplanned minutes with their root cause. The two tables answer different
questions; the dual view reads the former exclusively.


## OPEN (issue #278) — a catalog assumption that can never take effect

`ideal_cycle_time_source = "demonstrated_best"` is applied only when
`demonstrated_best_cycle_time_hours` is set, and `aggregate_oee_inputs` never
sets it on any production path. A site selecting it sees the assumption
recorded, approved and listed as active while OEE keeps using the engineering
standard. `rolling_90_day_average` sits behind the same kind of guard and
should be checked with it.

The seeder deviates `setup_treatment` instead, with the reason recorded beside
CALCULATION_ASSUMPTIONS so the choice is not reverted. That is a workaround in
demo data, not a fix.


## RESOLVED (2026-09-03) — cross-tenant attendance rows

The guard shipped between the finding and this review: both write paths call
`_require_employee_belongs_to_client` (crud/attendance.py:181 single, :472
bulk), and six unit tests in
tests/test_crud/test_attendance_rejects_cross_tenant_employees.py cover the
rejection, a same-client employee still being accepted, a MULTI-client
employee accepted for each of their clients (the comma-split case a `==`
would have broken), a floating-pool employee not being locked out, and a
missing employee refused the same way as someone else's.

Two things closed here rather than assumed:

  * `mark_all_present`, the third write path, is clean BY CONSTRUCTION -- it
    queries employees assigned to the client instead of taking ids from the
    caller, so it cannot express a cross-tenant row. That was the plan's
    "check the sibling write paths" bullet.
  * the defect was originally found over HTTP, and every existing test called
    the CRUD function directly -- so all of them would still pass if the route
    stopped going through it. Added
    `test_bulk_create_refuses_another_clients_employee_over_http`, which
    asserts the row FAILS and that nothing reaches the table. The endpoint
    answers 201 whatever its rows did, so the status alone proves nothing.
    Mutation-proofed: removing the guard makes it report
    `successful: 1` with a created id, reproducing the original finding.

### (original finding)

## NEXT: cross-tenant attendance rows (found 2026-08-30, verified)

`POST /api/attendance/bulk` accepts an employee belonging to a DIFFERENT client
and writes the row.

Reproduction, measured against the seeded contract database:

    body [{client_id: "DEMO-HOURLY", employee_id: 1, shift_date: <seed>, scheduled_hours: 8}]
    employee 1's client_id_assigned is 'DEMO-PIECE'
    -> 201, successful=1, failed=0
    -> ATTENDANCE_ENTRY row written with (client_id='DEMO-HOURLY', employee_id=1)

`bulk_create_attendance_records` performs no check that the employee belongs to
the row's client. FK enforcement would not catch it either: the mismatch is
COMPOSITE (both ids exist, they just do not belong together). Same tenancy
class as the uniform client-scope work in #144.

Found by the contract harness: the route only started running when write
capture gave it a body, and the id-consistency spec written to avoid the
mismatch is what made the acceptance visible.

PLAN (own PR, agreed):
  * per row, require the employee's `client_id_assigned` to contain the row's
    `client_id`; otherwise that row fails with a tenancy error. The route is
    per-row and answers 201 regardless, so this belongs in the per-row error
    list rather than as a whole-request 4xx.
  * test: a cross-tenant row is rejected and NOT written
  * test: a same-tenant row still succeeds (or the first test passes on a
    route that rejects everything)
  * check the sibling write paths in crud/attendance.py for the same gap


## FOUND, not fixed: unauthenticated SMTP connection attempt in production

`EmailService` connects to SMTP_HOST and attempts a send even when it has NO
credentials. Read from the code, and demonstrated by removing the contract
harness's stub -- the suite then logged "SMTP test email delivery failed" and
"SMTP delivery failed", i.e. it really did try.

    SMTP_USER = ""   SMTP_PASSWORD = ""   SENDGRID_API_KEY = ""
    SMTP_HOST = set, defaulting to smtp.gmail.com

    services/email_service.py:
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:   # connects
            if self.smtp_user and self.smtp_password:                  # merely SKIPS
                server.login(...)                                      # the login

The routes' own "email service not configured" branch is reached on
ImportError alone, never on absent credentials, so it does not cover this.

CONSEQUENCE: a caller of POST /api/reports/email-config/test or
POST /api/reports/send-manual on a deployment without mail configured causes an
outbound connection to smtp.gmail.com that can only fail -- a slow 500 rather
than a fast, honest "not configured", and an egress attempt from the API host.

The contract harness stubs the transport, so the TEST SUITE is unaffected. That
stub does not change production behaviour and was never meant to.

DECISION NEEDED, since it changes outward behaviour: should `EmailService`
report "not configured" when it has no credentials instead of connecting?
That looks obviously right -- an unauthenticated send to a public relay cannot
succeed -- but it changes what a deployed API returns, so it is the user's call
rather than a silent fix.


## RESOLVED — `DELETE /api/filters/history` is unreachable (route shadowing)

Fixed by registration order: `routes/filters.py` now declares `/history`
(line 172) BEFORE `/{filter_id}` (line 182), so the specific path wins the
match. Confirmed two ways rather than by reading the diff: the route resolves
to `clear_user_filter_history`, and the contract golden master records
`DELETE /api/filters/history` as `["<non-json>"]` -- a real captured 204 --
where it previously held the shadowing route's 422.

`DELETE /api/filters/{filter_id}` remains `<blocked:filter_id>`, and for an
unrelated reason: SAVED_FILTER is scoped by `user_id`, so a seeded row 404s
for every non-owner including an admin. It is the last entry in
BLOCKED_ROUTES, blocked by the schema rather than by seeder coverage.

### (original finding)

The endpoint exists and can never be called. `routes/filters.py` registers

    line 168:  @router.delete("/{filter_id}")     filter_id: int
    line 315:  @router.delete("/history")         no parameters at all

and FastAPI matches in REGISTRATION order, so `DELETE /api/filters/history`
binds to `{filter_id}="history"`, fails int parsing, and 422s. Measured:

    DELETE /api/filters/history -> 422
    {"detail":[{"type":"int_parsing","loc":["path","filter_id"],
                "input":"history"}]}

`clear_user_filter_history` is therefore dead over HTTP. Any unit test calling
the CRUD directly would pass while the route stayed unreachable.

Found by the contract harness: `<status:422>` on a route whose handler takes NO
parameters is impossible from its own signature, which is what made it worth
looking at.

FIX: register the literal path BEFORE the parameterised one (the standard
FastAPI ordering rule). Small, but it changes which handler answers a live URL,
so it wants its own PR and a test that pins the ordering rather than the
symptom -- a test asserting 204 would pass again if someone later re-ordered
the file, only for a different literal route to start shadowing.

CHECKED, and it IS a class -- TWO dead endpoints, not one:

    GET /api/holds/pending-approvals   -> 404 {"detail": "WIP hold not found"}
        Shadowed by GET /api/holds/{hold_id}. WORSE than the filters case: the
        id is a STRING, so it matches, looks up a hold called
        "pending-approvals", finds none, and answers a misleading 404. A caller
        asking for a list is told a hold does not exist.

    DELETE /api/filters/history        -> 422 int_parsing on filter_id
        Shadowed by DELETE /api/filters/{filter_id}. The int parse fails, so at
        least the error names the real cause.

    GET /api/alerts/config/            -> 200, NOT affected. Flagged by my
        first scan only because it normalised away the trailing slash; the
        registered path really is `/api/alerts/config/`, which does not collide
        with `/api/alerts/{alert_id}`. A false positive, recorded so the next
        reader does not re-investigate it.

METHOD NOTE: the first version of that scan reported ZERO shadowed routes while
I had a proven instance in hand. It walked `app.routes` naively and saw 9
(method, path) pairs instead of 460 -- FastAPI nests routers behind
`_IncludedRouter`, which is the same trap that made an earlier structural test
pass on an empty list. Use `capture.flatten_api_routes`.

FIX: register each literal path BEFORE its parameterised sibling. The test
should pin the ORDERING PROPERTY across all routers -- a test that merely
asserts 204/200 on these two would pass again if a third literal route were
added after a `/{param}` tomorrow.


## OBSERVATION: the golden master tracks 164 of 460 live /api routes

Measured while fixing the route shadowing: 296 live routes have no shape
contract. Zero golden entries point at a route that no longer exists, so the
subset is deliberate -- it is the scope the response-model refactor drew --
not rot.

WHY IT MATTERS, concretely. `GET /api/holds/pending-approvals` was dead for as
long as it was shadowed, and the contract harness never noticed, because the
harness drives from GOLDEN'S KEYS and that route is not one of them. It was
found by scanning the route table for a registration-order property, not by
capture. A route absent from the golden master is invisible to every gate
built on it.

NOT a bug and NOT fixed here: expanding the golden master to all 460 routes is
a scope decision with real cost (each new entry needs resolvable params, and
some need bodies), and it belongs to whoever decides how far the contract
should reach. Recorded so the 164 is understood as a choice rather than
mistaken for coverage.


## FINDING: the attendance OT-split e2e test permanently consumes a fixture per run

`frontend/e2e/attendance-labor-allocation.spec.ts` seeds its precondition via
`seedExistingAttendanceEntry()`, which POSTs a real ATTENDANCE_ENTRY row and
never removes it -- the spec has a `beforeEach` and no `afterEach`.

The pool it draws from is exactly the logged-in user's own client. Measured on
the local demo DB: `demo_operator` -> client `DEMO-PIECE` -> 8 eligible active
employees. The helper needs one with no entry for today + `shifts[0]`, so the
spec can run at most 8 times per calendar day before setup fails with
"the logged-in user's own client needs a shift and at least one employee with
no attendance entry for it today".

WHY CI NEVER SEES IT: CI builds a fresh database per run, so the pool is always
full. The defect is invisible to the gate and only bites repeated local runs --
which is precisely when someone is debugging a grid change and needs the spec
most. It also mimics a product regression: the failure names the setup helper,
not the exhausted pool, so the first read is "the seeder broke".

NOT a bug in the app and NOT caused by the AG Grid v36 migration -- confirmed
by mutation-testing the migrated selector (the guard fires with its own message)
and by the fact that all three touched specs passed 13/13 on the final code
before the pool ran dry.

FIXED on branch `fix/attendance-e2e-idempotent` (its own PR, stacked on the AG
Grid bump). The spec now tears the row down in an `afterEach`. Two wrinkles the
implementation had to account for:

  - DELETE /api/attendance/{id} requires supervisor-or-above and the spec runs
    as an operator, so the teardown authenticates separately as `demo_admin`.
  - The endpoint only SOFT-deletes. That is sufficient because a global
    `do_orm_execute` listener (`backend/db/soft_delete_filter.py`) applies
    `with_loader_criteria` to hide inactive rows from every ORM read, including
    the existence check the seeder uses -- verified, not assumed.

PROVEN, not asserted: with the teardown, five consecutive runs left the free-
employee count at 7 and soft-deleted all five rows they created. Mutation test
-- disabling the teardown -- drops the count from 8 to 7 on a single run, so the
gate is load-bearing.

LOCAL CLEANUP DONE: the 8 residue rows (plus 14 orphan-able
ATTENDANCE_HOUR_ALLOCATION children) were removed after backing the database up;
entry count went 16648 -> 16640 exactly, with zero orphaned allocations.


## OBSERVATION: soft-deleting an attendance entry leaves its hour allocations behind

Surfaced by cross-model review of the e2e teardown above, then measured: 12
ATTENDANCE_HOUR_ALLOCATION rows currently sit attached to soft-deleted parents.

This is PRODUCT behaviour, not a test defect. `ATTENDANCE_HOUR_ALLOCATION` has
only `allocation_id`, `attendance_entry_id`, `category`, `hours` -- no
`is_active`, so it is not a soft-deletable entity and the cascade in
`db/soft_delete_service.py` cannot reach it. `DELETE /api/attendance/{id}`
therefore always leaves the children, in production exactly as in tests.

The rows are inert rather than corrupt: the FK still resolves, and the global
`do_orm_execute` filter hides the parent, so any join through the parent yields
nothing. Nothing reads them today.

DELIBERATELY NOT "FIXED" IN THE TEST. The teardown calls the product's own
DELETE endpoint; making it reach past the API into the database to delete more
than the product does would hide this behaviour rather than record it. If the
accumulation is judged undesirable, the fix belongs in the delete path -- either
give the table soft-delete columns so the cascade covers it, or hard-delete the
children when the parent is soft-deleted -- not in a spec.


## FINDING: the contrast checker uses gradient stops raw, never composited

Raised by cross-model review of the v36 contrast fix (#260) and adjudicated as
PRE-EXISTING, not a regression from that change.

`findViolations` treats every gradient stop as an opaque background. A
semi-transparent stop is scored as if it were solid instead of being composited
over whatever sits behind it, and fully-transparent stops are dropped outright
by the `c.a > 0` filter.

CONCRETE FALSE NEGATIVE. An element whose own gradient is
`linear-gradient(rgba(0,0,0,.2), rgba(0,0,0,.2))` over a white ancestor is
scored as white-on-black -- 21:1, a clean pass -- when what a user actually sees
is white on light grey at roughly 1.6:1, a hard WCAG-AA failure. Likewise a
`#000 -> transparent` gradient keeps only the black stop and ignores the light
background showing through the transparent end.

WHY IT IS PRE-EXISTING. The line before #260 read
`candidates = stops.length ? stops : [solidBg]`, drawing `stops` from the same
`.filter((c) => c.a > 0)`. Uncomposited stops and dropped transparent stops were
already the behaviour. #260 changed only WHICH gradient's stops win -- the
element's own rather than any ancestor's, i.e. the one actually in front -- and
did not touch how stops are combined with what is behind them.

FIXED on branch `fix/contrast-composite-gradient-stops`, as its own PR.

`collectSamples` now records each gradient with the DEPTH of the node carrying
it, so a stop can be composited over `effectiveBg(bgStack.slice(depth))` -- the
surface it is actually painted on. Transparent stops then need no special case:
compositing one yields its base, which is exactly what shows through.

THE SWEEP THAT JUSTIFIED IT, run before writing the fix: across all 15 audited
screens in both themes there are 86 gradient-carrying elements and 172 stops, of
which ZERO are translucent and ZERO use a syntax the collector cannot read
(computed styles serialise to rgb()). So the fix changes no current result --
it closes a class that would pass silently the first time someone ships a
translucent overlay. The census was itself checked for vacuity: it reports the
totals it scanned, not just the hits.

TWO FALSE POSITIVES WERE INTRODUCED AND CAUGHT BEFORE MERGE, both from getting
the layer order wrong, and both now pinned by tests:
  - offering deeper layers as extra worst-case candidates -- an
    `rgba(0,0,0,.8)` gradient over a white ancestor is dark grey that white
    text reads fine against, and scoring that white separately fails a correct
    control;
  - skipping translucent background-colors NEARER than the surface the walk
    settles on -- same error mirrored, it flagged readable white text sitting
    on a dark scrim.

ALSO CLOSED, found by the same review: only the STOP colours were scored, but a
gradient renders every colour between them and the worst contrast can fall
strictly in between. `#767676` text on a black-to-white gradient clears AA at
both ends (4.62:1 on black, 4.54:1 on white) and collapses to 1.15:1 against
the mid grey.

The first attempt at this -- a fixed 8-step grid -- was itself shown unsound by
the next review round, and the counterexample was reproduced numerically before
being believed: black text on `rgb(251,0,251) -> rgb(0,251,0)` reads >= 4.52 at
every eighth of the ramp yet dips to 4.4666 at t ~ 0.3235. A grid steps over
minima. What ships instead brackets with a coarse scan and then refines by
golden-section search, which converges because relative luminance along a stop
pair is convex (checked numerically over the ramp, min second difference
8.2e-07).

Pinning that gate needed care: `ratio` is rounded to 2dp, so both the refined
and the coarse answers print 4.47 and an assertion on the ratio proves nothing.
The test asserts `bgUsed` instead -- refinement lands on rgb(170,81,170), the
coarse grid on rgb(167,84,167) -- and only then does disabling refinement fail
the test.

A further round objected that golden-section assumes a unimodal minimum while
the contrast RATIO is not always one (where background luminance crosses the
foreground's there are two minima with a local maximum between). The refined
point is therefore accepted only when it beats the coarse scan, so the search
is monotonically no worse than the grid. Honest scope of that guard: a
40k-case random search over opaque stop pairs put the largest regression at
3e-6, float noise, so it is belt-and-braces rather than a fix for an observed
failure -- and it is NOT mutation-proven, because no input distinguishes it.
The invariant is pinned by a 120-case property test instead, which asserts the
reported ratio never beats a plain grid and counts the violations it actually
exercised so it cannot pass vacuously.

This only ADDS candidates, so it was checked against the live gate rather than
assumed safe: light and dark still pass, because every gradient the app ships is
a pair of near-identical colours.

KNOWN LIMITS, documented in the code rather than papered over: a translucent
gradient stacked over ANOTHER gradient composites over the solid stack, because
`effectiveBg` sees background-colors only; a gradient whose stops are all
unreadable (oklch, oklab) contributes nothing and the walk carries on; a
comma-separated multi-layer `background-image` has its stops flattened (all 86
elements ship a single layer); and `url(...)` backgrounds remain invisible to
the collector, which is pre-existing.


## FINDING: the scenario comparison sends its numbers as JSON STRINGS

Surfaced the moment `POST /api/capacity/scenarios/compare` became reachable
(the seeder now writes `capacity_scenario`, so the route finally answers with
data instead of `[]`). Measured against a seeded database, not inferred:

    "original_capacity_hours": "0.0",   <- string
    "capacity_increase_percent": "0",   <- string
    "cost_impact": "0.0",               <- string
    "scenario_id": 2,                   <- number
    "bottlenecks_resolved": 0           <- number

Six of the eleven fields are Decimal-typed and every one of them serialises as
a string. This is the repo's known `-> Any` mechanism: an annotated return runs
through Pydantic, which renders Decimal as a string, while only an unannotated
handler reaches `decimal_encoder`. Same class as the KPI serialisation fix that
shipped in #145 for five fields on other routes.

WHY IT MATTERS: a caller has to `Number()`-coerce six fields or arithmetic on
them silently concatenates. The golden master records field PATHS, not types, so
the contract harness cannot see this and will not catch it changing.

NOT FIXED HERE. The fix is to give the route a response model with float-typed
fields, which also closes its `ALLOWLIST` entry ("routes still awaiting a
response model"). That is an API-typing change with its own OpenAPI surface to
regenerate, and it belongs beside the other five allowlist entries of the same
shape rather than riding along with a seeding change.

## RESOLVED (#265, 2026-09-01) — the seeded comparison is structurally real but numerically zero

Closed by seeding the capacity workbook: all 13 `capacity_*` tables now hold
data, so the scenarios are applied to a real capacity. Measured after: analysis
capacity 2674h against demand 2546h, utilisation 95.2%, one bottleneck; the
OVERTIME plan takes utilisation to 79.3% (+20%, resolves the bottleneck) while
SETUP_REDUCTION reaches 92.4% (+3%, resolves none). The original text follows.

### (original observation)

The same probe shows every capacity figure is 0: `original_capacity_hours`
"0.0", `modified_capacity_hours` "0", `capacity_increase_percent` "0".

The scenarios themselves are real -- two per client, correct types, parameters
the service reads -- and the RESPONSE is real: two rows, eleven fields each, so
the captured contract is genuine and is not the empty-list trap the deferral
warned about. What is zero is the capacity the scenarios are applied TO.
`analyze_capacity` derives it from line capacity and schedules, and the 13
`capacity_*` tables other than `capacity_scenario` are still unseeded, so there
is nothing for a 20% overtime uplift to be 20% OF.

CONSEQUENCE, stated plainly: the contract goal is met and the demo's what-if
screen is no longer empty, but it will show every plan delivering a 0% capacity
increase. Making those numbers mean something needs `capacity_schedule` and the
line-capacity tables seeded -- a materially bigger scope than this change, and
its own decision about how much of the capacity module the demo should model.


## FINDING: capacity analysis divides by the shift count twice

`CapacityAnalysisService._get_calendar_data` derives hours-per-shift as:

    avg_hours       = total_hours / total_shifts     # already PER SHIFT
    hours_per_shift = avg_hours / avg_shifts         # divided per shift AGAIN

so a calendar declaring 2 shifts of 8h + 4h contributes 3 hours per shift where
12 hours per day were declared. `_calculate_line_capacity` then multiplies
`working_days * shifts_per_day * hours_per_shift`, giving 23 * 2 * 3 = 138
gross hours where the calendar says 23 * 12 = 276.

MEASURED, not inferred: seeded capacity came out at 58.1 h per line-day, and
58.1 = 2 shifts * 3h * 0.85 efficiency * 0.95 attendance * 12 operators
reproduces it exactly. The correct figure would be double.

WHO IS AFFECTED: every capacity figure the app reports understates by a factor
of `shifts_per_day` for any client running more than one shift. A single-shift
calendar is unaffected (dividing by 1 twice is still 1), which is presumably
why it has not been noticed.

NOT FIXED HERE. Correcting it moves every capacity number, every utilisation
percentage and every scenario comparison, so it needs its own before/after
measurement and its own review -- shipping it inside a seeding change would
mean an unmeasured change to the numbers a planner reads. The seeder
deliberately MIRRORS the current arithmetic when sizing the demo schedule
(`emitters_capacity.py`, the block above `units_per_line_day`) so utilisation
lands where intended against what the app actually reports; that constant is
where the seed needs revisiting when the service is corrected.
