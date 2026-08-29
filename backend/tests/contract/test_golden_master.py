"""Did any route stop sending a field it used to send?

That is the whole question this module asks, and the golden master
(`golden/api_shapes.json`) is the answer it diffs against. The seeded
database, the authenticated client and the capture itself live in
`conftest.py`; whether that capture can be TRUSTED is
`test_capture_integrity.py`'s question, not this one.

Per the Task 4 handoff this is the SOLE safety net for the eight
`/api/kpi/*/trend` routes: `frontend_usage.KNOWN_BLIND` documents that the
frontend field-usage extractor cannot see them (structural, not a regex gap
-- see that module), and no e2e spec mentions `trend` or `chart`, so a chart
silently losing its data renders empty and every other gate stays green.

`MAX_STATUS_ONLY_ROUTES` and the known-good route below are the anti-vacuity
control: an auth-less capture records `<status:401>` for all 164 routes and
re-running it against itself reports "zero differences", so a zero-diff pass
is satisfiable by a worthless capture. These two make that failure mode fail
here instead of reading as success.
"""

from __future__ import annotations

import json
from typing import Dict, List

from backend.tests.contract.capture import is_placeholder, is_status_only
from backend.tests.contract.conftest import GOLDEN
from backend.tests.contract.frontend_usage import KNOWN_BLIND

# 35, down from 41: the six DELETEs that #239 fixed no longer record a bare
# `<status:404>`. This is a CEILING and must only fall -- it is the anti-vacuity
# control, so raising it to make a run pass would re-admit exactly the worthless
# capture it exists to reject.
MAX_STATUS_ONLY_ROUTES = 35


#: The 7 routes no id can reach, because their backing table has zero seeded
#: rows -- 15 until S3 seeded JOB and freed the eight `job_id` reached.
#: Pinned EXACTLY (in `test_capture_integrity.BLOCKED_ROUTES`), not as a
#: ceiling: a route dropping out of this set
#: means the seeder started writing its table and the route is now capturable
#: (promote its spec out of Kind.BLOCKED), while a route joining it means the
#: opposite -- something that used to be reachable no longer is. Both are
#: findings, and neither should pass silently. Reasons live in
#: `param_resolution.REGISTRY[key].reason`.
def test_no_route_lost_a_field(captured_shapes: Dict[str, List[str]]) -> None:
    """Compares KEY SETS, never value types. Changing a type is the point of
    this refactor -- "4" becoming 4 is success -- so a type-comparing golden
    master would fail on every intended change and be switched off within a
    day.
    """
    golden = json.loads(GOLDEN.read_text())

    for route, keys in golden.items():
        assert captured_shapes.get(route) == keys, f"{route} changed shape"


def test_a_known_good_trend_route_resolves_real_fields(captured_shapes: Dict[str, List[str]]) -> None:
    """Anti-vacuity control, half A.

    A zero-diff pass is also what a completely worthless capture -- 164
    identical `<status:401>` entries, see the module docstring's finding 1 --
    would report. Pinning one route to the shape it must resolve to when
    auth genuinely works means a regression back to that failure mode fails
    HERE instead of reading as success.
    """
    assert captured_shapes.get("GET /api/kpi/efficiency/trend") == ["[].date", "[].value"]


def test_status_only_routes_stay_under_the_measured_ceiling(captured_shapes: Dict[str, List[str]]) -> None:
    """Anti-vacuity control, half B.

    Half A alone would not catch a partial regression -- e.g. auth breaking
    for every route except the one pinned above. Counting how many of the
    164 recorded a status instead of a shape, and pinning that count, catches
    a harness that stops reaching routes it used to reach, whatever the
    cause (auth, db wiring, routing).
    """
    status_only = [route for route, shape in captured_shapes.items() if is_status_only(shape)]
    assert len(status_only) <= MAX_STATUS_ONLY_ROUTES


def test_no_known_blind_trend_route_recorded_only_a_status(captured_shapes: Dict[str, List[str]]) -> None:
    """The eight `/api/kpi/*/trend` routes are where this golden master
    matters most: `frontend_usage.KNOWN_BLIND` documents that the frontend
    extractor cannot see them, and no e2e spec mentions `trend` or `chart`.
    A `<status:...>` entry for any of them would mean the one net watching
    this cluster isn't actually reaching it.
    """
    for endpoint in sorted(KNOWN_BLIND):
        route = f"GET {endpoint}"
        # A missing entry (route dropped out of loose_routes(app) entirely --
        # e.g. it already picked up a real response_model) is exactly as
        # untrustworthy as a status-only one, so it is treated the same way
        # rather than raising an opaque KeyError.
        shape = captured_shapes.get(route, ["<status:MISSING>"])
        assert not is_status_only(shape), f"{route} recorded {shape}"


def test_no_route_regressed_from_a_real_shape_to_a_placeholder(captured_shapes: Dict[str, List[str]]) -> None:
    """Direction matters, and `test_no_route_lost_a_field` cannot say which
    way a route moved -- it reports "changed shape" for an improvement and a
    regression alike.

    A route whose golden entry is a real shape and whose capture is a
    `<status:...>`, `<blocked:...>` or `<non-json>` placeholder has lost every
    field it had. That direction is never acceptable churn: it means id
    resolution, auth or the seed got WORSE, and it must fail rather than be
    recaptured over.
    """
    golden = json.loads(GOLDEN.read_text())
    regressed = {
        route: captured_shapes.get(route, ["<status:MISSING>"])
        for route, keys in golden.items()
        if not is_placeholder(keys) and is_placeholder(captured_shapes.get(route, ["<status:MISSING>"]))
    }

    assert regressed == {}


def test_a_known_wrong_shape_entry_gained_its_nested_object(captured_shapes: Dict[str, List[str]]) -> None:
    """Anti-vacuity control for THIS task.

    Eight golden entries recorded a 200 shape for an entity whose id was the
    literal string `{client_id}`; those are worse than the 54 statuses,
    because they look like real answers. This is the sharpest of them: asked
    with real braces it recorded three keys, and `by_status` was one of them
    -- a bare name with nothing under it. Asked with a real client it carries
    an entire nested object. A response model built from the old entry would
    have dropped `status`, `count` and `percentage` from every response.

    Pinned exactly, so a regression to brace-requesting fails here with the
    reason visible instead of as one line in a wide diff.
    """
    assert captured_shapes.get("GET /api/workflow/statistics/{client_id}/status-distribution") == [
        "by_status[].count",
        "by_status[].percentage",
        "by_status[].status",
        "client_id",
        "total_work_orders",
    ]
