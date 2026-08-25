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
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import Engine, text

from backend.tests.contract.param_specs import (
    COMPOSITES,
    FAMILY_ROUTER,
    MUTATING_METHODS,
    REGISTRY,
    Kind,
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


def spec_key(param: str, route_path: str) -> str:
    """`param@family` for a collision-prone name, the bare name otherwise."""
    routes = FAMILY_ROUTER.get(param)
    if routes is None:
        return param
    for fragment, key in routes:
        if fragment in route_path:
            return key
    raise UnresolvableParam(
        param,
        route_path,
        f"{param!r} is a collision-prone name with no FAMILY_ROUTER entry matching this route. "
        "Add the new route family explicitly -- falling back to the bare name would resolve it "
        "against another family's table and return a wrong-entity 200.",
    )


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
        key = spec_key(param, route_path)
        spec = REGISTRY.get(key)
        if spec is None:
            raise UnresolvableParam(key, route_path, f"no ParamSpec registered for {key!r}")
        if spec.kind is Kind.BLOCKED:
            raise UnresolvableParam(key, route_path, spec.reason or "")
        if spec.kind is Kind.LITERAL:
            return str(spec.literal)
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


def plan_capture(route_keys: Iterable[str], resolver: Resolver) -> CapturePlan:
    """Resolve every route key up front, before a single request is issued.

    Up front and not lazily, for two reasons. An id read back mid-capture would
    see a database an earlier mutating route had already changed; and the
    isolated phase restores a pristine snapshot before each request, which
    makes every id resolved from the pristine state valid again -- but only if
    they were resolved from it in the first place.
    """
    plan = CapturePlan()
    for route_key in route_keys:
        method, path = route_key.split(" ", 1)
        try:
            plan.urls[route_key] = resolver.url_for(path)
        except UnresolvableParam as exc:
            plan.blocked[route_key] = exc
            continue
        target = plan.isolated if (method in MUTATING_METHODS and "{" in path) else plan.requests
        target.append((method, path, {}))
    return plan
