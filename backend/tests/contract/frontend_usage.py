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

import pathlib
import re

FRONTEND = pathlib.Path(__file__).resolve().parents[3] / "frontend" / "src"
API_DIR = FRONTEND / "services" / "api"

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


def coverage_of(endpoint: str) -> str:
    """Whether this extractor can say anything trustworthy about `endpoint`.

    Exists so a caller cannot mistake silence for assurance. A cross-check that
    prints "read-but-not-sent: []" looks identical whether the extractor examined
    the endpoint and found nothing wrong, or could not see it at all -- and the
    second is not a pass. Callers must branch on this rather than on emptiness.
    """
    if endpoint in KNOWN_BLIND:
        return "NO_COVERAGE"
    return "COVERED" if fields_read_by_frontend().get(endpoint) else "NO_FIELDS_FOUND"
