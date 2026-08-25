"""Extract, per endpoint, which response fields the frontend actually reads.

This is the second of two safety nets for the response-model refactor. A
Pydantic response model DROPS any key it does not declare. The golden master
(tasks 1-3) catches a field that DISAPPEARS from a response; this extractor
catches the opposite failure — a field the UI reads that a hand-written
response model never declares, which would otherwise be silently baked in as
a regression.

LIMITATION, stated rather than discovered later: a dynamic read — `row[key]`
where `key` is computed — is invisible to this extractor. The golden master
is the backstop for that case: it does not care why a field is read, only
that it is still sent. Do not treat a clean extractor run as proof no field
is needed.
"""

import pathlib
import re

FRONTEND = pathlib.Path(__file__).resolve().parents[3] / "frontend" / "src"

# api.get('/kpi/dashboard') and friends. The leading /api comes from the axios
# baseURL, so endpoint literals in the client are written without it. Some
# call sites chain the method on its own line (`return api\n  .get(...)`,
# e.g. getAbsenteeism / getDefectRates in kpi.ts) so whitespace, including a
# newline, is allowed between `api` and the method call.
_ENDPOINT = re.compile(r"api\s*\.\s*(?:get|post|put|delete)\(\s*['\"`]([^'\"`]+)")

# d?.by_reason / data.total / response.data.rate -- the read forms this codebase
# actually uses, confirmed by reading services/api/kpi.ts.
_FIELD = re.compile(r"\b(?:d|data|res|response|result)\??\.(\w+)")


def fields_read_by_frontend() -> dict:
    usage: dict = {}
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
                key = endpoint if endpoint.startswith("/api") else "/api" + endpoint
                usage.setdefault(key, set()).update(fields)
    return usage
