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

from unittest.mock import MagicMock

import pytest

from backend.auth.jwt import get_current_user
from backend.main import app


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
    ("POST", "/api/employees/upload/csv", ["operator"], "leader", 422),
    # These two accept an all-default body, so passing the guard yields 200.
    ("POST", "/api/reports/email-config", ["operator"], "leader", 200),
    ("POST", "/api/alerts/generate/check-all", ["operator"], "leader", 200),
    # Admin tier
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
