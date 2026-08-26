"""
Route-level permission matrix tests (Run 7 T2.7, M-7).

Pins the three-tier guard model from docs/user-guide/10-roles-permissions.md:

- admin                      — system administration (users/clients, cache,
                               DB migrations, nightly batch triggers)
- planner (admin, poweruser) — capacity planning, scenario/workbook edits,
                               platform configuration
- supervisory (admin, poweruser, leader, legacy supervisor)
                             — operations master data, work orders, bulk
                               loads, simulation runs
- any authenticated user     — transactional data entry (the operator's job)

Guards run before body validation, so denied personas assert exactly 403 and
allowed personas assert exactly 422 (empty body rejected by validation —
proving they got PAST the guard).
"""

import re
from unittest.mock import MagicMock

import pytest

from backend.auth.jwt import get_current_user
from backend.main import app


def _capacity_write_targets() -> list[tuple[str, str]]:
    """Every (method, concrete mounted-path) write route under /api/capacity.

    Walks the live ``app`` so paths carry their full mount prefix (the real URL
    a client hits). FastAPI 0.138 holds each ``include_router`` as a wrapper
    whose own path/methods are ``None`` and which exposes
    ``effective_route_contexts()`` to expand into the underlying routes with
    prefixes applied (the restructuring that silently broke the write guard in
    PR #110); duck-type on that method to flatten. Path params get a placeholder
    — the guard resolves before path/body validation, so the value is irrelevant
    to the 403 decision.
    """
    write_methods = {"POST", "PUT", "PATCH", "DELETE"}

    def _flatten(routes):
        for route in routes:
            expand = getattr(route, "effective_route_contexts", None)
            if callable(expand):
                yield from expand()
            else:
                yield route

    targets: set[tuple[str, str]] = set()
    for route in _flatten(app.routes):
        path = getattr(route, "path", "")
        if not path.startswith("/api/capacity"):
            continue
        for method in (getattr(route, "methods", None) or set()) & write_methods:
            targets.add((method, re.sub(r"\{[^}]+\}", "1", path)))
    return sorted(targets)


CAPACITY_WRITE_TARGETS = _capacity_write_targets()


def _persona(role: str):
    u = MagicMock()
    u.role = role
    u.is_active = True
    u.user_id = f"USR-MATRIX-{role.upper()}"
    u.username = f"matrix_{role}"
    u.client_id_assigned = None if role in ("admin", "poweruser") else "ACME-MFG"
    return u


@pytest.fixture
def as_role(test_client):
    """Return a function that re-points get_current_user at a role persona.

    The module-scoped test_client fixture already overrides get_db; only the
    user identity is swapped here (importing conftest helpers directly would
    re-execute it as a second module with a separate engine).
    """

    def _set(role: str):
        app.dependency_overrides[get_current_user] = lambda: _persona(role)
        return test_client

    yield _set
    app.dependency_overrides.pop(get_current_user, None)


# (method, path, denied_roles, allowed_role, allowed_status)
# allowed_status 422 = empty body rejected by validation AFTER passing the guard.
MATRIX = [
    # Planner tier (admin/poweruser): capacity planning + configuration.
    # Capacity rows use admin as the allowed persona — those paths also pass
    # through the client-tenancy middleware, which only exempts admin for a
    # header-less override persona; the poweruser side of the planner guard
    # is pinned by the kpi-thresholds and client-config rows.
    ("POST", "/api/capacity/orders", ["operator", "leader", "supervisor"], "admin", 422),
    ("POST", "/api/capacity/calendar", ["operator", "leader"], "admin", 422),
    ("POST", "/api/capacity/bom", ["operator", "leader"], "admin", 422),
    # Empty threshold update body is a valid no-op, so passing the guard is 200.
    ("PUT", "/api/kpi-thresholds", ["operator", "leader"], "poweruser", 200),
    ("POST", "/api/client-config/", ["operator", "leader"], "admin", 422),
    # Supervisory tier (everyone but operator): ops master data, bulk, sims
    ("POST", "/api/employees", ["operator"], "leader", 422),
    ("POST", "/api/jobs", ["operator"], "leader", 422),
    ("POST", "/api/floating-pool", ["operator"], "leader", 422),
    ("POST", "/api/part-opportunities", ["operator"], "leader", 422),
    ("POST", "/api/v2/simulation/validate", ["operator"], "leader", 422),
    ("POST", "/api/v2/simulation/scenarios", ["operator"], "leader", 422),
    ("POST", "/api/production/batch-import", ["operator"], "supervisor", 422),
    # These two accept an all-default body, so passing the guard yields 200.
    ("POST", "/api/reports/email-config", ["operator"], "leader", 200),
    ("POST", "/api/alerts/generate/check-all", ["operator"], "leader", 200),
    # Planner tier CSV uploads (admin/poweruser)
    ("POST", "/api/floating-pool/upload/csv", ["operator", "leader", "supervisor"], "poweruser", 422),
    # Admin tier
    ("POST", "/api/employees/upload/csv", ["operator", "leader", "supervisor"], "admin", 422),
    ("POST", "/api/clients/upload/csv", ["operator", "leader", "supervisor"], "admin", 422),
    # Work order writes (_check_wo_write_permission, supervisory tier). Empty
    # body clears the guard for the allowed role and reaches the CRUD lookup,
    # where work order "1" doesn't exist in this fixture's empty DB => 404.
    # (Delay-classification's own field-level 403 — supervisory-only even for
    # a supervisory-gated route — is covered at the CRUD layer by
    # test_work_order_delay_classification.py; this row pins the route guard.)
    ("PUT", "/api/work-orders/1", ["operator", "viewer"], "supervisor", 404),
    # Audit trail reads (Phase A2), admin-only. Read endpoints rather than
    # writes, so they sit outside the write-tier rows above, but they belong
    # here for the reason this file exists: every other audit authz test
    # builds its own FastAPI() and mounts the router itself, so none of them
    # would notice audit_router being dropped from bootstrap/routers.py.
    # These rows walk the LIVE backend.main.app, so they pin the wiring too.
    # An admin GET over an empty AUDIT_ENTRY table is a legitimate 200
    # ({"entries": [], "total": 0, "trail_started_at": null}).
    ("GET", "/api/audit", ["operator", "viewer", "leader", "supervisor", "poweruser"], "admin", 200),
    ("GET", "/api/audit/HOLD_ENTRY/HOLD-1", ["operator", "viewer", "leader", "supervisor", "poweruser"], "admin", 200),
]


class TestPermissionMatrix:
    @pytest.mark.parametrize("method,path,denied,allowed,allowed_status", MATRIX)
    def test_denied_roles_get_403(self, as_role, method, path, denied, allowed, allowed_status):
        for role in denied:
            client = as_role(role)
            response = client.request(method, path, json={})
            assert response.status_code == 403, f"{role} on {method} {path}: got {response.status_code}"

    @pytest.mark.parametrize("method,path,denied,allowed,allowed_status", MATRIX)
    def test_allowed_role_passes_guard(self, as_role, method, path, denied, allowed, allowed_status):
        client = as_role(allowed)
        response = client.request(method, path, json={})
        assert response.status_code == allowed_status, f"{allowed} on {method} {path}: got {response.status_code}"

    def test_operator_transactional_entry_still_allowed(self, as_role):
        """The operator's documented job — data entry — must stay open.

        An empty body 422 (not 403) proves the operator passed authorization
        and only failed validation.
        """
        client = as_role("operator")
        for method, path in [
            ("POST", "/api/production"),
            ("POST", "/api/downtime"),
            ("POST", "/api/holds"),
            ("POST", "/api/attendance"),
        ]:
            response = client.request(method, path, json={})
            assert response.status_code == 422, f"operator on {method} {path}: got {response.status_code}"

    # Transactional data-entry write endpoints gated to the contributor tier
    # (every role except viewer) in the Run 7 role-model reconciliation.
    CONTRIBUTOR_WRITE_ENDPOINTS = [
        ("POST", "/api/production"),
        ("POST", "/api/downtime"),
        ("POST", "/api/attendance"),
        ("POST", "/api/quality/"),
        ("POST", "/api/holds"),
        ("POST", "/api/coverage"),
        ("POST", "/api/defects"),
    ]

    def test_viewer_cannot_write_transactional_data(self, as_role):
        """Viewer is read-only: every data-entry write must 403 (Run 7)."""
        client = as_role("viewer")
        for method, path in self.CONTRIBUTOR_WRITE_ENDPOINTS:
            response = client.request(method, path, json={})
            assert response.status_code == 403, f"viewer on {method} {path}: got {response.status_code}"

    def test_operator_is_a_contributor(self, as_role):
        """Operator (and above) keep data-entry access — 422 = passed the guard."""
        client = as_role("operator")
        for method, path in self.CONTRIBUTOR_WRITE_ENDPOINTS:
            response = client.request(method, path, json={})
            assert response.status_code != 403, f"operator wrongly denied on {method} {path}"

    def test_workflow_transition_no_longer_bypasses_wo_gate(self, as_role):
        """workflow.py's transition endpoint sidestepped the Run-6 work-order
        write gate with bare authentication — operators must now get 403."""
        client = as_role("operator")
        response = client.post("/api/workflow/work-orders/WO-X/transition", json={})
        assert response.status_code == 403

    def test_nightly_trigger_is_admin_only(self, as_role):
        response = as_role("leader").post("/api/metrics/calculate/run-nightly", json={})
        assert response.status_code == 403


class TestCapacityWriteGuardRequestLevel:
    """Request-level proof of ``require_capacity_write`` on EVERY capacity write
    route — the behavioral complement to
    ``test_write_access.test_write_routes_have_dependency`` (which only checks the
    dependency is *attached* by introspection).

    Pins the supervisor write-block that FastAPI 0.138's ``_IncludedRouter``
    restructuring silently dropped (PR #110): with the guard gone, POWERUSER
    cleared the planner guard and reached body validation (422) instead of being
    denied (403). A green unit suite missed that regression because no test
    exercised these sub-resources (lines/standards/scenarios/…) over HTTP — this
    closes that blind spot for the whole capacity write surface, not a sample.
    """

    def test_capacity_write_routes_discovered(self):
        assert CAPACITY_WRITE_TARGETS, "no capacity write routes discovered to guard"

    @pytest.mark.parametrize("method,path", CAPACITY_WRITE_TARGETS)
    def test_supervisor_blocked_on_every_capacity_write(self, as_role, method, path):
        """POWERUSER (supervisor) is denied write on every capacity route, and the
        denial comes from ``require_capacity_write`` specifically (no capacity
        write route is admin-gated, so the planner guard passes a poweruser).
        Asserting the guard's exact detail string — not a generic substring —
        rules out a 403 from a different guard (auth/tenancy) masquerading as the
        capacity block."""
        response = as_role("poweruser").request(method, path, json={})
        assert response.status_code == 403, f"supervisor not blocked on {method} {path}: got {response.status_code}"
        # Exact message raised by require_capacity_write — unique to that guard.
        assert (
            response.json().get("detail") == "Supervisors do not have write access to Capacity Planning data"
        ), f"403 on {method} {path} did not originate from require_capacity_write: {response.json()}"

    @pytest.mark.parametrize("method,path", CAPACITY_WRITE_TARGETS)
    def test_admin_passes_every_capacity_write_guard(self, as_role, method, path):
        """Admin is the sole role that may write capacity data; clearing the
        guard (neither 401 authn nor 403 authz) proves the route is not a blanket
        deny — which would make the supervisor assertion vacuous — and that admin
        passes both the planner guard and ``require_capacity_write``. A post-guard
        422 (empty body) or 2xx is the expected outcome."""
        response = as_role("admin").request(method, path, json={})
        assert response.status_code not in (
            401,
            403,
        ), f"admin did not clear the guard on {method} {path}: got {response.status_code}"


# ===========================================================================
# Cross-tenant by-id authorization (found 2026-08-25, fixed on
# fix/cross-tenant-by-id-authz)
#
# A scoped user could read — and soft-delete — another client's rows through
# by-id routes: GET/PUT/DELETE /api/shifts/{id} and friends resolved the row by
# id alone and never checked its owner. PR #144 made the LIST routes uniform
# and missed these. Everything below is measured against a two-tenant database
# built by INSERT (not by the seeder, which writes zero rows for five of the
# tables involved).
# ===========================================================================

CROSS_TENANT_403 = "Cross-tenant denial is 403 — the code verify_client_access already returns."


def _two_tenant_client():
    """Fresh two-tenant DB + a TestClient acting as tenant A's supervisor.

    A supervisor (not an admin) is essential: get_user_client_filter returns
    None for ADMIN/POWERUSER, meaning "all clients", so an admin persona can
    never exercise cross-tenant denial.
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
    actor = db.query(User).filter(User.client_id_assigned == TENANT_A).one()

    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: actor
    return TestClient(app, raise_server_exceptions=False), db, engine


@pytest.fixture
def tenant_a_client():
    """Function-scoped: several probed routes soft-delete or rename rows."""
    client, db, engine = _two_tenant_client()
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        from backend.database import get_db

        app.dependency_overrides.pop(get_db, None)
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
    # DELETE floating-pool is 404 for its OWN tenant too: soft_delete() on a
    # model with no is_active column returns False (the seven-broken-DELETEs
    # bug, out of scope here). The authorization check still runs first, so the
    # cross-tenant answer is a 403 and not a misleading 404.
    ("DELETE", "/api/floating-pool/{pool_id}", 404, 403),
]

# Routes where client_id arrives as a QUERY parameter and replaced the
# role-derived filter with no authorization. Same defect, different carrier;
# found by extending the sweep to every route declaring a client_id query.
CLIENT_ID_QUERY_MATRIX = [
    ("GET", "/api/employees", 200, 403),
    ("GET", "/api/employee-line-assignments/", 200, 403),
    ("GET", "/api/equipment/", 200, 403),
    ("GET", "/api/production-lines/tree", 200, 403),
    ("GET", "/api/production-lines/unlinked", 200, 403),
    ("POST", "/api/production-lines/sync-capacity", 200, 403),
    ("GET", "/api/reports/email-config", 200, 403),
    ("GET", "/api/export/attendance", 200, 403),
    ("GET", "/api/export/downtime-events", 200, 403),
    ("GET", "/api/export/employees", 200, 403),
    ("GET", "/api/export/holds", 200, 403),
    ("GET", "/api/export/products", 200, 403),
    ("GET", "/api/export/quality-inspections", 200, 403),
    ("GET", "/api/export/shifts", 200, 403),
    ("GET", "/api/export/work-orders", 200, 403),
]


def _by_id_targets():
    from backend.tests.fixtures.cross_tenant_probe import by_id_targets

    return by_id_targets(app)


BY_ID_TARGETS = _by_id_targets()


class TestCrossTenantByIdRoutes:
    """Behavioural cross-tenant probe. Grep is not a substitute: an earlier
    text search for scope markers in endpoint bodies produced 139 candidates,
    most of them false, because the real checks live in the CRUD layer. Only a
    request answers the question."""

    def test_by_id_route_set_is_discovered(self):
        """The universal guard below is vacuous if the walk finds nothing."""
        assert len(BY_ID_TARGETS) >= 190, f"only {len(BY_ID_TARGETS)} by-id routes discovered"

    def test_tenants_are_asymmetric(self):
        """Fixture integrity. Aggregate routes (calendar hours, Bradford
        factor, inferred cycle time) return identical bodies for two tenants
        holding identical numbers, which makes an unscoped route look scoped.
        Every measured quantity must differ."""
        from backend.tests.fixtures.two_tenant import TENANT_A, TENANT_B, asym

        keys = [
            "cal_shift1_hours",
            "units_produced",
            "run_time_hours",
            "units_inspected",
            "defect_count",
            "downtime_minutes",
            "absence_hours",
        ]
        identical = [k for k in keys if asym(TENANT_A, k) == asym(TENANT_B, k)]
        assert identical == [], f"tenants share these values, so routes reading them cannot discriminate: {identical}"

    @pytest.mark.parametrize("method,path,own_status,other_status", BY_ID_MATRIX)
    def test_own_tenant_still_reaches_its_own_row(self, tenant_a_client, method, path, own_status, other_status):
        """Non-vacuity control: the fix must not deny the rightful owner."""
        from backend.tests.fixtures.cross_tenant_probe import request_for_tenant
        from backend.tests.fixtures.two_tenant import TENANT_A

        response = request_for_tenant(tenant_a_client, method, path, TENANT_A)
        assert response.status_code == own_status, f"{method} {path} own-tenant: {response.status_code}"

    @pytest.mark.parametrize("method,path,own_status,other_status", BY_ID_MATRIX)
    def test_cross_tenant_by_id_request_is_denied(self, tenant_a_client, method, path, own_status, other_status):
        from backend.tests.fixtures.cross_tenant_probe import request_for_tenant
        from backend.tests.fixtures.two_tenant import TENANT_B

        response = request_for_tenant(tenant_a_client, method, path, TENANT_B)
        assert (
            response.status_code == other_status
        ), f"{method} {path} cross-tenant: {response.status_code}. {CROSS_TENANT_403}"

    @pytest.mark.parametrize("method,path,own_status,other_status", CLIENT_ID_QUERY_MATRIX)
    def test_own_tenant_client_id_query_still_works(self, tenant_a_client, method, path, own_status, other_status):
        from backend.tests.fixtures.two_tenant import TENANT_A

        response = tenant_a_client.request(method, path, params={"client_id": TENANT_A}, json={})
        assert response.status_code == own_status, f"{method} {path} own-tenant: {response.status_code}"

    @pytest.mark.parametrize("method,path,own_status,other_status", CLIENT_ID_QUERY_MATRIX)
    def test_cross_tenant_client_id_query_is_denied(self, tenant_a_client, method, path, own_status, other_status):
        from backend.tests.fixtures.two_tenant import TENANT_B

        response = tenant_a_client.request(method, path, params={"client_id": TENANT_B}, json={})
        assert (
            response.status_code == other_status
        ), f"{method} {path} cross-tenant: {response.status_code}. {CROSS_TENANT_403}"

    @pytest.mark.parametrize("method,path", BY_ID_TARGETS)
    def test_no_by_id_route_returns_other_tenants_data(self, tenant_a_client, method, path):
        """The structural guard, and the reason this is not two point fixes.

        Protection here does NOT ride on id format (see the report): it rides
        on whether the data path performs an explicit tenant check. So the
        guard is behavioural and covers the WHOLE by-id surface — a new route
        joins BY_ID_TARGETS automatically and must pass on the day it ships.

        Only a success may not carry tenant B's marker; a denial legitimately
        names the client it refused ("cannot access client 'TEN-B'").
        """
        from backend.tests.fixtures.cross_tenant_probe import request_for_tenant
        from backend.tests.fixtures.two_tenant import TENANT_B

        response = request_for_tenant(tenant_a_client, method, path, TENANT_B)
        if not 200 <= response.status_code < 300:
            return
        assert (
            TENANT_B not in response.text
        ), f"{method} {path} answered {response.status_code} carrying tenant B's data: {response.text[:200]}"

    def test_unassigned_employee_is_visible_to_every_tenant(self, tenant_a_client):
        """An employee with client_id_assigned NULL is a shared floating-pool
        resource (the meaning EmployeeCreate documents), not a hidden one.
        Pins the fail-open half of verify_employee_access so a later tightening
        is a deliberate choice rather than an accident."""
        from backend.tests.fixtures.two_tenant import EMPLOYEE_SHARED

        response = tenant_a_client.get(f"/api/employees/{EMPLOYEE_SHARED}")
        assert response.status_code == 200, f"shared employee denied: {response.text[:200]}"

    def test_alerts_listing_is_scoped_without_any_client_id(self, tenant_a_client):
        """The worst shape: no crafted request needed. /api/alerts/ returned
        every tenant's alerts to any authenticated caller who simply omitted
        client_id."""
        from backend.tests.fixtures.two_tenant import TENANT_B

        response = tenant_a_client.get("/api/alerts/")
        assert response.status_code == 200
        assert TENANT_B not in response.text, f"unscoped alert listing leaked tenant B: {response.text[:200]}"

    def test_employee_listing_is_scoped_without_any_client_id(self, tenant_a_client):
        from backend.tests.fixtures.two_tenant import TENANT_B

        response = tenant_a_client.get("/api/employees")
        assert response.status_code == 200
        assert TENANT_B not in response.text, f"unscoped employee listing leaked tenant B: {response.text[:200]}"
