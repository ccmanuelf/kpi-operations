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

from typing import Dict, List

from sqlalchemy import func, select, table

from backend.tests.contract.capture import capture_isolated, was_never_reached
from backend.tests.contract.conftest import _Harness
from backend.tests.contract.param_specs import NEVER_404, REGISTRY, Kind

BLOCKED_ROUTES = frozenset(
    {
        "DELETE /api/break-times/{break_id}",
        "DELETE /api/coverage/{coverage_id}",
        "DELETE /api/equipment/{equipment_id}",
        "DELETE /api/filters/{filter_id}",
        "DELETE /api/floating-pool/{pool_id}",
        "DELETE /api/jobs/{job_id}",
        "DELETE /api/part-opportunities/{part_number}",
        "DELETE /api/v2/simulation/scenarios/{scenario_id}",
        "GET /api/jobs/{job_id}/dpmo",
        "GET /api/jobs/{job_id}/efficiency",
        "GET /api/jobs/{job_id}/kpi-summary",
        "GET /api/jobs/{job_id}/performance",
        "GET /api/jobs/{job_id}/ppm",
        "GET /api/jobs/{job_id}/yield",
        "GET /api/qr/job/{job_id}/image",
    }
)


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
        if REGISTRY.get(exc.key) is None or REGISTRY[exc.key].kind is not Kind.BLOCKED
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
    specs = [REGISTRY[exc.key] for exc in harness.plan.blocked.values() if exc.key in REGISTRY]
    blocked_tables = sorted({spec.table for spec in specs if spec.table})
    # `select(func.count()).select_from(table(name))` rather than an f-string
    # SQL literal: the name comes from our own REGISTRY, but interpolating it
    # is a B608 finding that would have to be silenced with a bandit
    # suppression comment, and SQLAlchemy quotes the identifier correctly for
    # either dialect anyway.
    with harness.engine.connect() as conn:
        counts = {name: conn.execute(select(func.count()).select_from(table(name))).scalar() for name in blocked_tables}

    assert counts == {
        "BREAK_TIME": 0,
        "EQUIPMENT": 0,
        "FLOATING_POOL": 0,
        "JOB": 0,
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
    assert len(succeeded) == 30
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
