"""Extract, per endpoint, which response fields the frontend actually reads.

This is the second of two safety nets for the response-model refactor. A
Pydantic response model DROPS any key it does not declare. The golden master
(tasks 1-3) catches a field that DISAPPEARS from a response; this extractor
catches the opposite failure — a field the UI reads that a hand-written
response model never declares, which would otherwise be silently baked in as
a regression.

Two extraction strategies are combined:

Pass 0 (direct): a field read in the SAME `export const` block as the
endpoint literal, e.g. `getAbsenteeism` in kpi.ts, which calls
`api.get('/attendance/kpi/absenteeism', ...)` and reads `d?.by_reason` in the
same function body.

Pass 1 + Pass 2 (wrapper hop): many endpoints are called through a thin,
named wrapper (`export const getEfficiencyTrend = (params) =>
api.get('/kpi/efficiency/trend', ...)`) that is then invoked BY NAME from a
different file — a Pinia store, a composable, a .vue view — where the actual
field reads happen. Pass 1 maps wrapper name -> endpoint(s) by scanning
services/api/*.ts. Pass 2 then scans every other file under frontend/src for
a reference to that name and attributes every field read anywhere in that
file to the resolved endpoint(s).

Pass 2 deliberately over-matches, at whole-file granularity, rather than
trying to scope down to "the call site's enclosing block": a caller module
frequently doesn't even define blocks the same way the api/ modules do (a
.vue SFC has no top-level `export const`), and known real call sites in this
codebase span multiple sibling `export const` blocks in the same file (see
KNOWN GAP below). A false positive here costs someone a two-second look at a
field that turns out not to be endpoint-specific; a false negative would
silently drop a field the UI genuinely depends on from the safety net. A
short list of obvious non-field JS/TS method names (`_JS_NOISE`) is filtered
out since whole-file matching surfaces plain method calls (`d.map(...)`) as
if they were field reads; `value` and `data` are kept because both are
genuine backend response field names in this codebase, not just generic
accessors.

KNOWN GAP, deliberately not chased further: the `/api/kpi/*/trend` cluster
(efficiency, wipAging, onTimeDelivery, availability, performance, quality,
oee, absenteeism, ppm, throughput) still resolves to an EMPTY field set even
with both passes. Traced by hand: `stores/kpi.ts` calls
`api.getEfficiencyTrend(params)` etc. and stores the raw response opaquely
(`this.trends[trendField] = trendRes.data`) with no per-point field access.
The actual `date`/`value` read happens up to two hops further downstream, in
`components/kpi/kpiChartConfig.ts::unwrapTrend`, which:
  1. destructures each point with the parameter name `r`, not one of this
     module's recognised receivers (`d`/`data`/`res`/`response`/`result`) --
     `d.map((r: { date: unknown; value: unknown }) => ({ date: String(r.date), ... }))`;
  2. reads `res` through a TypeScript cast, `(res as { data?: unknown })?.data`,
     which breaks the "receiver immediately followed by `.`" assumption `_FIELD`
     relies on -- the `as {...}` cast sits in between; and
  3. states `date`/`value` partly as inline TYPE ANNOTATIONS, not only as
     runtime `.field` accesses.
Recognising this would require either treating arbitrary single-letter
callback parameters as receivers (catastrophic false-positive rate --
`r`/`i`/`e`/`t` are common short-lived loop/handler variables all over an
unrelated codebase) or a structurally different extractor (TypeScript
type-shape mining, not accessor-regex matching). Per instruction, this is
recorded as a stated boundary rather than papered over by widening `_FIELD`
until it happens to match. The golden master remains the backstop for this
cluster exactly as for the dynamic-key case below.

LIMITATION, stated rather than discovered later: a dynamic read — `row[key]`
where `key` is computed — is invisible to this extractor. The golden master
is the backstop for that case: it does not care why a field is read, only
that it is still sent. Do not treat a clean extractor run as proof no field
is needed.
"""

import json
import pathlib
import re

FRONTEND = pathlib.Path(__file__).resolve().parents[3] / "frontend" / "src"
API_DIR = FRONTEND / "services" / "api"
GOLDEN = pathlib.Path(__file__).resolve().parent / "golden" / "api_shapes.json"

# api.get('/kpi/dashboard') and friends. The leading /api comes from the axios
# baseURL, so endpoint literals in the client are written without it. Some
# call sites chain the method on its own line (`return api\n  .get(...)`,
# e.g. getAbsenteeism / getDefectRates in kpi.ts) so whitespace, including a
# newline, is allowed between `api` and the method call.
_ENDPOINT = re.compile(r"api\s*\.\s*(?:get|post|put|delete)\(\s*['\"`]([^'\"`]+)")

# d?.by_reason / data.total / response.data.rate -- the read forms this codebase
# actually uses, confirmed by reading services/api/kpi.ts.
_FIELD = re.compile(r"\b(?:d|data|res|response|result)\??\.(\w+)")

# Pass 2 widens matching to a whole file, which surfaces plain method calls
# (`d.map(...)`, `res.then(...)`) as if they were field reads. Filter the
# obvious ones. `value` and `data` are NOT here: both are genuine backend
# response field names elsewhere in this codebase (e.g. trend points carry
# `value`; several capacity/work-order endpoints wrap payloads in `data`).
_JS_NOISE = {"filter", "map", "length", "forEach", "then", "catch", "toFixed"}


def _normalize(endpoint: str) -> str:
    return endpoint if endpoint.startswith("/api") else "/api" + endpoint


def _wrapper_to_endpoints() -> dict:
    """Pass 1: map each `export const NAME = ... => api.<verb>(...)` wrapper
    in services/api/*.ts to the endpoint(s) it calls."""
    wrappers: dict = {}
    for path in sorted(API_DIR.glob("*.ts")):
        text = path.read_text(encoding="utf-8")
        for block in text.split("export const ")[1:]:
            name_match = re.match(r"(\w+)", block)
            endpoints = _ENDPOINT.findall(block)
            if not name_match or not endpoints:
                continue
            name = name_match.group(1)
            wrappers.setdefault(name, set()).update(_normalize(e) for e in endpoints)
    return wrappers


def fields_read_by_frontend() -> dict:
    usage: dict = {}

    # Pass 0: fields read in the same block as the endpoint literal.
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
                usage.setdefault(_normalize(endpoint), set()).update(fields)

    # Pass 1 + Pass 2: resolve thin wrappers to their endpoint(s), then look
    # everywhere else under frontend/src for a reference to that wrapper name
    # and pull in every field read in that whole file. See module docstring
    # for why this is whole-file and why it still misses the trend cluster.
    wrappers = _wrapper_to_endpoints()
    if wrappers:
        name_pattern = re.compile(
            r"\b(?:" + "|".join(re.escape(n) for n in sorted(wrappers, key=len, reverse=True)) + r")\b"
        )
        for path in sorted(FRONTEND.rglob("*.ts")) + sorted(FRONTEND.rglob("*.vue")):
            if path.parent == API_DIR:
                continue  # the wrapper's own definition; already covered by pass 0
            text = path.read_text(encoding="utf-8")
            referenced = set(name_pattern.findall(text))
            if not referenced:
                continue
            fields = set(_FIELD.findall(text)) - _JS_NOISE
            if not fields:
                continue
            for name in referenced:
                for endpoint in wrappers[name]:
                    usage.setdefault(endpoint, set()).update(fields)

    return usage


#: Endpoints where this extractor is KNOWN to be blind, so an empty or bleed-only
#: result must never be read as "nothing missing". Measured 2026-08-25: all eight
#: /api/kpi/*/trend endpoints report non-empty field sets that contain neither
#: `date` nor `value` -- the only two fields they actually return. The listed
#: fields are bleed from unrelated code in the same file. Coverage read 10/10
#: while real protection was 0/10, which is worse than an honest zero.
#:
#: Root cause is structural, not a regex to widen: kpiChartConfig.ts::unwrapTrend
#: destructures points as `r`, reads the axios envelope through a TypeScript cast,
#: and states date/value partly as type ANNOTATIONS rather than runtime accesses.
#: Recovering those needs type-shape mining, not another pass of accessor matching.
#:
#: Task 8 note (2026-08-25): `coverage_of()` now requires found fields to
#: intersect the route's real field names, so today's bleed for these eight
#: (`data`, `data_quality`, `has_estimated`, `inference`, `was_inferred`)
#: already fails the intersection on its own -- none of it is `date` or
#: `value`. This set is kept anyway, not shrunk, because that non-collision
#: is incidental rather than structural: `date` and `value` are two of the
#: most generic property names in this codebase (every trend cluster member
#: and the dashboard list endpoint use them), and kpi.ts is one large shared
#: file that Pass 2 scans at whole-file granularity. A future edit that adds
#: an unrelated `.date` or `.value` read anywhere near one of these wrapper
#: names would flip the intersection to a coincidental, non-attributable
#: COVERED, even though unwrapTrend's `r`-destructuring/type-cast/annotation
#: pattern means the extractor still cannot see the real per-point read. The
#: intersection rule cannot distinguish a genuine hit from that coincidence
#: for a two-letter, ubiquitous field name -- KNOWN_BLIND is what does.
#: `/api/kpi/on-time-delivery/trend` carries a second, independent reason:
#: its own golden master entry is `[]` (no data at capture time), so
#: `_real_field_names` already returns an empty set for it regardless.
KNOWN_BLIND = frozenset(
    {
        "/api/kpi/availability/trend",
        "/api/kpi/efficiency/trend",
        "/api/kpi/oee/trend",
        "/api/kpi/on-time-delivery/trend",
        "/api/kpi/performance/trend",
        "/api/kpi/quality/trend",
        "/api/kpi/throughput-time/trend",
        "/api/kpi/wip-aging/trend",
    }
)


def _real_field_names(endpoint: str, method: str = "GET") -> frozenset:
    """Top-level field names the golden master recorded for `endpoint`.

    `_FIELD` above only ever captures the field name immediately following
    one of its receiver tokens (`d.`, `data.`, ...) -- a single hop; it
    cannot chain through `d.otd.rate` and capture `rate`. So the only names
    this extractor could ever legitimately produce are the TOP-LEVEL keys of
    a response. Real field names are therefore the first dot-segment of each
    golden master key path, after stripping a trailing `[]` from any
    segment: a flat list route records `[].date` (segments `["", "date"]`
    after stripping -> top segment `date`), while a nested list-of-object
    field records e.g. `trends.efficiency[].date` (segments `["trends",
    "efficiency", "date"]` -> top segment `trends`).

    Golden master shapes that carry NO real field information MUST resolve to
    an empty set here so a caller can never manufacture a COVERED verdict out
    of them. There are two kinds:
      - A PLACEHOLDER entry, written `<...>`: `<status:422>` (the capture
        harness never reached a real response body), `<non-json>` (it did, and
        the body was a PNG or a 204 with no body at all), or `<blocked:job_id>`
        (Task 8b: no id could reach this route, because its backing table has
        zero seeded rows). Every one of these is skipped by the leading `<`,
        NOT by matching `<status:` alone: `<non-json>` predates Task 8b on 17
        entries and was already being counted as a field named `<non-json>`,
        which no frontend read could ever match but which is nonsense in the
        real-field set regardless. Task 8b took that from 17 entries to 29 and
        added `<blocked:...>`, so the general rule replaces the special case.
      - `[]`: the route was reached but the recorded shape has no keys at
        all (e.g. GET /api/kpi/otd/by-client returns an empty list against
        this harness's default seed data). This is a golden-master DATA gap,
        not a code defect, but it means "real fields unknown", not "real
        fields are zero", so it must be treated exactly like a placeholder.
    """
    entry = json.loads(GOLDEN.read_text(encoding="utf-8")).get(f"{method} {endpoint}")
    if not entry:
        return frozenset()
    names = set()
    for path in entry:
        if path.startswith("<"):
            continue
        segments = [s[:-2] if s.endswith("[]") else s for s in path.split(".")]
        segments = [s for s in segments if s]
        if segments:
            names.add(segments[0])
    return frozenset(names)


def coverage_of(endpoint: str, method: str = "GET") -> str:
    """Whether this extractor can say anything trustworthy about `endpoint`.

    Exists so a caller cannot mistake silence for assurance. A cross-check that
    prints "read-but-not-sent: []" looks identical whether the extractor examined
    the endpoint and found nothing wrong, or could not see it at all -- and the
    second is not a pass. Callers must branch on this rather than on emptiness.

    Three distinguishable states:

    - `COVERED` -- fields were found AND at least one intersects the route's
      real field names (from the golden master, see `_real_field_names`).
      This is the only state that means something was actually verified.
    - `NO_FIELDS_FOUND` -- the extractor found nothing, or found only fields
      that do not match any of the route's real fields (bleed). Also the
      verdict whenever the golden master itself carries no real field names
      for this route (a `<status:...>` entry or an empty shape) -- there is
      nothing to intersect against, so COVERED can never be trustworthy.
    - `NO_COVERAGE` -- known-blind (KNOWN_BLIND): a documented, structural
      extraction gap, independent of what today's bleed happens to contain.

    Until Task 8, this returned COVERED whenever `fields_read_by_frontend()`
    found ANY field name for `endpoint`, with no check that the fields found
    were the endpoint's own. Measured during the Task 7 pilot: 8 of the 24
    /api/kpi routes reported COVERED off bleed from unrelated code in the
    same frontend source file, with ZERO real field overlap (see
    task-8-brief.md's evidence table) -- a broken extractor and a working
    one were indistinguishable from this function's output. Fixed by
    requiring intersection with the route's real field names.
    """
    if endpoint in KNOWN_BLIND:
        return "NO_COVERAGE"
    found = fields_read_by_frontend().get(endpoint)
    if not found:
        return "NO_FIELDS_FOUND"
    real = _real_field_names(endpoint, method)
    return "COVERED" if found & real else "NO_FIELDS_FOUND"
