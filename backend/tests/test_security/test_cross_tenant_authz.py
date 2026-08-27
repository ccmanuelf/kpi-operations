"""Cross-tenant authorization matrix.

Split out of test_permission_matrix.py, which it outgrew: same estate, same
fixtures, same single matrix — two files only because the repo caps a file at
500 lines. test_permission_matrix.py keeps the role-tier guards; this file
keeps the tenant guards.
"""

import pytest

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
tenant_a_env = cross_tenant_probe.tenant_a_env
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

    @pytest.mark.parametrize("blank", ["", "   ", ",", " , "])
    def test_blank_client_assignment_is_not_shared(self, tenant_a_client, tenant_a_db, blank):
        """NULL means shared; blank does NOT.

        `EmployeeUpdate.client_id_assigned` has no min_length and
        PUT /api/employees/{id} is supervisor-tier, so treating a blank string
        as "unowned" let a supervisor publish an employee they own to every
        tenant by writing "". The listing never showed it either (it admits
        only IS NULL), so the by-id route was MORE permissive than the listing
        — B3 in mirror image.
        """
        from backend.orm.employee import Employee

        tenant_a_db.add(
            Employee(
                employee_id=9500,
                employee_code="BLANK-E1",
                employee_name="Blank Assignment",
                client_id_assigned=blank,
            )
        )
        tenant_a_db.commit()

        by_id = tenant_a_client.get("/api/employees/9500")
        assert by_id.status_code == 403, f"blank assignment {blank!r} granted by-id access: {by_id.text[:200]}"

        listing = tenant_a_client.get("/api/employees")
        assert listing.status_code == 200
        assert "BLANK-E1" not in listing.text, "listing and by-id route disagree about a blank assignment"

    @pytest.mark.parametrize(
        "employee,expected_detail",
        [
            (None, "Access denied: no employee record to authorize"),
            (object(), "Access denied: employee record does not expose client_id_assigned"),
        ],
    )
    def test_verify_employee_access_fails_closed(self, employee, expected_detail):
        """`getattr(row, "client_id_assigned", None) or ""` turned "cannot read
        the field" into "no owners" into "shared" into GRANTED. A helper that
        cannot inspect what it authorizes on must deny."""
        from unittest.mock import MagicMock

        from backend.middleware.client_auth import ClientAccessError, verify_employee_access

        user = MagicMock()
        user.role = "supervisor"
        user.username = "sup"
        user.client_id_assigned = TENANT_A
        with pytest.raises(ClientAccessError) as exc:
            verify_employee_access(user, employee)
        assert exc.value.status_code == 403
        # Assert the REASON, not just the code: a fail-open getattr still
        # raises here, only via the blank-assignment branch, which would make
        # this test pass while the sentinel it exists to pin is gone.
        assert exc.value.detail == expected_detail

    def test_verify_employee_access_fails_closed_even_for_admin(self):
        """The fail-closed branch sits BEFORE the admin bypass on purpose: an
        uninspectable row is a caller bug, and silently granting it to the one
        role that can see every tenant is the worst place to be lenient."""
        from unittest.mock import MagicMock

        from backend.middleware.client_auth import ClientAccessError, verify_employee_access

        admin = MagicMock()
        admin.role = "admin"
        admin.username = "admin_all"
        with pytest.raises(ClientAccessError):
            verify_employee_access(admin, None)

    def test_supervisor_cannot_rewrite_an_employees_client_assignment(self, tenant_a_client):
        """Passing the tenant check on the CURRENT owner does not entitle the
        caller to change who the owner is. Reassignment is a planner action
        with its own endpoint that verifies access to the TARGET client."""
        from backend.tests.fixtures.two_tenant import EMPLOYEE_A

        moved = tenant_a_client.put(f"/api/employees/{EMPLOYEE_A}", json={"client_id_assigned": TENANT_B})
        assert moved.status_code == 403, f"supervisor moved an employee to another tenant: {moved.text[:200]}"

        blanked = tenant_a_client.put(f"/api/employees/{EMPLOYEE_A}", json={"client_id_assigned": ""})
        assert blanked.status_code == 403, f"supervisor blanked an assignment: {blanked.text[:200]}"

        unchanged = tenant_a_client.put(
            f"/api/employees/{EMPLOYEE_A}", json={"client_id_assigned": TENANT_A, "department": "Cutting"}
        )
        assert unchanged.status_code == 200, "a no-op assignment must not be rejected"

    def test_system_wide_alerts_survive_an_explicit_client_filter(self, tenant_a_db, tenant_a_client):
        """`... AND client_id = 'X'` dropped every NULL row, so a comment
        claiming system-wide alerts "stay visible" was false on the branch a
        dashboard takes."""
        from backend.orm.alert import Alert

        tenant_a_db.add(
            Alert(
                alert_id="GLOBAL-AL-1",
                client_id=None,
                category="quality",
                severity="critical",
                title="System-wide alert",
                message="affects everyone",
            )
        )
        tenant_a_db.commit()

        narrowed = tenant_a_client.get("/api/alerts/", params={"client_id": TENANT_A})
        assert narrowed.status_code == 200
        assert "GLOBAL-AL-1" in narrowed.text, "system-wide alert vanished when narrowed to a client"

    def test_only_an_all_client_caller_may_mutate_a_system_wide_alert(self, tenant_a_db, tenant_a_client):
        """A client-less alert is readable by everyone but writable only by a
        caller with all-client scope: acknowledge_alert stamps the caller's
        user_id into a row every other tenant can read."""
        from backend.orm.alert import Alert

        tenant_a_db.add(
            Alert(
                alert_id="GLOBAL-AL-2",
                client_id=None,
                category="quality",
                severity="critical",
                title="System-wide alert",
                message="affects everyone",
            )
        )
        tenant_a_db.commit()

        readable = tenant_a_client.get("/api/alerts/GLOBAL-AL-2")
        assert readable.status_code == 200, "system-wide alerts must stay readable"

        mutated = tenant_a_client.post("/api/alerts/GLOBAL-AL-2/acknowledge", json={})
        assert mutated.status_code == 403, f"scoped caller mutated a system-wide alert: {mutated.text[:200]}"

        tenant_a_db.expire_all()
        assert tenant_a_db.query(Alert).filter(Alert.alert_id == "GLOBAL-AL-2").one().status == "active"

    def test_admin_may_mutate_a_system_wide_alert(self, two_tenant_as):
        """Non-vacuity: the denial above must not be a blanket block."""
        client = two_tenant_as("USR-ADMIN")
        from backend.orm.alert import Alert  # noqa: F401

        created = client.post(
            "/api/alerts/",
            json={
                "client_id": None,
                "category": "quality",
                "severity": "critical",
                "title": "System-wide",
                "message": "affects everyone",
            },
        )
        assert created.status_code == 201, created.text[:200]
        alert_id = created.json()["alert_id"]
        acked = client.post(f"/api/alerts/{alert_id}/acknowledge", json={})
        assert acked.status_code == 200, f"admin blocked from a system-wide alert: {acked.text[:200]}"

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
