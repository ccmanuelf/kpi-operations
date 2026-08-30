"""Resolve a route template's path params to REAL ids from the seeded database.

`capture_all`'s docstring has always stated the hazard exactly: *"the caller
owns id resolution -- the harness deliberately does not guess ids, because a
wrong id yields a 404 whose shape is recorded as if it were the real answer."*
But nothing ever DID the resolving. `loose_routes()` hands back `(method,
route.path, {})` -- the raw template -- so every path-param route in the golden
master was captured by requesting a URL with literal braces in it, e.g.
`GET /api/workflow/statistics/%7Bclient_id%7D/status-distribution`.

Measured across the golden master's 63 path-param entries before this module
existed: 32 `<status:404>`, 22 `<status:422>`, 1 `<status:400>`, and 8 that
recorded a 200 shape for an entity whose id was the literal string
`{client_id}`. The 8 are the dangerous ones -- `status-distribution` recorded
3 keys where the real answer has 5, silently omitting an entire nested object
(`by_status[].{status,count,percentage}`). A response model built from that
entry would drop three fields from production responses.

This module is the missing half. Three code paths, not 49 special cases:

  SEEDED_ROW  one SELECT against the DB the harness just seeded; fail loudly
              if it returns nothing (that is a SEEDER regression, not a
              missing feature, and gets its own louder message).
  LITERAL     a fixed string; the param is not a row id at all (a KPI type
              name, a dataset name, a cache-key prefix).
  BLOCKED     no value can produce a meaningful answer today, because the
              backing table has zero seeded rows. Declared, with a reason,
              never guessed. Extending the seeder is Task 8d, not this module.

DERIVE, DO NOT HARDCODE. Every SEEDED_ROW value comes from executing its SQL
against the live seeded DB, never from a pasted literal, for reasons that are
not theoretical:

  * `seed/identity.py`'s `IntPkAllocator` starts every integer PK at
    `MAX(pk) + 1` of the LIVE transaction, so `employee_id`, `line_id`,
    `shift_id`, `product_id` and both `catalog_id` spaces are 1 only on a
    pristine database.
  * String PKs embed a calendar date derived from `as_of`
    (`DEMO-HOURLY-PE-2026-08-12-0-0`), and `DOWNTIME_ENTRY` / `ATTENDANCE_ENTRY`
    additionally embed internal auto-increment line/shift PKs
    (`DT-20260812-1-1`) -- those cannot be reconstructed from a format string
    at all, only read back.
  * `HOLD_ENTRY` rows exist only for particular RNG draws: smoke + seed=7
    produces ZERO holds; smoke + seed=1234 produces 5.

A stale literal on a route that cannot 404 is the worst case of all: a green
test capturing an empty body. See `capture.capture_all`'s brace guard for the
last line of defence.

THE QUERY HALF. A path param is not the only thing a caller can fail to
supply, and the failure looks different but records the same lie: nine golden
entries read `<status:422>` because the harness sent no `start_date`, no
`bucket`, no `client_id`. `resolve_query` / `required_query_params` /
`CapturePlan.kwargs` below are that half, declared in `query_specs.py` the
same way `param_specs.py` declares this one, resolved through the same
`_value_of` and the same `_cache`, and carried to the request as kwargs rather
than as URL text. Everything a request needs now travels in the plan, which is
what the write-capture harness extends for bodies: another registry and
another entry in `kwargs`, not another resolver.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import Engine, text

from backend.tests.contract.capture import SeededToday, flatten_api_routes
from backend.tests.contract.param_specs import (
    COMPOSITES,
    FAMILY_ROUTER,
    MUTATING_METHODS,
    REGISTRY,
    Kind,
)
from backend.tests.contract.query_specs import (
    EFFECTIVELY_REQUIRED_QUERY_PARAMS,
    QUERY_FAMILY_ROUTER,
    QUERY_REGISTRY,
)

_PARAM = re.compile(r"\{(\w+)\}")


class UnresolvableParam(Exception):
    """Raised when a path param cannot be resolved. Never swallowed.

    The whole defect this module repairs is that an unresolved param silently
    produced a recordable answer. Falling back to a literal-brace URL is the
    one outcome that must be impossible.
    """

    def __init__(self, key: str, route: str, reason: str) -> None:
        super().__init__(f"{route}: cannot resolve {{{key.split('@')[0]}}} -- {reason}")
        self.key = key
        self.route = route
        self.reason = reason


def _route_family_key(param: str, route_path: str, router: Dict[str, Tuple[Tuple[str, str], ...]], table: str) -> str:
    """`param@family` for a collision-prone name, the bare name otherwise.

    Shared by the path and query registries because the hazard is identical:
    one param NAME meaning more than one thing depending on the route. A
    routed name whose route matches no fragment RAISES -- falling back to the
    bare name is what turns a new route family into a silent wrong-entity
    resolution rather than a failure that names itself.
    """
    routes = router.get(param)
    if routes is None:
        return param
    for fragment, key in routes:
        if fragment in route_path:
            return key
    raise UnresolvableParam(
        param,
        route_path,
        f"{param!r} is a collision-prone name with no {table} entry matching this route. "
        "Add the new route family explicitly -- falling back to the bare name would resolve it "
        "against another family's table and return a wrong-entity 200.",
    )


def spec_key(param: str, route_path: str) -> str:
    """`param@family` for a collision-prone PATH param, the bare name otherwise."""
    return _route_family_key(param, route_path, FAMILY_ROUTER, "FAMILY_ROUTER")


def query_spec_key(param: str, route_path: str) -> str:
    """`param@family` for a collision-prone QUERY param, the bare name otherwise."""
    return _route_family_key(param, route_path, QUERY_FAMILY_ROUTER, "QUERY_FAMILY_ROUTER")


def params_of(route_path: str) -> List[str]:
    return _PARAM.findall(route_path)


def blocked_shape(key: str) -> List[str]:
    """The golden entry for a route no id can reach.

    Deliberately NOT a `<status:...>` placeholder: a status says "the route
    answered and this is what it said", which is a lie when the request was
    never sent. The reason lives in `REGISTRY[key].reason` rather than in the
    string so that editing a reason does not churn the golden file.
    """
    return [f"<blocked:{key}>"]


class Resolver:
    """Turns a route template into a concrete URL, or raises saying why not."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._cache: Dict[str, str] = {}

    def _scalar(self, sql: str) -> Optional[object]:
        with self._engine.connect() as conn:
            return conn.execute(text(sql)).scalar()

    def resolve(self, param: str, route_path: str) -> str:
        """A PATH param's value, from the path registry."""
        return self._value_of(spec_key(param, route_path), route_path, REGISTRY, "REGISTRY")

    def resolve_query(self, param: str, route_path: str) -> str:
        """A required QUERY param's value, from the query registry.

        Deliberately the same `_value_of` the path resolver uses: `client_id`
        and `product_id` are the SAME entities whether they arrive in the path
        or the query string, `query_specs.QUERY_REGISTRY` holds the very spec
        OBJECTS `REGISTRY` holds for them, and the `self._cache` entry is
        shared because it is keyed on the spec key. One SELECT, one answer,
        no second machinery to keep in step -- which is also what makes the
        write-capture harness's body params an extra registry rather than an
        extra resolver.
        """
        return self._value_of(query_spec_key(param, route_path), route_path, QUERY_REGISTRY, "QUERY_REGISTRY")

    def _value_of(self, key: str, route_path: str, registry: Dict[str, Any], name: str) -> str:
        spec = registry.get(key)
        if spec is None:
            raise UnresolvableParam(key, route_path, f"no ParamSpec registered in {name} for {key!r}")
        if spec.kind is Kind.BLOCKED:
            raise UnresolvableParam(key, route_path, spec.reason or "")
        if spec.kind is Kind.LITERAL:
            # `choices` is the application's own accepted set, imported rather
            # than retyped. Checking membership here is what stops a literal
            # that the app has since renamed from being sent anyway and
            # recording the resulting 422 as this route's answer -- the exact
            # failure the old `<status:422>` entries were.
            if spec.choices is not None and spec.literal not in spec.choices:
                raise UnresolvableParam(
                    key,
                    route_path,
                    f"literal {spec.literal!r} is not in the application's own accepted set "
                    f"{list(spec.choices)}. The app changed its vocabulary; update the spec.",
                )
            return str(spec.literal)
        if spec.kind is Kind.SEED_WINDOW:
            # `SeededToday.today()`, never `date.today()`: the same pin the
            # captured routes read, so the window is a property of the seed
            # rather than of the day the suite happens to run. Unpinned it
            # RAISES (see SeededToday), which is why there is no fallback here.
            return (SeededToday.today() - timedelta(days=spec.offset_days or 0)).isoformat()
        if key not in self._cache:
            value = self._scalar(str(spec.sql))
            if value is None:
                # Deliberately a DIFFERENT, louder message than the BLOCKED
                # case. A blocked param is an expected, documented gap; a
                # SEEDED_ROW param that finds nothing means the seeder stopped
                # writing a table it is supposed to write. Collapsing the two
                # into one "not found" is how a broken seeder gets mistaken
                # for a known gap and quietly skipped for months.
                raise UnresolvableParam(
                    key,
                    route_path,
                    f"SEEDED_ROW spec found no row in {spec.table} via {spec.sql!r}. "
                    "The seed no longer populates this table -- fix the seeder, not this spec.",
                )
            self._cache[key] = str(value)
        return self._cache[key]

    def values_for(self, route_path: str) -> Dict[str, str]:
        """Every param of `route_path`, resolved. Composite halves first.

        Split out from `url_for` so `bogus_url_for` can derive its substitutes
        from the SAME values rather than re-deriving them -- two code paths
        that disagree about which param belongs to which route is how a probe
        ends up testing something other than what the capture requested.
        """
        values: Dict[str, str] = {}
        composite = COMPOSITES.get(route_path)
        if composite is not None:
            sql, names = composite
            with self._engine.connect() as conn:
                row = conn.execute(text(sql)).first()
            if row is None:
                raise UnresolvableParam(
                    "+".join(names),
                    route_path,
                    f"composite spec found no row via {sql!r}. Fix the seeder, not this spec.",
                )
            values.update({name: str(value) for name, value in zip(names, row)})

        for param in params_of(route_path):
            # `param not in values`, not `values.get(param) or ...`: a composite
            # half that legitimately resolved to a falsy string would otherwise
            # fall through to the single-param path and break the atomicity the
            # composite exists to guarantee.
            if param not in values:
                values[param] = self.resolve(param, route_path)
        return values

    def url_for(self, route_path: str) -> str:
        """The concrete URL for `route_path`, with every param substituted."""
        return _substitute(route_path, self.values_for(route_path))

    def query_for(self, route_path: str, route: Any) -> Dict[str, str]:
        """Every query param `route` will not answer without, resolved. `{}`
        when it has none -- which is most routes, and is what keeps this a
        no-op for the 155 golden entries that never needed it.

        Two sources, because required-ness has two homes. `required_query_
        params` reads FastAPI's `dependant`, which is authoritative for the
        422 the harness is avoiding but blind to a route that declares
        `Query(None)` and then raises in its own body. Those are named in
        `EFFECTIVELY_REQUIRED_QUERY_PARAMS`, declared per route rather than
        inferred from a status code -- see that registry's note.
        """
        params = list(required_query_params(route))
        for param in EFFECTIVELY_REQUIRED_QUERY_PARAMS.get(route_path, ()):
            if param not in params:
                params.append(param)
        return {param: self.resolve_query(param, route_path) for param in params}


def required_query_params(route: Any) -> Tuple[str, ...]:
    """The query params `route` will 422 without, in declaration order.

    Read off FastAPI's OWN `route.dependant`, not off `inspect.signature`.
    The two forms in this codebase --

        start_date: date
        client_id: str = Query(..., description="Client ID")

    -- disagree about where required-ness lives (absent default vs a default
    that IS the requirement), and a signature scan reading "has a default" as
    "optional" misses the second silently: that is how the measurement this
    work started from lost `GET /api/capacity/kpi/variance`'s `client_id`.
    `dependant` is what the running route uses to decide, so it cannot
    disagree with the 422 the harness is trying to stop provoking.

    Sub-dependencies are walked too. None contributes a REQUIRED param today
    (`resolve_client_scope`'s `client_id` is optional), so this recursion adds
    nothing to the current capture -- it is here because a required param
    arriving through a shared dependency would otherwise be invisible to the
    top-level scan, and the failure would look like a route that "just 422s".

    `alias` rather than `name`: the alias is the wire name, and they differ
    the moment anyone writes `Query(..., alias="from")`.
    """
    dependant = getattr(route, "dependant", None)
    if dependant is None:  # pragma: no cover -- every APIRoute carries one
        return ()
    found: List[str] = []
    stack = [dependant]
    while stack:
        current = stack.pop(0)
        found.extend(field.alias for field in current.query_params if field.field_info.is_required())
        stack.extend(current.dependencies)
    return tuple(dict.fromkeys(found))


def route_index(app: Any) -> Dict[str, Any]:
    """`"METHOD /path"` -> the effective route object, for every /api route.

    Keyed the way the golden master is keyed so a plan can look up the route
    behind an entry. Built once per plan: `flatten_api_routes` walks ~470
    routes through FastAPI's `_IncludedRouter` wrappers (see `capture.py`),
    which is not something to redo per param.
    """
    index: Dict[str, Any] = {}
    for route in flatten_api_routes(app.routes):
        if not str(route.path).startswith("/api"):
            continue
        for method in set(route.methods or ()) - {"HEAD", "OPTIONS"}:
            index[f"{method} {route.path}"] = route
    return index


def _substitute(route_path: str, values: Dict[str, str]) -> str:
    url = route_path
    for param, value in values.items():
        url = url.replace("{" + param + "}", value)
    return url


def bogus_url_for(route_path: str, resolver: Resolver) -> str:
    """The same URL with every ID replaced by one that cannot exist.

    Derived from the REAL value's shape rather than hardcoded per param: an
    all-digits id becomes `999999999` (no seeded integer PK comes near it, and
    a non-numeric substitute would 422 on an `int`-typed param and prove
    nothing about the id), anything else becomes `NO-SUCH-ID`. Composite halves
    are substituted too, since a right id under a wrong client is a 404 that
    looks like a bad id.

    A `Kind.LITERAL` param is NOT an id, so it is substituted only when its
    spec declares a `bogus` value -- see `ParamSpec.bogus` for why feeding an
    id sentinel to `{kpi_type}` is both meaningless and noisy. A route left
    entirely unsubstituted returns its real URL; the caller must treat that as
    "not probeable" rather than as "id-insensitive", and
    `test_a_2xx_is_proof_the_id_was_right_except_where_declared` asserts no
    such route reaches its comparison.
    """
    # Starts from the REAL values and overrides, so a param left unsubstituted
    # keeps a valid value rather than a brace -- `capture_all`'s guard would
    # (correctly) refuse to request a URL still carrying one.
    values = dict(resolver.values_for(route_path))
    for param, value in list(values.items()):
        spec = REGISTRY.get(spec_key(param, route_path))
        if spec is not None and spec.kind is Kind.LITERAL:
            if spec.bogus is not None:
                values[param] = spec.bogus
            continue
        # Composite halves have no standalone spec (spec is None) and are ids
        # like any other, so they fall through to the sentinel deliberately.
        values[param] = "999999999" if value.isdigit() else "NO-SUCH-ID"
    return _substitute(route_path, values)


@dataclass(frozen=True)
class CapturePlan:
    """What to request, in what order, and what could not be requested."""

    #: (method, route template, request kwargs) for routes safe to run in one pass.
    requests: List[Tuple[str, str, dict]] = field(default_factory=list)
    #: Same, for mutating path-param routes: each is replayed against a
    #: freshly restored snapshot so it cannot poison its successors.
    isolated: List[Tuple[str, str, dict]] = field(default_factory=list)
    #: route key -> concrete URL. Never contains a brace; `capture_all` asserts it.
    urls: Dict[str, str] = field(default_factory=dict)
    #: route key -> the request kwargs that route was planned with, today
    #: `{"params": {...}}` for the routes carrying required query params and
    #: `{}` for everything else.
    #:
    #: Kept as a MAP as well as inside the request tuples so a second pass can
    #: re-issue a route the way the capture issued it. `bogus_id_shapes` is
    #: that second pass, and getting this wrong is not theoretical: probing
    #: `GET /api/pivot/{dataset}` with a bogus dataset but WITHOUT its query
    #: params gets a 422 for the missing params, which differs from the real
    #: shape and so reads as "this route discriminates on its id" -- a green
    #: answer to a question that was never asked. The id-sensitivity gate is
    #: only meaningful when the two requests differ in the id ALONE.
    #:
    #: This is also the seam the write-capture harness extends: a request body
    #: is another entry in the same dict (`{"json": {...}}`), resolved by
    #: another registry, with every consumer already reading it from here.
    kwargs: Dict[str, dict] = field(default_factory=dict)
    #: route key -> the exception that blocked it, NOT just its spec key.
    #:
    #: The whole exception, because `UnresolvableParam` carries two very
    #: different failures under one type and only its `reason` tells them
    #: apart: a declared BLOCKED gap ("JOB has zero seeded rows... Task 8d"),
    #: and a SEEDED_ROW spec that found nothing, which is a SEEDER REGRESSION
    #: and says so in a deliberately louder message. Storing only the key threw
    #: that message away and left the two indistinguishable at every consumer
    #: -- which is precisely the collapse `Resolver.resolve` writes two
    #: separate messages to prevent.
    blocked: Dict[str, "UnresolvableParam"] = field(default_factory=dict)


def plan_capture(route_keys: Iterable[str], resolver: Resolver, app: Any) -> CapturePlan:
    """Resolve every route key up front, before a single request is issued.

    Up front and not lazily, for two reasons. An id read back mid-capture would
    see a database an earlier mutating route had already changed; and the
    isolated phase restores a pristine snapshot before each request, which
    makes every id resolved from the pristine state valid again -- but only if
    they were resolved from it in the first place.

    Query params are resolved here too, and only for NON-mutating routes.
    That exclusion is not squeamishness about writes: a mutating route is
    replayed against a restored snapshot only when it carries a path param
    (`capture_isolated`), so handing a paramless POST the query params it has
    been 422ing for would move it from "never ran" to "ran in the middle of
    the read pass and left its writes behind". The seven affected routes are
    declared in `query_specs.DEFERRED_TO_WRITE_CAPTURE` and gated two-sided,
    so this is a stated boundary rather than an accident of ordering.

    `app` is needed because required-ness is FastAPI's answer, not ours --
    see `required_query_params`.
    """
    plan = CapturePlan()
    index = route_index(app)
    for route_key in route_keys:
        method, path = route_key.split(" ", 1)
        route = index.get(route_key)
        if route is None:
            raise AssertionError(
                f"{route_key} is in the golden master but not registered on the app. "
                "Either the route was removed (prune its golden entry deliberately) or "
                "route enumeration broke -- both are findings, neither is a skip."
            )
        try:
            plan.urls[route_key] = resolver.url_for(path)
            plan.kwargs[route_key] = {} if method in MUTATING_METHODS else _params_kwarg(resolver, path, route)
        except UnresolvableParam as exc:
            plan.urls.pop(route_key, None)
            plan.blocked[route_key] = exc
            continue
            # Every mutating route is isolated, not only the ones carrying a path
        # param. `"{" in path` was standing in for "this route mutates", and the
        # two are not the same question: twenty mutating routes have no path
        # param, so they were planned into the READ pass where `restore()` is
        # never called and anything they write persists into every route captured
        # after them. Four of them actually execute today
        # (alerts/generate/check-all, cache/clear, metrics/calculate/run-nightly,
        # predictions/demo/seed) -- the last two write.
        #
        # No golden entry changes when they move (measured: zero shapes differ),
        # so this corrects a latent order-dependence rather than a live wrong
        # answer. It is a prerequisite for write capture all the same: once these
        # routes are handed request bodies they stop being harmless.
        target = plan.isolated if method in MUTATING_METHODS else plan.requests
        target.append((method, path, plan.kwargs[route_key]))
    return plan


def _params_kwarg(resolver: Resolver, path: str, route: Any) -> dict:
    query = resolver.query_for(path, route)
    return {"params": query} if query else {}
