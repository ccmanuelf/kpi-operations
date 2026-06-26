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
    ("POST", "/api/admin/database/migrate", ["operator", "leader", "supervisor"], "admin", 422),
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
