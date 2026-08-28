"""Request machinery for the cross-tenant authorization matrix.

Enumerates every by-id route from the LIVE app and resolves each path
parameter to a row owned by a chosen tenant, so one request can be issued "as
tenant A, for tenant B's row". Assertions live in
``backend/tests/test_security/test_permission_matrix.py``; this module holds
only the request machinery, the expectation table and the client fixtures —
data and plumbing, so every assertion can stay in the one test file without
pushing it past the 500-line limit.

Route enumeration walks the app rather than a hand-written list: FastAPI holds
each ``include_router`` as an ``_IncludedRouter`` wrapper whose own path is
``None``, so the walk descends through ``original_router`` and re-applies the
mount prefix. That is what makes a NEW by-id route enter the probe set
automatically instead of shipping unclassified.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

import pytest
from fastapi.routing import APIRoute

from backend.auth.jwt import get_current_user
from backend.main import app

from backend.tests.fixtures.two_tenant import employee_of, int_pk, str_pk

CROSS_TENANT_403 = "Cross-tenant denial is 403 — the code verify_client_access already returns."

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


# The cross-tenant matrix itself, and the client that drives it. Data and
# plumbing live here so every ASSERTION stays in the test files.


def _two_tenant_client(actor_user_id: str | None = None):
    """Fresh two-tenant DB + a TestClient acting as one persona.

    Defaults to tenant A's supervisor: a supervisor (not an admin) is essential
    for the DENIAL direction, since get_user_client_filter returns None for
    ADMIN/POWERUSER. ``actor_user_id`` selects an over-denial persona instead.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker

    from backend.database import get_db
    from backend.orm.user import User
    from backend.tests.conftest import clone_template_engine
    from backend.tests.fixtures.two_tenant import TENANT_A, build_two_tenant_db

    engine = clone_template_engine()
    db = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    build_two_tenant_db(db)
    if actor_user_id is None:
        actor = db.query(User).filter(User.client_id_assigned == TENANT_A).one()
    else:
        actor = db.query(User).filter(User.user_id == actor_user_id).one()

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: actor
    return TestClient(app, raise_server_exceptions=False), db, engine


@pytest.fixture
def tenant_a_env():
    """One two-tenant database, exposed as both a client and a Session.

    tenant_a_client and tenant_a_db derive from THIS fixture rather than each
    building their own. They used to call _two_tenant_client() separately,
    which made two databases while `app.dependency_overrides[get_db]` — a
    global — pointed at whichever ran last. A test asking for both got a
    Session and a client on different databases, and whether it worked
    depended on the order the parameters happened to be listed in.
    """
    client, db, engine = _two_tenant_client()
    try:
        yield client, db
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        from backend.database import get_db

        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


@pytest.fixture
def tenant_a_client(tenant_a_env):
    """Function-scoped: several probed routes soft-delete or rename rows."""
    return tenant_a_env[0]


@pytest.fixture
def tenant_a_db(tenant_a_env):
    """The Session behind tenant_a_client — same database, always."""
    return tenant_a_env[1]


@pytest.fixture
def two_tenant_as():
    """Return a factory: user_id -> TestClient on a fresh two-tenant DB.

    Function-scoped and one database per persona, because several probed
    routes soft-delete or rename the rows the next persona would read.
    """
    made: list[Any] = []

    def _make(actor_user_id: str):
        client, db, engine = _two_tenant_client(actor_user_id)
        made.append((db, engine))
        return client

    yield _make

    app.dependency_overrides.pop(get_current_user, None)
    from backend.database import get_db

    app.dependency_overrides.pop(get_db, None)
    for db, engine in made:
        db.close()
        engine.dispose()


# (method, path, expected status for OWN tenant, expected status for the OTHER
# tenant). Every row returned 2xx-with-the-other-tenant's-row before the fix;
# the OWN column is the non-vacuity control — a denial proves nothing if the
# route is broken for its rightful owner too.
BY_ID_MATRIX = [
    ("GET", "/api/shifts/{shift_id}", 200, 403),
    ("PUT", "/api/shifts/{shift_id}", 200, 403),
    ("DELETE", "/api/shifts/{shift_id}", 204, 403),
    ("GET", "/api/production-lines/{line_id}", 200, 403),
    ("PUT", "/api/production-lines/{line_id}", 200, 403),
    ("DELETE", "/api/production-lines/{line_id}", 204, 403),
    ("POST", "/api/production-lines/{line_id}/link-capacity", 200, 403),
    ("DELETE", "/api/production-lines/{line_id}/link-capacity", 200, 403),
    ("PUT", "/api/break-times/{break_id}", 200, 403),
    ("DELETE", "/api/break-times/{break_id}", 204, 403),
    ("GET", "/api/equipment/{equipment_id}", 200, 403),
    ("PUT", "/api/equipment/{equipment_id}", 200, 403),
    ("DELETE", "/api/equipment/{equipment_id}", 204, 403),
    ("GET", "/api/employee-line-assignments/employee/{employee_id}", 200, 403),
    ("GET", "/api/employee-line-assignments/line/{line_id}", 200, 403),
    ("PUT", "/api/employee-line-assignments/{assignment_id}", 200, 403),
    ("DELETE", "/api/employee-line-assignments/{assignment_id}", 200, 403),
    ("GET", "/api/floating-pool/{pool_id}", 200, 403),
    ("PUT", "/api/floating-pool/{pool_id}", 200, 403),
    ("GET", "/api/employees/{employee_id}", 200, 403),
    ("PUT", "/api/employees/{employee_id}", 200, 403),
    ("POST", "/api/employees/{employee_id}/floating-pool/assign", 200, 403),
    ("POST", "/api/employees/{employee_id}/floating-pool/remove", 200, 403),
    ("GET", "/api/attendance/kpi/bradford-factor/{employee_id}", 200, 403),
    ("GET", "/api/qr/employee/{employee_id}/image", 200, 403),
    ("GET", "/api/calendar/{calendar_date}", 200, 403),
    ("GET", "/api/inference/cycle-time/{product_id}", 200, 403),
    ("GET", "/api/alerts/{alert_id}", 200, 403),
    # State MUTATIONS, and the reason a crash must never be mistaken for a
    # denial: these three had no tenant check at all. They answered 500 only
    # because current_user.get("user_id") blew up AFTER the status assignment,
    # so the one-line .get() -> .user_id fix would have turned three silent
    # crashes into three live cross-tenant writes.
    ("POST", "/api/alerts/{alert_id}/acknowledge", 200, 403),
    ("POST", "/api/alerts/{alert_id}/resolve", 200, 403),
    ("POST", "/api/alerts/{alert_id}/dismiss", 200, 403),
    # This read 404 for its OWN tenant until S1: soft_delete() on a model with
    # no is_active column returned False, so the route raised 404 for every id.
    # The entry documented that honestly and scoped it out; S1 fixed it for all
    # eleven such endpoints, so the own-tenant answer is now the 204 the route
    # always advertised. The cross-tenant answer is unchanged, and was never
    # part of the defect: the authorization check runs first, which is why this
    # was a 403 and not a misleading 404 even while the delete was broken.
    ("DELETE", "/api/floating-pool/{pool_id}", 204, 403),
]

# Routes where client_id arrives as a QUERY parameter and replaced the
# role-derived filter with no authorization. Same defect, different carrier;
# found by extending the sweep to every route declaring a client_id query.
# (method, path, own status, cross-tenant status, extra query params). The
# extras only satisfy other REQUIRED parameters so the request reaches
# authorization instead of dying in validation.
_RANGE = {"start_date": "2026-08-01", "end_date": "2026-08-31"}
CLIENT_ID_QUERY_MATRIX = [
    ("GET", "/api/employees", 200, 403, {}),
    ("GET", "/api/employee-line-assignments/", 200, 403, {}),
    ("GET", "/api/equipment/", 200, 403, {}),
    # /shared returns [] for both tenants here, so only the status
    # discriminates — which is exactly why it needs a row.
    ("GET", "/api/equipment/shared", 200, 403, {}),
    ("GET", "/api/production-lines/tree", 200, 403, {}),
    ("GET", "/api/production-lines/unlinked", 200, 403, {}),
    ("POST", "/api/production-lines/sync-capacity", 200, 403, {}),
    ("GET", "/api/reports/email-config", 200, 403, {}),
    # The two calendar aggregates leak tenant B's TOTALS, not its ids, so no
    # marker check can see them — see test_calendar_aggregates_are_per_tenant.
    ("GET", "/api/calendar/working-days", 200, 403, _RANGE),
    ("GET", "/api/calendar/summary", 200, 403, _RANGE),
    ("GET", "/api/export/attendance", 200, 403, {}),
    ("GET", "/api/export/downtime-events", 200, 403, {}),
    ("GET", "/api/export/employees", 200, 403, {}),
    ("GET", "/api/export/holds", 200, 403, {}),
    ("GET", "/api/export/production-entries", 200, 403, {}),
    ("GET", "/api/export/products", 200, 403, {}),
    ("GET", "/api/export/quality-inspections", 200, 403, {}),
    ("GET", "/api/export/shifts", 200, 403, {}),
    ("GET", "/api/export/work-orders", 200, 403, {}),
]


# Declarations that keep the universal guard from going blind. It used to
# early-return on any non-2xx and then only look for the tenant id in the body:
# blind on every 2xx route, trivially satisfied by a 204's empty body, and
# classing a 500 as a denial — how GET /api/alerts/{alert_id} hid a real leak
# for a whole pass. Both lists are gated two-sided by the tests that read them.

#: (method, path) -> why a cross-tenant request legitimately answers 2xx.
#: An UNDECLARED 2xx is a finding, so a new leak cannot slip through as one.
LITERAL_PARAM = "literal_param"  # the parameter is not a tenant id at all
NO_TENANT_ROWS = "no_tenant_rows"  # correctly scoped: nothing of B's comes back

CROSS_TENANT_2XX_ALLOWED: dict[tuple[str, str], str] = {
    ("GET", "/api/filters/default/{filter_type}"): LITERAL_PARAM,
    ("GET", "/api/kpi/{metric}/cause"): LITERAL_PARAM,
    ("GET", "/api/pivot/{dataset}"): LITERAL_PARAM,
    ("GET", "/api/pivot/{dataset}/csv"): LITERAL_PARAM,
    ("GET", "/api/preferences/defaults/{role}"): LITERAL_PARAM,
    ("GET", "/api/work-orders/status/{status}"): LITERAL_PARAM,
    ("GET", "/api/attendance/by-employee/{employee_id}"): NO_TENANT_ROWS,
    ("GET", "/api/capacity/orders/{order_id}/work-orders"): NO_TENANT_ROWS,
    ("GET", "/api/coverage/by-shift/{shift_id}"): NO_TENANT_ROWS,
    ("GET", "/api/defects/by-quality-entry/{quality_entry_id}"): NO_TENANT_ROWS,
    ("GET", "/api/floating-pool/check-availability/{employee_id}"): NO_TENANT_ROWS,
    ("GET", "/api/part-opportunities/category/{category}"): NO_TENANT_ROWS,
    ("GET", "/api/quality/by-work-order/{work_order_id}"): NO_TENANT_ROWS,
    ("GET", "/api/work-orders/{work_order_id}/jobs"): NO_TENANT_ROWS,
}

#: (method, path) -> why a cross-tenant request answers 5xx. A crash is NOT a
#: denial: these three had no tenant check at all and only looked safe because
#: they blew up. Kept so the taxonomy stays explicit and the day they stop
#: crashing, the guard re-classifies them instead of staying quiet.
CROSS_TENANT_5XX_KNOWN: dict[tuple[str, str], str] = {
    ("POST", "/api/defect-types/upload/{client_id}"): (
        "the route's `except Exception` swallows ClientAccessError into a 500 "
        "'Failed to process defect type catalog' — it denies, but reports the "
        "denial as a server error"
    ),
}


#: Quantities that must differ between the tenants; a symmetric fixture makes
#: an unscoped aggregate route indistinguishable from a scoped one.
ASYMMETRY_KEYS = (
    "cal_shift1_hours",
    "units_produced",
    "run_time_hours",
    "units_inspected",
    "defect_count",
    "downtime_minutes",
    "absence_hours",
)
