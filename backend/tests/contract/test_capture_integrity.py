"""Can the capture itself be trusted?

`test_golden_master.py` asks whether any route stopped sending a field. It
can only answer that if the capture ASKED each route the right question, and
before Task 8b it did not: every path-param route was requested with literal
braces in the URL, so 63 entries recorded what
`/api/workflow/statistics/%7Bclient_id%7D/status-distribution` returns.

This module gates the machinery that fixed it, because almost none of it is
visible in the golden file:

  * no requested URL still carries a brace;
  * the routes no id can reach are exactly the declared manifest, and their
    tables are still empty (so improving the seeder forces a promotion rather
    than being silently ignored);
  * a route was blocked only by a DECLARED gap, never by a seeder regression;
  * the snapshot restore between mutations actually happens -- removing it
    leaves all 164 golden entries byte-identical;
  * and a 2xx really is proof the id was right, except on the seven routes
    where it provably is not.

Every one of those would pass silently if the mechanism under it were
removed, which is why they are asserted here rather than trusted to show up
as a shape diff.
"""

from __future__ import annotations

import json

from typing import Dict, List

from sqlalchemy import func, select, table

from backend.tests.contract.capture import capture_isolated, was_never_reached
from backend.tests.contract.conftest import GOLDEN, _Harness
from backend.tests.contract.param_specs import MUTATING_METHODS, NEVER_404, REGISTRY, Kind
from backend.tests.contract.query_specs import QUERY_REGISTRY

#: The routes whose answer no resolvable value can make meaningful, because a
#: table they read has zero seeded rows. 8, from 7.
#:
#: This set may only shrink BY PROMOTION -- a route leaving it means the
#: seeder started writing its table -- and a route joining it is a finding
#: that must say which of two things happened. Losing reachability is the bad
#: one. `GET /api/capacity/kpi/variance` is the other: it was never reachable,
#: it recorded `<status:422>`, and that status was the HARNESS's omission (no
#: `client_id` was supplied), not the route's answer. Supplying one shows
#: `calculate_variance_detailed` returning `[]` for every client, because
#: CAPACITY_KPI_COMMITMENT is empty -- so the honest record is a declared gap
#: with a staleness gate, not an empty shape that would look like a captured
#: contract. See `query_specs.QUERY_REGISTRY["client_id@capacity-variance"]`.
#:
#: 7 was itself down from 15: seeding JOB (S3) promoted `job_id` out of
#: `Kind.BLOCKED` and with it all eight routes it reached -- the six
#: `GET /api/jobs/{job_id}/*` KPI routes, `DELETE /api/jobs/{job_id}` and
#: `GET /api/qr/job/{job_id}/image`.
BLOCKED_ROUTES = frozenset(
    {
        "DELETE /api/break-times/{break_id}",
        "DELETE /api/coverage/{coverage_id}",
        "DELETE /api/equipment/{equipment_id}",
        "DELETE /api/filters/{filter_id}",
        "DELETE /api/floating-pool/{pool_id}",
        "DELETE /api/part-opportunities/{part_number}",
        "DELETE /api/v2/simulation/scenarios/{scenario_id}",
        "GET /api/capacity/kpi/variance",
    }
)


def _spec_for(key: str):
    """The spec behind a blocked route's key, from EITHER registry.

    A path param and a required query param can both block a route, and they
    are declared in different modules for the same reason `param_specs.py`
    and `param_resolution.py` are split. Looking in only one of them is how a
    gate goes quietly vacuous: `test_every_blocked_spec_still_has_zero_rows`
    filtered on `key in REGISTRY`, so the first query-side BLOCKED spec would
    have been skipped -- silently dropping the very staleness promise the
    declaration makes.
    """
    return REGISTRY.get(key) or QUERY_REGISTRY.get(key)


def test_no_captured_url_contains_an_unresolved_path_param(harness: _Harness) -> None:
    """The defect this task repairs, pinned at the plan level.

    Every path-param route used to be requested as
    `/api/workflow/statistics/%7Bclient_id%7D/status-distribution` and its
    answer recorded as if a real client had been asked. `capture_all` now
    raises on a braced URL, but that guard only fires for routes the plan
    actually issues; this one covers the plan itself, so a resolver that
    starts returning the template unchanged fails with the route named rather
    than with a shape diff 60 entries wide.
    """
    braced = {route: url for route, url in harness.plan.urls.items() if "{" in url or "}" in url}

    assert braced == {}


def test_blocked_routes_are_exactly_the_declared_manifest(harness: _Harness) -> None:
    """No surprises in either direction.

    An UNLISTED blocked route means the capture silently stopped reaching
    something it used to reach. A listed route that is no longer blocked means
    the seeder started writing its table and the spec must be promoted out of
    `Kind.BLOCKED` -- without this half, seed coverage improves and the harness
    keeps skipping routes it could now capture. That is the failure mode
    section 5.5 of the resolution map calls "rotting into folklore".
    """
    assert frozenset(harness.plan.blocked) == BLOCKED_ROUTES


def test_no_route_was_blocked_by_anything_but_a_declared_gap(harness: _Harness) -> None:
    """A blocked route must be blocked by a DECLARED gap, and the failure must
    say which kind it was.

    `UnresolvableParam` covers two unrelated situations. A `Kind.BLOCKED` spec
    is an expected, documented gap: the table has no rows and Task 8d will add
    them. A `Kind.SEEDED_ROW` spec that finds no row is a SEEDER REGRESSION --
    a table the seeder is supposed to write and stopped writing -- and
    `Resolver.resolve` raises it with a deliberately different, louder message
    for exactly that reason.

    Without this test the two collapse: the manifest gate notices that the set
    of blocked routes changed, but reports it as a manifest mismatch, pointing
    the reader at the declaration rather than at the seeder. This asserts on
    the SPEC KIND, not on message text, and puts `exc.reason` in the failure
    output so the louder message is the first thing read.
    """
    undeclared = {
        route: exc.reason
        for route, exc in harness.plan.blocked.items()
        if _spec_for(exc.key) is None or _spec_for(exc.key).kind is not Kind.BLOCKED
    }

    assert undeclared == {}


def test_every_blocked_spec_still_has_zero_rows(harness: _Harness) -> None:
    """The staleness half of the gate, asserted against the seeded database
    rather than against a comment. Each blocked spec claims its table is
    empty; the moment Task 8d seeds `JOB`, `EQUIPMENT`, `BREAK_TIME` or any
    other of them, this goes red and forces the promotion.
    """
    # `if spec.table` narrows away the Optional; that a BLOCKED spec always
    # HAS a table is gated separately by
    # test_param_resolution.test_row_backed_specs_name_the_table_they_read,
    # so a None here cannot silently shrink this set unnoticed.
    specs = [spec for spec in (_spec_for(exc.key) for exc in harness.plan.blocked.values()) if spec is not None]
    blocked_tables = sorted({spec.table for spec in specs if spec.table})
    # `select(func.count()).select_from(table(name))` rather than an f-string
    # SQL literal: the name comes from our own REGISTRY, but interpolating it
    # is a B608 finding that would have to be silenced with a bandit
    # suppression comment, and SQLAlchemy quotes the identifier correctly for
    # either dialect anyway.
    with harness.engine.connect() as conn:
        counts = {name: conn.execute(select(func.count()).select_from(table(name))).scalar() for name in blocked_tables}

    # JOB is absent since S3 seeded it: its spec is no longer BLOCKED, so it is
    # no longer one of the tables this gate counts. The staleness claim it used
    # to make here is now made in the opposite direction by
    # tests/test_seed/test_coverage.py, which fails if JOB has NO rows.
    assert counts == {
        # Not a param gap: `client_id` resolves fine on GET /api/capacity/kpi/
        # variance. This table being empty is what makes its answer `[]`, and
        # counting it here is what turns "seed some commitments and the route
        # becomes capturable" from a note into a failing test.
        "CAPACITY_KPI_COMMITMENT": 0,
        "BREAK_TIME": 0,
        "EQUIPMENT": 0,
        "FLOATING_POOL": 0,
        "PART_OPPORTUNITIES": 0,
        "SAVED_FILTER": 0,
        "SIMULATION_SCENARIO": 0,
        "shift_coverage": 0,
    }


def _request(route: str) -> tuple:
    method, path = route.split(" ", 1)
    return (method, path, {})


def test_the_isolated_phase_restores_between_mutations(harness: _Harness, captured_shapes) -> None:
    """The snapshot restore is the largest new mechanism in this harness, and
    the golden file cannot see it.

    Disabling it leaves all 164 entries byte-identical, because the only
    collisions available today are masked by the `soft_delete()` bug that makes
    seven DELETEs 404 for any id -- and most of the DELETEs that DO succeed are
    soft deletes, so repeating them still answers 204. A mechanism whose
    absence looks exactly like its presence is gated by nothing, so this drives
    `capture_isolated` directly against the two genuinely non-idempotent routes
    in the plan, once with the real restore and once with a no-op.

    `DELETE /api/kpi-thresholds/{client_id}/{kpi_key}` HARD-deletes its row:
    200 `{message}` first, 404 forever after. `capture_all` keys by route
    template, so running it twice records the SECOND answer -- which is the
    real shape if and only if the database was restored in between.

    `POST /api/work-orders/{work_order_id}/approve-qc` is the sharper of the
    two, because it does not fail loudly: approving an already-approved work
    order answers 200 and silently DROPS the `message` key. That is a golden
    entry quietly losing a field to a neighbouring route -- precisely the class
    of accident this whole task exists to remove, reproduced one layer down.

    Boundary, stated rather than discovered later: this gates the `restore()`
    call inside `capture_isolated`, which is the only one in the capture path.
    It cannot catch a fixture rewired to pass a no-op in place of
    `harness.restore`; that would need the module-scoped capture to be re-run.
    """
    thresholds = "DELETE /api/kpi-thresholds/{client_id}/{kpi_key}"
    approve_qc = "POST /api/work-orders/{work_order_id}/approve-qc"
    urls = harness.plan.urls
    approved = ["message", "qc_approved", "qc_approved_by", "qc_approved_date", "status", "work_order_id"]

    try:
        harness.restore()
        twice_restored = capture_isolated(
            harness.client, [_request(thresholds)] * 2, urls, harness.restore
        ) | capture_isolated(harness.client, [_request(approve_qc)] * 2, urls, harness.restore)

        harness.restore()
        twice_unrestored = capture_isolated(
            harness.client, [_request(thresholds)] * 2, urls, lambda: None
        ) | capture_isolated(harness.client, [_request(approve_qc)] * 2, urls, lambda: None)
    finally:
        harness.restore()

    assert twice_restored == {thresholds: ["message"], approve_qc: approved}
    # The control: without the restore both routes record something else, so
    # the assertion above is not passing because these routes are inert.
    assert twice_unrestored == {thresholds: ["<status:404>"], approve_qc: approved[1:]}


def test_a_2xx_is_proof_the_id_was_right_except_where_declared(
    harness: _Harness,
    captured_shapes: Dict[str, List[str]],
    bogus_id_shapes: Dict[str, List[str]],
    bogus_urls: Dict[str, str],
) -> None:
    """The brief's requirement: the harness must not treat a 200 as proof the
    id was right, but record per route whether it is.

    Every path-param route whose capture SUCCEEDED (anything but a
    `<status:...>` placeholder -- a real shape, or `<non-json>` for a 204 or a
    PNG) is re-requested with an id that cannot exist. Two sides, and both are
    load-bearing:

    - a route NOT in `NEVER_404` must DISCRIMINATE. If it stops, its golden
      entry has quietly become an entry any id would have produced, and
      nothing else in this harness would notice.
    - a route IN `NEVER_404` must still be id-INSENSITIVE. If it starts
      discriminating, the declaration is stale and is suppressing a real check.

    A one-sided version of this test passes with `NEVER_404` empty, which is
    exactly the state this test exists to make impossible.
    """
    succeeded = {
        route: shape for route, shape in captured_shapes.items() if "{" in route and not was_never_reached(shape)
    }
    id_insensitive = {route for route, shape in succeeded.items() if bogus_id_shapes[route] == shape}

    assert id_insensitive == NEVER_404
    # 44, up from 36: S3 seeds JOB, which made eight routes resolvable. Seven
    # of them landed here -- the six GET /api/jobs/{job_id}/* KPI routes plus
    # GET /api/qr/job/{job_id}/image, whose PNG records `<non-json>`, itself a
    # success. (DELETE /api/jobs/{job_id} does NOT: it answers 409, because a
    # seeded job's work order is not deletable while the job exists.) The
    # eighth is GET /api/work-orders/{work_order_id}/rty, which was reachable
    # all along and answered 404 only because the order had no jobs to compute
    # a rolled-throughput yield from. This number may only go UP without a
    # stated reason: a drop means a route stopped being capturable.
    #
    # 48, up from 44: supplying required QUERY params (`query_specs.py`) made
    # four more path-param routes answer at last --
    # GET /api/attendance/kpi/bradford-factor/{employee_id},
    # GET /api/kpi/{metric}/cause, GET /api/pivot/{dataset} and
    # GET /api/pivot/{dataset}/csv (whose CSV stream records `<non-json>`,
    # itself a success). All four DISCRIMINATE, and the probe is only entitled
    # to say so because it re-requests them WITH the same query params: without
    # them every probe answers 422 for the missing params and the difference
    # would prove nothing about the id. See `CapturePlan.kwargs`.
    # 50, up from 48: two more path-param routes answer now that the
    # write-capture deferral shrank to routes that actually need a request
    # body (`DEFERRED_TO_WRITE_CAPTURE`) --
    # POST /api/workflow/config/{client_id}/apply-template and
    # POST /api/workflow/work-orders/{work_order_id}/validate.
    #
    # apply-template arriving here is what caught a product bug: it answered
    # the SAME 200 for a real client and for NO-SUCH-CLIENT-XYZ, because both
    # workflow-config write paths did `ClientConfig(client_id=client_id)` on a
    # miss and created a row for a client that did not exist. Guarded now by
    # `crud/workflow/configuration._require_client`, so the route discriminates
    # and needs no NEVER_404 entry -- see
    # tests/test_crud/test_workflow_config_requires_client.py.
    # 51, up from 50: `PUT /api/workflow/config/{client_id}` answers now that
    # write capture sends it a body (`body_specs.BODY_REGISTRY`). It is the only
    # one of the four new body routes carrying a path param, so it is the only
    # one this count sees.
    # 53, up from 52: `POST /api/defect-types/upload/{client_id}` answers now
    # that the registry can express a multipart body. It is the only one of the
    # three routes un-deferred alongside it that carries a path param.
    #
    # It arrived here id-INSENSITIVE -- the same 200 for a real client and for
    # NO-SUCH-CLIENT-XYZ, with the DEFECT_TYPE_CATALOG row written either way.
    # Guarded now in `crud/defect_type_catalog.py`, so it discriminates and
    # needs no NEVER_404 entry.
    assert len(succeeded) == 53
    # Third side, and the one that keeps the other two honest: a route whose
    # probe URL equals its real URL was compared against ITSELF, so it lands in
    # `id_insensitive` for free and its NEVER_404 membership proves nothing.
    # This is reachable -- `bogus_url_for` deliberately does not substitute a
    # LITERAL param unless its spec declares a `bogus` value, so dropping
    # `{pattern}`'s would silently turn the cache route into a vacuous pass.
    unprobed = sorted(route for route in succeeded if bogus_urls[route] == harness.plan.urls[route])

    assert unprobed == []


def test_never_404_entries_all_answered_2xx(captured_shapes: Dict[str, List[str]]) -> None:
    """`NEVER_404` is a claim about routes the harness actually reached. A
    member that never got a 2xx would satisfy the identity check in the test
    above trivially -- two placeholders comparing equal -- so the membership
    would read as verified while proving nothing.

    `was_never_reached`, not `is_status_only`: a mutation that added
    `GET /api/jobs/{job_id}/yield` (a `<blocked:job_id>` entry, never
    requested at all) to `NEVER_404` walked straight through the
    status-only version of this check. Blocked is the MORE vacuous of the two
    and was the one being missed.
    """
    unreached = {
        route: captured_shapes[route] for route in sorted(NEVER_404) if was_never_reached(captured_shapes[route])
    }

    assert unreached == {}


def test_no_mutating_route_is_captured_outside_the_isolated_phase(harness: _Harness) -> None:
    """`restore()` runs per request in the isolated phase and never in the read
    phase, so a mutating route planned into the read phase writes into the
    database every route captured after it will read.

    The predicate used to be `method in MUTATING_METHODS and "{" in path`.
    Carrying a path param is not what makes a route mutate, and twenty
    mutating routes have none -- four of which execute today, two of which
    write (`POST /api/metrics/calculate/run-nightly`,
    `POST /api/predictions/demo/seed`). No golden shape depended on their
    leftovers when this was corrected, so nothing was being answered wrongly;
    the ordering was simply free to start mattering at any time, and write
    capture is exactly the change that would make it.

    Asserted against the plan rather than the predicate so a future rewrite of
    the planning logic has to keep the property, not the expression.

    `POST /api/cache/clear` is worth naming, because `restore()` explicitly
    does not cover it: the boundary is the database file, and the cache it
    empties is in-process. Moving it still helps, for a reason that is about
    ORDER rather than restoration -- `captured_shapes` runs the read phase to
    completion first and the isolated phase after it, so a route in the
    isolated phase cannot affect anything captured in the read phase at all.
    What remains is that in-process state is not restored BETWEEN isolated
    requests either; no golden entry depends on cache contents today, and
    `capture_isolated`'s own docstring is where that limit is recorded.
    """
    misplaced = sorted(f"{method} {path}" for method, path, _ in harness.plan.requests if method in MUTATING_METHODS)

    assert not misplaced, (
        "mutating routes planned into the un-restored read phase, where their writes "
        f"leak into every later capture: {misplaced}"
    )


def test_the_isolated_phase_holds_exactly_the_mutating_golden_routes(harness: _Harness) -> None:
    """Guards the guard above, from the golden master rather than a count.

    Planning every route into `requests` would satisfy
    nothing-mutating-in-requests only by leaving `isolated` empty, and the
    restore-between-mutations test would then drive an empty list and pass on
    no work. A threshold like `>= 40` closes that but rots: once there are 41
    mutating routes, dropping one still clears the bar.

    So the expected set is DERIVED -- every mutating route in the golden
    master, minus the ones planning could not resolve (`plan.blocked`, which
    is itself gated by `test_blocked_routes_are_exactly_the_declared_manifest`).
    An omitted route now fails by name.
    """
    golden = json.loads(GOLDEN.read_text())
    expected = {
        route for route in golden if route.split(" ", 1)[0] in MUTATING_METHODS and route not in harness.plan.blocked
    }
    planned = {f"{method} {path}" for method, path, _ in harness.plan.isolated}

    assert planned == expected, {
        "planned but not expected": sorted(planned - expected),
        "expected but not planned": sorted(expected - planned),
    }
    assert planned, "no mutating routes planned at all -- the isolated phase would do no work"
