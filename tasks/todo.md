# Tasks

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


## NEXT: `DELETE /api/filters/history` is unreachable (route shadowing)

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
