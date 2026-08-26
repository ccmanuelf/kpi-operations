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
from backend.tests.fixtures import cross_tenant_probe
from backend.tests.fixtures.cross_tenant_probe import (
    CROSS_TENANT_2XX_ALLOWED,
    CROSS_TENANT_5XX_KNOWN,
    LITERAL_PARAM,
    by_id_targets,
    request_for_tenant,
    url_for,
)
from backend.tests.fixtures.two_tenant import TENANT_A, TENANT_B, asym, marker_values


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
# Cross-tenant by-id authorization (found 2026-08-25).
#
# A scoped user could read — and soft-delete — another client's rows: by-id
# routes resolved the row by id alone and never checked its owner. PR #144
# made the LIST routes uniform and missed these. Measured against a two-tenant
# database built by INSERT, not by the seeder (which writes zero rows for five
# of the tables involved).
# ===========================================================================

CROSS_TENANT_403 = cross_tenant_probe.CROSS_TENANT_403
BY_ID_TARGETS = by_id_targets(app)
BY_ID_MATRIX = cross_tenant_probe.BY_ID_MATRIX
CLIENT_ID_QUERY_MATRIX = cross_tenant_probe.CLIENT_ID_QUERY_MATRIX
tenant_a_client = cross_tenant_probe.tenant_a_client
two_tenant_as = cross_tenant_probe.two_tenant_as
tenant_a_db = cross_tenant_probe.tenant_a_db


class TestCrossTenantByIdRoutes:
    """Behavioural cross-tenant probe. Grep is not a substitute: a text search
    for scope markers in endpoint bodies gave 139 candidates, most of them
    false — the real checks live in the CRUD layer. Only a request answers it."""

    def test_by_id_route_set_is_discovered(self):
        """The universal guard below is vacuous if the walk finds nothing."""
        assert len(BY_ID_TARGETS) >= 190, f"only {len(BY_ID_TARGETS)} by-id routes discovered"

    def test_tenants_are_asymmetric(self):
        """Fixture integrity: aggregate routes return identical bodies for
        tenants holding identical numbers, hiding an unscoped route."""

        identical = [k for k in cross_tenant_probe.ASYMMETRY_KEYS if asym(TENANT_A, k) == asym(TENANT_B, k)]
        assert identical == [], f"tenants share these values, so routes reading them cannot discriminate: {identical}"

    @pytest.mark.parametrize("method,path,own_status,other_status", BY_ID_MATRIX)
    def test_own_tenant_still_reaches_its_own_row(self, tenant_a_client, method, path, own_status, other_status):
        """Non-vacuity control: the fix must not deny the rightful owner."""

        response = request_for_tenant(tenant_a_client, method, path, TENANT_A)
        assert response.status_code == own_status, f"{method} {path} own-tenant: {response.status_code}"

    @pytest.mark.parametrize("method,path,own_status,other_status", BY_ID_MATRIX)
    def test_cross_tenant_by_id_request_is_denied(self, tenant_a_client, method, path, own_status, other_status):

        response = request_for_tenant(tenant_a_client, method, path, TENANT_B)
        assert (
            response.status_code == other_status
        ), f"{method} {path} cross-tenant: {response.status_code}. {CROSS_TENANT_403}"

    @pytest.mark.parametrize("method,path,own_status,other_status,extra", CLIENT_ID_QUERY_MATRIX)
    def test_own_tenant_client_id_query_still_works(
        self, tenant_a_client, method, path, own_status, other_status, extra
    ):

        response = tenant_a_client.request(method, path, params={"client_id": TENANT_A, **extra}, json={})
        assert response.status_code == own_status, f"{method} {path} own-tenant: {response.status_code}"

    @pytest.mark.parametrize("method,path,own_status,other_status,extra", CLIENT_ID_QUERY_MATRIX)
    def test_cross_tenant_client_id_query_is_denied(
        self, tenant_a_client, method, path, own_status, other_status, extra
    ):

        response = tenant_a_client.request(method, path, params={"client_id": TENANT_B, **extra}, json={})
        assert (
            response.status_code == other_status
        ), f"{method} {path} cross-tenant: {response.status_code}. {CROSS_TENANT_403}"

    @pytest.mark.parametrize("method,path", BY_ID_TARGETS)
    def test_no_by_id_route_returns_other_tenants_data(self, tenant_a_client, method, path):
        """The structural guard: protection rides on whether the data path
        performs a tenant check, not on id format, so this covers the whole
        by-id surface and a new route must be classified the day it ships.

        Three blind spots in the first version, all closed: a 5xx counted as a
        denial (how a leak on GET /api/alerts/{alert_id} survived a whole pass);
        a 2xx passed merely for lacking the tenant id, which a 204 does
        trivially; and a body carrying tenant B's NUMBERS, not its ids — the
        calendar aggregates — read as clean."""

        response = request_for_tenant(tenant_a_client, method, path, TENANT_B)
        status = response.status_code

        if status >= 500:
            assert (method, path) in CROSS_TENANT_5XX_KNOWN, (
                f"{method} {path} answered {status} to a cross-tenant request. A crash is not a "
                f"denial — declare it in CROSS_TENANT_5XX_KNOWN with the reason, or fix it."
            )
            return

        if not 200 <= status < 300:
            return

        reason = CROSS_TENANT_2XX_ALLOWED.get((method, path))
        assert reason is not None, (
            f"{method} {path} answered {status} to a request for tenant B's row. Either it leaks "
            f"and needs a check, or it is safe and needs a CROSS_TENANT_2XX_ALLOWED entry saying why."
        )

        if reason == LITERAL_PARAM:
            # Prove the declaration rather than trusting it: a literal param
            # means both tenants produce the SAME url, so there was never a
            # cross-tenant request to make.
            assert url_for(path, TENANT_A) == url_for(
                path, TENANT_B
            ), f"{method} {path} is declared LITERAL_PARAM but its url differs per tenant"
            return

        body = response.text
        assert TENANT_B not in body, f"{method} {path} answered {status} carrying tenant B's id: {body[:200]}"
        leaked = [value for value in marker_values(TENANT_B) if value in body]
        assert leaked == [], (
            f"{method} {path} answered {status} carrying values that only tenant B's rows produce "
            f"{leaked} — a body can leak another tenant without ever naming it: {body[:200]}"
        )

    @pytest.mark.parametrize(
        "declared,floor,ceiling,label",
        [
            (CROSS_TENANT_2XX_ALLOWED, 200, 299, "still answers 2xx"),
            (CROSS_TENANT_5XX_KNOWN, 500, 599, "still crashes"),
        ],
    )
    def test_declarations_still_describe_reality(self, tenant_a_client, declared, floor, ceiling, label):
        """Two-sided gate: an allow-list nobody re-checks rots into folklore."""
        stale = []
        for method, path in declared:
            status = request_for_tenant(tenant_a_client, method, path, TENANT_B).status_code
            if not floor <= status <= ceiling:
                stale.append((method, path, status))
        assert stale == [], f"declared entries that no longer {label}: {stale}"

    @pytest.mark.parametrize("persona", ["USR-ADMIN", "USR-POWER", "USR-LEADER-AB", "USR-LEADER-WS"])
    @pytest.mark.parametrize("method,path,own_status,other_status", BY_ID_MATRIX)
    def test_authorized_personas_are_not_over_denied(
        self, two_tenant_as, persona, method, path, own_status, other_status
    ):
        """Over-denial is the failure mode a tenant fix causes, and no
        single-tenant test would notice: admin/poweruser get client_ids=None
        ("all") and a leader can hold several, so a check falling through to
        deny still looks correct. Requesting tenant B's row as one of these must
        return exactly what the owner gets. The whitespace persona passes only
        because _get_clients_from_legacy_field strips each token."""

        client = two_tenant_as(persona)
        response = request_for_tenant(client, method, path, TENANT_B)
        assert response.status_code == own_status, (
            f"{persona} over-denied on {method} {path}: {response.status_code} "
            f"(expected {own_status}, the status the owner gets)"
        )

    @pytest.mark.parametrize("persona", ["USR-ADMIN", "USR-LEADER-AB", "USR-LEADER-WS", "USR-JUNCTION"])
    @pytest.mark.parametrize("method,path,own_status,other_status,extra", CLIENT_ID_QUERY_MATRIX)
    def test_authorized_personas_are_not_over_denied_on_query_routes(
        self, two_tenant_as, persona, method, path, own_status, other_status, extra
    ):
        """USR-JUNCTION's assignment exists only in USER_CLIENT_ASSIGNMENT, so
        any call site that calls verify_client_access WITHOUT a db session
        cannot see it and denies this leader their own client — which is what
        /api/reports/email-config did before it grew a db dependency."""
        client = two_tenant_as(persona)
        response = client.request(method, path, params={"client_id": TENANT_A, **extra}, json={})
        assert (
            response.status_code == own_status
        ), f"{persona} over-denied on {method} {path}: {response.status_code} (expected {own_status})"

    def test_unassigned_employee_is_visible_to_every_tenant(self, tenant_a_client):
        """An employee with client_id_assigned NULL is a shared floating-pool
        resource (the meaning EmployeeCreate documents), not a hidden one.
        Pins the fail-open half of verify_employee_access so a later tightening
        is a deliberate choice rather than an accident."""
        from backend.tests.fixtures.two_tenant import EMPLOYEE_SHARED

        response = tenant_a_client.get(f"/api/employees/{EMPLOYEE_SHARED}")
        assert response.status_code == 200, f"shared employee denied: {response.text[:200]}"

    def test_alerts_listing_is_scoped_without_any_client_id(self, tenant_a_client):
        """The worst shape, no crafted request needed: /api/alerts/ returned
        every tenant's alerts to a caller who simply omitted client_id."""

        response = tenant_a_client.get("/api/alerts/")
        assert response.status_code == 200
        assert TENANT_B not in response.text, f"unscoped alert listing leaked tenant B: {response.text[:200]}"

    def test_employee_listing_agrees_with_by_id_route_on_colliding_client_ids(self, tenant_a_client):
        """A listing must never be MORE permissive than the by-id route.
        `LIKE '%TEN-A%'` also matches 'TEN-A-WEST', so the listing showed an
        employee GET /api/employees/{id} refuses with 403. Armed the moment one
        client id contains another (a plain 'DEMO' would pull in all DEMO-*)."""
        from backend.tests.fixtures.two_tenant import EMPLOYEE_LOOKALIKE, TENANT_A_LOOKALIKE

        listing = tenant_a_client.get("/api/employees")
        assert listing.status_code == 200
        assert (
            TENANT_A_LOOKALIKE not in listing.text
        ), f"listing leaked the look-alike client's employee: {listing.text[:200]}"

        by_id = tenant_a_client.get(f"/api/employees/{EMPLOYEE_LOOKALIKE}")
        assert by_id.status_code == 403, f"by-id route disagrees with the listing: {by_id.status_code}"

    @pytest.mark.parametrize("wanted,expected", cross_tenant_probe.TOKEN_CASES)
    def test_client_token_clause_matches_whole_tokens_only(self, tenant_a_db, wanted, expected):
        """Direct test of the clause both halves of the employee surface share.

        A substring LIKE matches 'ACME' inside 'ACME-WEST' and 'ACMES', and
        treats the '_' in seed's SAMPLE_REF as a wildcard — either way the
        listing returns rows the by-id route refuses."""
        from backend.middleware.client_auth import client_token_clause
        from backend.orm.employee import Employee

        cross_tenant_probe.seed_token_rows(tenant_a_db)
        matched = {
            e.employee_id
            for e in tenant_a_db.query(Employee)
            .filter(Employee.employee_id >= 9000, client_token_clause(Employee.client_id_assigned, wanted))
            .all()
        }
        assert matched == expected, f"{wanted!r} matched {matched}"

    def test_calendar_aggregates_are_per_tenant(self, tenant_a_client):
        """The calendar routes leak tenant B's TOTALS, never its ids; asserting
        tenant A's own number is what makes a removed check visible."""

        response = tenant_a_client.get(
            "/api/calendar/summary",
            params={"client_id": TENANT_A, "start_date": "2026-08-01", "end_date": "2026-08-31"},
        )
        assert response.status_code == 200
        assert response.json()["total_planned_hours"] == float(asym(TENANT_A, "cal_shift1_hours"))

    def test_employee_listing_is_scoped_without_any_client_id(self, tenant_a_client):

        response = tenant_a_client.get("/api/employees")
        assert response.status_code == 200
        assert TENANT_B not in response.text, f"unscoped employee listing leaked tenant B: {response.text[:200]}"
