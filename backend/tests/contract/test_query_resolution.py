"""Gates on the REQUIRED QUERY PARAM layer -- `query_specs.py` (what) plus
`param_resolution.py`'s query half (how).

`test_param_resolution.py` and `test_capture_integrity.py` ask the same two
questions of the PATH registry, split pure-vs-seeded. This module keeps both
halves together because the query layer is small and because its two halves
answer one question between them: nine golden entries used to read
`<status:422>`, and a status placeholder is indistinguishable from a real
rejection. Both possible causes -- the route genuinely refusing, and the
harness never asking properly -- produce the identical entry, so the only way
to know which one happened is to ask properly and look. Eight of the nine were
the harness.

What each gate is here to stop, in the order they appear:

  * a NEW required query param on a golden route silently reinstating a
    `<status:422>` nobody reads;
  * the mutating routes being "temporarily" supplied query params and running
    unisolated inside the read pass;
  * an enum literal outliving the application's own vocabulary;
  * the id specs quietly forking into a second copy of the seeded SQL;
  * the date window drifting back onto the real clock, which is the expiry
    #245 removed;
  * and the id-sensitivity probe answering a question it never asked, by
    re-requesting a route WITHOUT the query params the capture used.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Dict, List

import pytest
from sqlalchemy import column, func, select, table

from backend.tests.contract.capture import SeededToday, capture_all, is_placeholder
from backend.tests.contract.conftest import GOLDEN, SEED_AS_OF, _Harness
from backend.tests.contract.param_resolution import (
    Resolver,
    UnresolvableParam,
    required_query_params,
    route_index,
)
from backend.tests.contract.param_specs import REGISTRY, Kind, MUTATING_METHODS
from backend.tests.contract.query_specs import (
    DEFERRED_TO_WRITE_CAPTURE,
    EFFECTIVELY_REQUIRED_QUERY_PARAMS,
    QUERY_REGISTRY,
    STATUS_IS_THE_ROUTES_OWN_ANSWER,
    WINDOW_DAYS,
)

#: The eight routes this layer took from `<status:422>` to a real captured
#: answer, and what each needed. Written out rather than derived so the gates
#: below compare the mechanism against a stated intent, not against itself.
#:
#: The ninth, `GET /api/capacity/kpi/variance`, is deliberately absent: its
#: `client_id` resolves, and the route still has nothing to say. It is
#: declared `Kind.BLOCKED` and lives in `test_capture_integrity.BLOCKED_ROUTES`.
UNBLOCKED: Dict[str, tuple] = {
    "GET /api/attendance/statistics/summary": ("start_date", "end_date"),
    "GET /api/attendance/kpi/bradford-factor/{employee_id}": ("start_date", "end_date"),
    "GET /api/quality/statistics/summary": ("start_date", "end_date"),
    "GET /api/quality/kpi/quality-score": ("product_id", "start_date", "end_date"),
    "GET /api/kpi/labor-hours": ("start_date", "end_date"),
    "GET /api/kpi/{metric}/cause": ("date",),
    "GET /api/pivot/{dataset}": ("bucket", "start_date", "end_date"),
    "GET /api/pivot/{dataset}/csv": ("bucket", "start_date", "end_date"),
    # Not FastAPI-required -- declared in EFFECTIVELY_REQUIRED_QUERY_PARAMS.
    # The tenant-narrowing this test warns about is what the route demands:
    # it refuses to answer without a client, and the step names it returns
    # are structural rather than per-tenant.
    "GET /api/onboarding/status": ("client_id",),
    # Mutating, and safe to ask now that every mutator is isolated (#249).
    "POST /api/hold-catalogs/seed-defaults": ("client_id",),
    "POST /api/attendance/mark-all-present": ("client_id", "shift_id", "shift_date"),
    "POST /api/floating-pool/simulation/shift-coverage": (
        "shift_id",
        "shift_name",
        "regular_employees",
        "floating_pool_available",
        "required_employees",
    ),
    "POST /api/workflow/config/{client_id}/apply-template": ("template_id",),
    "POST /api/workflow/work-orders/{work_order_id}/validate": ("to_status",),
}

VARIANCE = "GET /api/capacity/kpi/variance"


def _golden() -> Dict[str, List[str]]:
    data: Dict[str, List[str]] = json.loads(GOLDEN.read_text())
    return data


def _requirements() -> Dict[str, tuple]:
    """Every golden route that will not answer without query params, and which.

    Both sources, matching `Resolver.query_for` exactly. Reading only
    FastAPI's `dependant` here would let the gate and the harness disagree
    about what "required" means: `/api/onboarding/status` declares
    `Query(None)` and raises 400 in its own body, so a dependant-only view
    calls it unrequired, never asks for it to be accounted for, and leaves
    its `<status:400>` sitting in the golden master looking like an answer.
    That is the same defect this layer removes, one door over.
    """
    from backend.main import app

    index = route_index(app)
    found = {}
    for route_key in sorted(_golden()):
        required = list(required_query_params(index[route_key]))
        path = route_key.split(" ", 1)[1]
        for param in EFFECTIVELY_REQUIRED_QUERY_PARAMS.get(path, ()):
            if param not in required:
                required.append(param)
        if required:
            found[route_key] = tuple(required)
    return found


# ---------------------------------------------------------------- detection


def test_required_query_params_reads_both_declaration_forms():
    """The measurement this work started from missed one form, and it is the
    reason detection asks FastAPI instead of reading the signature.

    `start_date: date` states required-ness by having no default.
    `client_id: str = Query(..., description=...)` states it INSIDE a default
    -- so "has a default" reads as "optional" and the param disappears. Both
    forms are live in this codebase, one route each, and both are asserted
    here so a future switch to a signature scan fails rather than silently
    dropping the second.

    The third assertion is the one that keeps the harness from over-supplying:
    an OPTIONAL query param must NOT come back. `/api/attendance/statistics/
    summary` declares `shift_id` and `client_id` as optional; sending them
    would narrow the answer to one shift and one client and record THAT as the
    route's shape.
    """
    from backend.main import app

    index = route_index(app)

    # bare, no default
    assert required_query_params(index["GET /api/attendance/statistics/summary"]) == ("start_date", "end_date")
    # required-ness inside Query(...)
    assert required_query_params(index[VARIANCE]) == ("client_id",)
    # optional params are excluded, not merely deprioritised
    optional = {"shift_id", "client_id", "group_by", "product_id"}
    assert optional & set(required_query_params(index["GET /api/attendance/statistics/summary"])) == set()


def test_every_golden_route_with_required_query_params_is_accounted_for():
    """Two-sided, and the gate that stops this whole layer rotting.

    Every golden route that FastAPI says has required query params must be
    either resolved (`UNBLOCKED`, plus the blocked variance route) or declared
    deferred. A route added later with a required query param lands in neither
    and fails HERE, by name, instead of quietly recording a `<status:422>`
    that reads like the route's own answer -- which is exactly the state all
    nine of these entries were in.
    """
    accounted = set(UNBLOCKED) | {VARIANCE} | DEFERRED_TO_WRITE_CAPTURE

    assert set(_requirements()) == accounted


def test_the_declared_requirements_are_the_measured_ones():
    """`UNBLOCKED` claims which params each route needs. Compared against
    FastAPI's answer so the table cannot drift into decoration -- a route
    gaining a required param would otherwise leave this module describing a
    request the harness no longer sends."""
    measured = _requirements()

    assert {route: measured[route] for route in UNBLOCKED} == UNBLOCKED


def test_every_mutating_route_is_either_asked_or_owed_a_body():
    """The boundary, restated after the isolation fix.

    The rule used to be method-based: EVERY mutating route with required query
    params was deferred, because `capture_isolated` replayed only path-param
    mutations against a restored snapshot, so supplying params to a paramless
    POST would have run it inside the read pass, writes and all.

    That is no longer true. Every mutating route is now planned into the
    isolated phase (`test_no_mutating_route_is_captured_outside_the_isolated_
    phase`), so "it mutates" has stopped being a reason to leave it 422ing.
    What remains is the narrower reason the deferral was always really for:
    the route additionally wants a request BODY, which nothing here can build
    yet.

    So each mutating route with required query params must be exactly one of
    asked (`UNBLOCKED`) or owed a body (`DEFERRED_TO_WRITE_CAPTURE`), and the
    deferral has to be STRUCTURALLY justified -- a deferred route with no
    required body param is a route nobody got round to, declared as though it
    were blocked.
    """
    from backend.main import app

    index = route_index(app)
    mutating = {route for route in _requirements() if route.split(" ", 1)[0] in MUTATING_METHODS}

    assert DEFERRED_TO_WRITE_CAPTURE <= mutating, sorted(DEFERRED_TO_WRITE_CAPTURE - mutating)
    assert mutating == DEFERRED_TO_WRITE_CAPTURE | (mutating & set(UNBLOCKED)), {
        "neither asked nor deferred": sorted(mutating - DEFERRED_TO_WRITE_CAPTURE - set(UNBLOCKED)),
    }
    assert not (DEFERRED_TO_WRITE_CAPTURE & set(UNBLOCKED))

    unjustified = {
        route
        for route in DEFERRED_TO_WRITE_CAPTURE
        if not any(_is_required(param) for param in index[route].dependant.body_params)
    }
    assert not unjustified, (
        "deferred to write capture but needs no request body -- the isolation reason is gone, "
        f"so these are just unasked: {sorted(unjustified)}"
    )


# ------------------------------------------------------------- declarations


def test_every_query_spec_carries_exactly_what_its_kind_requires():
    """One `sql`, one `literal`, one `reason` or one `offset_days`, never two.

    The path registry's version of this gate (`test_param_resolution.py`) does
    not cover these specs, and the failure it prevents is the same: a
    SEED_WINDOW carrying a `literal` would return the hardcoded value and
    never read the pin, which is the drift the whole kind exists to remove.
    `offset_days=0` is legitimate, so membership is tested with `is not None`
    rather than truthiness -- the path version's truthiness check would call
    `end_date` unfilled.
    """
    expected = {
        Kind.SEEDED_ROW: ("sql",),
        Kind.LITERAL: ("literal",),
        Kind.BLOCKED: ("reason",),
        Kind.SEED_WINDOW: ("offset_days",),
    }
    for key, spec in sorted(QUERY_REGISTRY.items()):
        filled = tuple(
            sorted(name for name in ("sql", "literal", "reason", "offset_days") if getattr(spec, name) is not None)
        )

        assert filled == expected[spec.kind], f"{key} ({spec.kind}) filled {filled}"
        assert spec.key == key, f"{key} disagrees with its own .key ({spec.key})"


def test_the_id_specs_are_the_path_registry_s_own_objects():
    """Identity, not equality. The instruction was "reuse that machinery; do
    not build a second one", and a copied ParamSpec satisfies `==` while
    being a second place to fix when the seeder moves -- the failure would be
    a query param resolving to a row the path resolver no longer picks, with
    both registries looking correct in isolation.

    Sharing the object also shares `Resolver._cache`, so `product_id` is read
    back once whichever way it arrives.
    """
    assert QUERY_REGISTRY["product_id"] is REGISTRY["product_id"]


def test_enum_specs_reference_the_application_s_own_set():
    """`choices` must BE the app's object, not a value-equal copy.

    A copy passes a membership check forever, including after the app renames
    a member -- and the capture would then send a value the route 422s on and
    record that 422 as the answer, which is precisely the defect this layer
    removes. Identity is what makes the reference real.
    """
    from backend.pivot.buckets import VALID_BUCKETS

    assert QUERY_REGISTRY["bucket"].choices is VALID_BUCKETS
    assert QUERY_REGISTRY["bucket"].literal in VALID_BUCKETS


def test_a_stale_enum_literal_fails_loudly_rather_than_being_sent(monkeypatch):
    """The half identity cannot prove: that the membership check is WIRED.

    `choices` being the real object means nothing if nobody consults it. This
    swaps in a literal the application does not accept and requires the
    ordinary resolution path to raise -- without the check, the request goes
    out, the route 422s, and the golden master records that 422 as the route's
    contract, which is the exact defect this whole layer removes.
    """
    from dataclasses import replace

    resolver = Resolver(engine=None)  # no DB is touched on the LITERAL path
    path = "/api/pivot/{dataset}"

    # Control first: the raise below must be caused by the literal, not by
    # this code path being broken for every value.
    assert resolver.resolve_query("bucket", path) == "week"

    monkeypatch.setitem(QUERY_REGISTRY, "bucket", replace(QUERY_REGISTRY["bucket"], literal="fortnight"))

    with pytest.raises(UnresolvableParam) as raised:
        resolver.resolve_query("bucket", path)
    assert "not in the application's own accepted set" in raised.value.reason


def test_a_query_family_with_no_matching_route_raises():
    """Same rule as `FAMILY_ROUTER`: a routed param name whose route matches
    no fragment must RAISE. `client_id` is routed because one route's answer
    is empty for every client; a second capacity route appearing with a
    required `client_id` must be a deliberate declaration, not a silent reuse
    of the blocked spec (which would record `<blocked:...>` for a route that
    can answer perfectly well).
    """
    from backend.tests.contract.param_resolution import query_spec_key

    assert query_spec_key("client_id", VARIANCE) == "client_id@capacity-variance"
    with pytest.raises(UnresolvableParam) as raised:
        query_spec_key("client_id", "/api/capacity/kpi/commitments")

    assert "QUERY_FAMILY_ROUTER" in raised.value.reason


# ------------------------------------------------------------------- clock


def test_the_window_is_anchored_on_the_seed_and_not_on_the_calendar(monkeypatch):
    """The expiry #245 removed, kept removed.

    A window off `date.today()` covers the seed today and stops covering it
    later, with nothing in the repo having changed -- the entries would flip to
    their empty branch on a date. This proves the anchor is the SEED's today by
    moving that pin and requiring the resolved values to move with it by the
    same amount, which a real-clock implementation would not do.
    """
    resolver = Resolver(engine=None)  # SEED_WINDOW never touches the DB
    path = "/api/kpi/labor-hours"

    # Pinned here rather than borrowed from the `harness` fixture: this test
    # must be able to MOVE the pin, and a test that only works when some other
    # fixture happened to run first is not testing the anchor.
    monkeypatch.setattr(SeededToday, "AS_OF", SEED_AS_OF)

    at_seed = (resolver.resolve_query("start_date", path), resolver.resolve_query("end_date", path))
    assert at_seed == ((SEED_AS_OF - timedelta(days=WINDOW_DAYS)).isoformat(), SEED_AS_OF.isoformat())

    moved = SEED_AS_OF - timedelta(days=365)
    monkeypatch.setattr(SeededToday, "AS_OF", moved)

    assert resolver.resolve_query("end_date", path) == moved.isoformat()
    assert resolver.resolve_query("start_date", path) == (moved - timedelta(days=WINDOW_DAYS)).isoformat()


def test_an_unpinned_clock_refuses_to_resolve_a_window(monkeypatch):
    """No silent fallback. `SeededToday` raises when `AS_OF` is unset, and the
    query resolver must not paper over it with `date.today()` -- a fallback
    would reinstate the drift while every test above still passed."""
    monkeypatch.setattr(SeededToday, "AS_OF", None)
    resolver = Resolver(engine=None)  # SEED_WINDOW never touches the DB

    with pytest.raises(AssertionError, match="AS_OF is unset"):
        resolver.resolve_query("end_date", "/api/kpi/labor-hours")


# -------------------------------------------------------------- the capture


def test_the_window_actually_covers_the_seeded_rows(harness: _Harness):
    """`WINDOW_DAYS` claims to be wide enough. Measured against the DATABASE,
    every run, rather than believed: a seed profile that widened its span past
    the window would otherwise quietly start capturing a partial answer, which
    a shape-recording golden master cannot see.
    """
    start = SEED_AS_OF - timedelta(days=WINDOW_DAYS)
    spans: Dict[str, tuple] = {}
    with harness.engine.connect() as conn:
        for name in ("ATTENDANCE_ENTRY", "QUALITY_ENTRY", "PRODUCTION_ENTRY"):
            # Built through SQLAlchemy core rather than an f-string, the same
            # way `test_capture_integrity`'s row-count gate is: the names are
            # our own literals, but interpolating them is a bandit B608 finding
            # that would need a suppression comment, and core quotes the
            # identifier correctly for either dialect anyway.
            rows = table(name, column("shift_date"))
            day = func.date(rows.c.shift_date)
            row = conn.execute(select(func.min(day), func.max(day), func.count()).select_from(rows)).first()
            # An aggregate always returns one row; None would mean the query
            # never ran, which is a different failure and must not be silently
            # skipped into an empty `outside`.
            assert row is not None, name
            spans[name] = tuple(row)

    outside = {
        name: (lo, hi)
        for name, (lo, hi, count) in spans.items()
        if not count or date.fromisoformat(lo) < start or date.fromisoformat(hi) > SEED_AS_OF
    }
    assert outside == {}, f"seeded rows fall outside the captured window {start}..{SEED_AS_OF}: {outside}"


def test_only_the_routes_that_need_query_params_are_given_any(harness: _Harness):
    """Over-supply is as wrong as under-supply, and quieter.

    Sending an optional `client_id` narrows a route's answer to one tenant and
    records THAT as its shape. Every other golden route must be planned with
    no kwargs at all, so the 155 entries this layer does not touch stay
    byte-identical -- which is the property that made the nine-entry diff
    reviewable in the first place.
    """
    with_params = {route: kwargs["params"] for route, kwargs in harness.plan.kwargs.items() if kwargs}

    assert set(with_params) == set(UNBLOCKED)
    assert {route: tuple(params) for route, params in with_params.items()} == UNBLOCKED
    # Deferred routes are planned, and planned with nothing.
    assert all(harness.plan.kwargs[route] == {} for route in DEFERRED_TO_WRITE_CAPTURE)


def test_every_unblocked_route_answered_with_real_fields(captured_shapes: Dict[str, List[str]]):
    """The bar: a `<status:422>` becoming a real shape is only progress if the
    shape is REAL.

    Three things are checked, because "it returns 200 now" is exactly the
    claim that let #244's empty answers through. No entry may be a
    placeholder; no entry may be an empty shape (a 200 carrying no fields at
    all -- what `GET /api/capacity/kpi/variance` would have recorded, which is
    why it is blocked instead); and every route that returns ROWS must have
    recorded row keys. `shape_of` only descends into a list's first element,
    so a `rows[]`/`statistics[]` prefix in the entry is proof the collection
    came back non-empty -- an empty list contributes nothing at all.
    """
    placeholders = {r: captured_shapes[r] for r in UNBLOCKED if is_placeholder(captured_shapes[r])}
    # The CSV twin is the one legitimate placeholder: it streams text/csv, and
    # `<non-json>` is what a successful non-JSON answer records. Its JSON twin
    # carries the field evidence for both.
    assert placeholders == {"GET /api/pivot/{dataset}/csv": ["<non-json>"]}

    empty = {r: captured_shapes[r] for r in UNBLOCKED if captured_shapes[r] == []}
    assert empty == {}

    rows = {
        "GET /api/attendance/statistics/summary": "statistics[].",
        "GET /api/pivot/{dataset}": "rows[].",
    }
    for route, prefix in rows.items():
        assert any(key.startswith(prefix) for key in captured_shapes[route]), (
            f"{route} answered 200 but its collection was empty, so the entry records the "
            f"no-entries branch as if it were the route's contract"
        )


def test_the_id_probe_reuses_the_capture_s_query_params(harness: _Harness, bogus_id_shapes, bogus_urls):
    """The gate that keeps the id-sensitivity gate honest.

    `test_a_2xx_is_proof_the_id_was_right_except_where_declared` re-requests
    every path-param route with an impossible id and requires the answer to
    change. For a route with required query params, dropping those params from
    the probe ALSO changes the answer -- to a 422 about the missing params --
    so the gate passes while proving nothing about the id.

    Reproduced here rather than argued: the same bogus URL answers 404 (the id
    was wrong) with the capture's params and 422 (the request was malformed)
    without them. The first assertion fails the moment `bogus_id_shapes` stops
    passing `plan.kwargs`.
    """
    route = "GET /api/attendance/kpi/bradford-factor/{employee_id}"
    method, path = route.split(" ", 1)

    assert bogus_id_shapes[route] == ["<status:404>"]

    without = capture_all(harness.client, [(method, path, {})], urls={route: bogus_urls[route]})
    assert without[route] == ["<status:422>"]


def test_variance_is_blocked_by_an_empty_table_not_by_an_unresolvable_id(harness: _Harness):
    """The declaration says the id resolves and the route still has nothing to
    say. Both halves are checked, because the reason is the whole value of the
    entry: if `client_id` were actually unresolvable this would be a seeder
    regression wearing a data-gap label.
    """
    resolver = Resolver(harness.engine)

    # The id itself resolves -- through the PATH registry, where it is used by
    # thirteen other routes -- so nothing about this route's id is broken.
    assert resolver.resolve("client_id", "/api/capacity/workbook/{client_id}")

    with pytest.raises(UnresolvableParam) as raised:
        resolver.resolve_query("client_id", "/api/capacity/kpi/variance")
    assert "CAPACITY_KPI_COMMITMENT has zero seeded rows" in raised.value.reason

    # And the claim it rests on: asked with a real client, the route answers
    # 200 with a body carrying no fields. That is what would have gone into the
    # golden master as this route's contract.
    client_id = resolver.resolve("client_id", "/api/capacity/workbook/{client_id}")
    response = harness.client.get("/api/capacity/kpi/variance", params={"client_id": client_id})
    assert response.status_code == 200
    assert response.json() == []


def test_the_pivot_envelope_holds_for_every_dataset_not_just_the_captured_one(harness: _Harness):
    """`literal` names ONE dataset; the route serves six with disjoint measures.

    The capture asks `/api/pivot/{dataset}` with the single dataset
    `QUERY_REGISTRY["dataset"].literal` names, so the golden master records
    that dataset's measures as "the shape of the route". A cross-model review
    of the query-param layer raised exactly this: a fixed literal with a
    `choices` membership check catches a dataset the app DROPS, but never
    proves the recorded shape is representative of the ones it keeps.

    For pivot it genuinely is not. `registry.DATASETS` gives production,
    downtime, quality, holds, labor and delivery completely disjoint measure
    sets, so a response model enumerating any one of them would make Pydantic
    strip the other five out of the response -- a typed contract that silently
    deletes data. `PivotResponse` therefore declares only the envelope.

    This walks DATASETS itself rather than the captured literal, and requires
    of every dataset: the five envelope keys survive, and the measures the
    registry declares for THAT dataset arrive intact.

    Both ways of getting it wrong were mutation-checked against this test:
    typing `totals` as a model with production's measures REQUIRED makes the
    other datasets raise ResponseValidationError (500); typing them Optional
    makes the response come back 200 with the measures silently deleted
    ("response model dropped [...]"). The first is loud, the second is not --
    which is why this asserts on the field set rather than on the status code.
    """
    from backend.pivot.registry import DATASETS

    # No DB is touched: `bucket` is a LITERAL and the dates are SEED_WINDOWs.
    # (The sibling tests above pass None too; mypy only checks this one
    # because its signature is typed.)
    resolver = Resolver(engine=None)  # type: ignore[arg-type]
    bucket = resolver.resolve_query("bucket", "/api/pivot/{dataset}")
    start = resolver.resolve_query("start_date", "/api/pivot/{dataset}")
    end = resolver.resolve_query("end_date", "/api/pivot/{dataset}")

    checked = {}
    for name, spec in DATASETS.items():
        resp = harness.client.get(
            f"/api/pivot/{name}",
            params={"bucket": bucket, "start_date": start, "end_date": end},
        )
        assert resp.status_code == 200, f"{name} -> {resp.status_code} {resp.text[:200]}"
        body = resp.json()
        assert set(body) == {"dataset", "bucket", "group_by", "rows", "totals"}, name
        assert body["dataset"] == name

        # The registry's own measure list for THIS dataset, not the captured one.
        measures = set(spec.measures)
        missing = measures - set(body["totals"])
        assert not missing, f"{name}: response model dropped {sorted(missing)}"

        # `totals` is typed `Dict[str, Any]`, and Pydantic renders a Decimal
        # under `Any` as a JSON STRING -- the same leak this branch's
        # quality-score fix closed. The engine casts to float today, for all
        # six datasets; this keeps a dataset that starts returning Decimal
        # from re-opening it quietly, since an envelope model cannot coerce
        # what it does not name.
        stringly = {k: v for k, v in body["totals"].items() if isinstance(v, str)}
        assert not stringly, f"{name}: numeric totals arrived as strings: {stringly}"
        checked[name] = sorted(measures)

    assert len(checked) == len(DATASETS) >= 6
    # The captured dataset must not be the only one with a distinctive set --
    # otherwise this test would pass even if the route ignored `dataset`.
    assert len({tuple(v) for v in checked.values()}) > 1, checked


def _is_required(param: object) -> bool:
    """Whether a FastAPI `ModelField` is required, across pydantic shapes.

    `ModelField.required` exists on some versions and not others; where it is
    absent the truth lives on `field_info.is_required()`. Defaulting to True
    is the safe direction here -- an unknown shape counts as required, which
    at worst asks for a declaration that was not needed, rather than silently
    exempting a route from the gate.
    """
    value = getattr(param, "required", None)
    if value is not None:
        return bool(value)
    field_info = getattr(param, "field_info", None)
    is_required = getattr(field_info, "is_required", None)
    return bool(is_required()) if callable(is_required) else True


def test_an_optional_param_route_that_4xxs_is_declared_one_way_or_the_other():
    """Closes the door `required_query_params` cannot watch.

    `required_query_params` reads FastAPI's `dependant`, which is right about
    what provokes a 422 and blind to a route that takes `Query(None)` and
    then refuses in its own body. A route in that shape records a 4xx in the
    golden master that is indistinguishable, by inspection, from the route's
    real answer -- which is how `GET /api/onboarding/status` sat at
    `<status:400>` while the layer that would have fixed it was already
    shipped, and how a test in test_frontend_usage.py came to cite that 400
    as an example of a status that WAS the route's own answer.

    So every golden 4xx on a route with optional query params has to be
    named: either the harness owes it a param
    (`EFFECTIVELY_REQUIRED_QUERY_PARAMS`) or the route means it
    (`STATUS_IS_THE_ROUTES_OWN_ANSWER`, with the evidence). Routes that take
    a request body are skipped outright -- their 422 is the body talking, not
    a query param, and that is read off `dependant.body_params` rather than
    from a list of route names. Routes in `DEFERRED_TO_WRITE_CAPTURE` are
    skipped too: the read pass plans them with no params deliberately because
    they mutate, so their 422 records that decision. Neither registry is
    consulted for routes outside that shape, so this cannot quietly become a
    dumping ground for unrelated 4xxs.
    """
    from backend.main import app

    index = route_index(app)
    unexplained = {}
    for route_key, shape in sorted(_golden().items()):
        if not (shape and str(shape[0]).startswith("<status:4")):
            continue
        route = index.get(route_key)
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        optional = [q.alias for q in dependant.query_params if not _is_required(q)]
        if not optional:
            continue
        # A route that REQUIRES a body 422s for the body. Its optional query
        # params are incidental and this gate has no claim on it -- the
        # write-capture harness owes it a request, not a query param.
        # Read structurally off `dependant` rather than by naming routes, so
        # a body route added later is exempt without an edit here.
        #
        # Required-ness matters: `body_params` being non-empty is not enough.
        # `POST /api/defect-types/upload/{client_id}` carries an optional
        # `replace_existing` beside its required `file`, so a mere non-empty
        # test would exempt a route whose body is entirely optional -- whose
        # 4xx could then be a handler-raised complaint about a query param,
        # exempted without ever being declared.
        if any(_is_required(param) for param in dependant.body_params):
            continue

        # Deliberately not sent: the route mutates, so the read pass plans it
        # with no params on purpose and its 422 is that decision, not a gap.
        if route_key in DEFERRED_TO_WRITE_CAPTURE:
            continue

        path = route_key.split(" ", 1)[1]
        if path in EFFECTIVELY_REQUIRED_QUERY_PARAMS or route_key in STATUS_IS_THE_ROUTES_OWN_ANSWER:
            continue
        unexplained[route_key] = (shape[0], optional)

    assert not unexplained, (
        "4xx on a route with optional query params, explained by neither registry: " f"{unexplained}"
    )


def test_the_routes_own_answer_declarations_still_describe_a_4xx_route():
    """The other direction: a declaration that outlived its route.

    Once a route is promoted to a real shape -- by seeding the data it wanted,
    or by a param being supplied -- its entry here is stale, and leaving it
    would exempt a future 4xx on the same route from ever being explained
    again. Fails when that happens, naming the route to delete.
    """
    golden = _golden()
    stale = {
        route: golden.get(route)
        for route in STATUS_IS_THE_ROUTES_OWN_ANSWER
        if not (golden.get(route) and str(golden[route][0]).startswith("<status:4"))
    }

    assert not stale, f"declared as the route's own 4xx but no longer 4xx -- delete these: {stale}"
