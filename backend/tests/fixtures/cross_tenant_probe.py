"""Request machinery for the cross-tenant authorization matrix.

Enumerates every by-id route from the LIVE app and resolves each path
parameter to a row owned by a chosen tenant, so one request can be issued "as
tenant A, for tenant B's row". Assertions live in
``backend/tests/test_security/test_permission_matrix.py``; this module only
builds requests.

Route enumeration walks the app rather than a hand-written list: FastAPI holds
each ``include_router`` as an ``_IncludedRouter`` wrapper whose own path is
``None``, so the walk descends through ``original_router`` and re-applies the
mount prefix. That is what makes a NEW by-id route enter the probe set
automatically instead of shipping unclassified.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

from fastapi.routing import APIRoute

from backend.tests.fixtures.two_tenant import employee_of, int_pk, str_pk

_WRITE_SAFE_METHODS = {"HEAD", "OPTIONS"}


def flatten_routes(container: Any, prefix: str = "") -> list[tuple[str, APIRoute]]:
    """Every ``APIRoute`` reachable from ``container``, with its mounted path."""
    out: list[tuple[str, APIRoute]] = []
    for route in getattr(container, "routes", []):
        if isinstance(route, APIRoute):
            out.append((prefix + route.path, route))
        elif hasattr(route, "original_router"):
            sub_prefix = getattr(getattr(route, "include_context", None), "prefix", "") or ""
            out.extend(flatten_routes(route.original_router, prefix + sub_prefix))
        elif hasattr(route, "routes"):
            out.extend(flatten_routes(route, prefix))
        elif hasattr(route, "app") and hasattr(getattr(route, "app", None), "routes"):
            out.extend(flatten_routes(route.app, prefix))
    return out


def by_id_targets(app: Any) -> list[tuple[str, str]]:
    """Sorted ``(method, path)`` for every route carrying a path parameter."""
    targets: set[tuple[str, str]] = set()
    for path, route in flatten_routes(app):
        if "{" not in path:
            continue
        for method in (route.methods or set()) - _WRITE_SAFE_METHODS:
            targets.add((method, path))
    return sorted(targets, key=lambda t: (t[1], t[0]))


# (path prefix, param name, value factory). First match wins; an empty prefix
# is the family-agnostic default. Every value resolves to a row OWNED by the
# tenant passed in, which is what makes a cross-tenant request possible.
_PARAMS: tuple[tuple[str, str, Callable[[str], Any]], ...] = (
    ("/api/capacity/lines/", "line_id", int_pk),
    ("/api/capacity/calendar/", "entry_id", int_pk),
    ("/api/capacity/scenarios/", "scenario_id", int_pk),
    ("/api/kpi/calculate/", "entry_id", lambda c: str_pk(c, "PE")),
    ("/api/production/", "entry_id", lambda c: str_pk(c, "PE")),
    ("", "client_id", lambda c: c),
    ("", "shift_id", int_pk),
    ("", "line_id", int_pk),
    ("", "employee_id", employee_of),
    ("", "attendance_id", lambda c: str_pk(c, "AE")),
    ("", "assumption_id", int_pk),
    ("", "table_name", lambda c: "SHIFT"),
    ("", "record_pk", int_pk),
    ("", "break_id", int_pk),
    ("", "pattern", lambda c: "client_config:*"),
    ("", "calendar_date", lambda c: "2026-08-01"),
    ("", "coverage_id", int_pk),
    ("", "defect_type_id", lambda c: str_pk(c, "DT")),
    ("", "quality_entry_id", lambda c: str_pk(c, "QE")),
    ("", "inspection_id", lambda c: str_pk(c, "QE")),
    ("", "defect_detail_id", lambda c: str_pk(c, "DD")),
    ("", "downtime_id", lambda c: str_pk(c, "DE")),
    ("", "assignment_id", int_pk),
    ("", "equipment_id", int_pk),
    ("", "filter_type", lambda c: "production"),
    ("", "filter_id", int_pk),
    ("", "pool_id", int_pk),
    ("", "catalog_id", int_pk),
    ("", "hold_id", lambda c: str_pk(c, "HE")),
    ("", "product_id", int_pk),
    ("", "job_id", lambda c: str_pk(c, "JOB")),
    ("", "kpi_key", lambda c: "oee"),
    ("", "metric", lambda c: "oee"),
    ("", "result_id", int_pk),
    ("", "category", lambda c: f"{c}-CAT"),
    ("", "part_number", lambda c: str_pk(c, "PART")),
    ("", "dataset", lambda c: "production"),
    ("", "kpi_type", lambda c: "efficiency"),
    ("", "role", lambda c: "operator"),
    ("", "work_order_id", lambda c: str_pk(c, "WO")),
    ("", "user_id", lambda c: f"USR-{c}"),
    ("", "scenario_id", int_pk),
    ("", "status", lambda c: "RECEIVED"),
    ("", "detail_id", int_pk),
    ("", "header_id", int_pk),
    ("", "order_id", int_pk),
    ("", "schedule_id", int_pk),
    ("", "standard_id", int_pk),
    ("", "style_model", lambda c: f"{c}-STYLE"),
    ("", "item_code", lambda c: f"{c}-ITEM"),
    ("", "snapshot_id", int_pk),
    ("", "worksheet_name", lambda c: "lines"),
    ("", "alert_id", lambda c: str_pk(c, "AL")),
    ("", "entry_id", int_pk),
)

#: Values that satisfy a 422 so the request reaches the AUTHORIZATION layer.
#: A route that stops at body/query validation proves nothing about tenancy.
_QUERY_FILL: dict[str, Callable[[str], Any]] = {
    "client_id": lambda c: c,
    "start_date": lambda c: "2026-08-01",
    "end_date": lambda c: "2026-08-31",
    "date": lambda c: "2026-08-01",
    "bucket": lambda c: "week",
    "to_status": lambda c: "IN_PROGRESS",
    "template_id": lambda c: "standard",
    "metric": lambda c: "oee",
}
_BODY_FILL: dict[str, Callable[[str], Any]] = {
    "resolution_notes": lambda c: "probe",
    "completed_quantity": lambda c: 1,
    "actual_hours": lambda c: 1,
    "capacity_line_id": int_pk,
    "capacity_order_id": int_pk,
    "status": lambda c: "IN_PROGRESS",
    "to_status": lambda c: "IN_PROGRESS",
    "employee_id": employee_of,
}
#: Routes that reject an empty body with a hand-rolled 400 rather than a 422,
#: so the auto-fill loop never sees a validation detail to work from.
_PATH_BODY: dict[tuple[str, str], Callable[[str], dict[str, Any]]] = {
    ("POST", "/api/work-orders/{work_order_id}/link-capacity"): lambda c: {"capacity_order_id": int_pk(c)},
    ("PATCH", "/api/work-orders/{work_order_id}/status"): lambda c: {"status": "ON_HOLD"},
}
#: Multipart routes; ``json=`` would never satisfy them.
_PATH_FILES: dict[tuple[str, str], dict[str, Any]] = {
    ("POST", "/api/defect-types/upload/{client_id}"): {
        "file": ("d.csv", b"defect_code,defect_name\nCOLOR,Color\n", "text/csv")
    },
}


class UnresolvedParam(LookupError):
    """A path parameter with no entry in ``_PARAMS``.

    Raised rather than substituted with a placeholder: a literal ``{job_id}``
    in the URL 404s for the wrong reason and reads like a normal negative case.
    A new path parameter must be given a tenant-owned value here before its
    route can be probed.
    """


def resolve_param(path: str, param: str, tenant: str) -> str:
    for prefix, name, factory in _PARAMS:
        if name == param and path.startswith(prefix):
            return str(factory(tenant))
    raise UnresolvedParam(f"no tenant-owned value for {{{param}}} on {path}")


def url_for(path: str, tenant: str) -> str:
    """``path`` with every parameter bound to a row owned by ``tenant``."""
    url = re.sub(r"\{([^}]+)\}", lambda m: resolve_param(path, m.group(1).split(":")[0], tenant), path)
    assert "{" not in url and "}" not in url, f"unsubstituted path param in {url}"
    return url


def _fill_missing(response: Any, tenant: str, params: dict, body: dict) -> bool:
    try:
        detail = response.json()["detail"]
    except Exception:
        return False
    if not isinstance(detail, list):
        return False
    added = False
    for err in detail:
        loc: Iterable[Any] = err.get("loc") or []
        loc = list(loc)
        if len(loc) < 2 or err.get("type") != "missing":
            continue
        where, name = loc[0], loc[-1]
        if where == "query" and name not in params and name in _QUERY_FILL:
            params[name] = _QUERY_FILL[name](tenant)
            added = True
        elif where == "body" and name not in body and name in _BODY_FILL:
            body[name] = _BODY_FILL[name](tenant)
            added = True
    return added


def request_for_tenant(client: Any, method: str, path: str, tenant: str) -> Any:
    """Issue ``method path`` with every id bound to ``tenant``'s rows.

    Retries while a 422 names a field this module knows how to fill, so the
    request reaches authorization instead of dying in validation.
    """
    url = url_for(path, tenant)
    params: dict[str, Any] = {}
    body: dict[str, Any] = _PATH_BODY.get((method, path), lambda c: {})(tenant)
    files = _PATH_FILES.get((method, path))
    response = None
    for _ in range(6):
        kwargs: dict[str, Any] = {"params": params}
        if files is not None:
            kwargs["files"] = files
        else:
            kwargs["json"] = body
        response = client.request(method, url, **kwargs)
        if response.status_code != 422 or not _fill_missing(response, tenant, params, body):
            break
    return response
