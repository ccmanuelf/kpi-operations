"""
Tenant Isolation Tests for Hold Catalog CRUD Operations.

Verifies that a user from Client A cannot modify (update/deactivate)
hold status or hold reason catalog entries belonging to Client B.
Admin users (client_id_assigned=None) bypass the tenant filter.
"""

import pytest

from backend.database import get_db
from backend.main import app
from backend.orm.hold_status_catalog import HoldStatusCatalog
from backend.orm.hold_reason_catalog import HoldReasonCatalog
from backend.tests.fixtures.factories import TestDataFactory
from backend.tests.fixtures.auth_fixtures import (
    create_test_token,
    AuthenticatedClient,
)


@pytest.fixture(scope="function")
def tenant_isolation_setup(test_client, transactional_db):
    """
    Set up two clients (A and B), each with one hold status and one hold reason
    catalog entry, plus supervisor users scoped to each client and an admin user.
    """
    db = transactional_db

    app.dependency_overrides[get_db] = lambda: db

    # Create two clients
    TestDataFactory.create_client(db, client_id="TENANT-A", client_name="Tenant A")
    TestDataFactory.create_client(db, client_id="TENANT-B", client_name="Tenant B")
    db.flush()

    # Create hold status entries
    status_a = HoldStatusCatalog(
        client_id="TENANT-A",
        status_code="STATUS_A",
        display_name="Status A",
        is_default=False,
        is_active=True,
        sort_order=10,
    )
    status_b = HoldStatusCatalog(
        client_id="TENANT-B",
        status_code="STATUS_B",
        display_name="Status B",
        is_default=False,
        is_active=True,
        sort_order=10,
    )
    db.add_all([status_a, status_b])
    db.flush()

    # Create hold reason entries
    reason_a = HoldReasonCatalog(
        client_id="TENANT-A",
        reason_code="REASON_A",
        display_name="Reason A",
        is_default=False,
        is_active=True,
        sort_order=10,
    )
    reason_b = HoldReasonCatalog(
        client_id="TENANT-B",
        reason_code="REASON_B",
        display_name="Reason B",
        is_default=False,
        is_active=True,
        sort_order=10,
    )
    db.add_all([reason_a, reason_b])
    db.commit()

    # Capture auto-generated PKs
    status_a_id = status_a.catalog_id
    status_b_id = status_b.catalog_id
    reason_a_id = reason_a.catalog_id
    reason_b_id = reason_b.catalog_id

    # Create users via TestDataFactory (generates user_id properly)
    supervisor_a = TestDataFactory.create_user(
        db,
        username="supervisor_a_tenant",
        role="supervisor",
        client_id="TENANT-A",
        password="TestPass123!",
    )
    supervisor_b = TestDataFactory.create_user(
        db,
        username="supervisor_b_tenant",
        role="supervisor",
        client_id="TENANT-B",
        password="TestPass123!",
    )
    admin_user = TestDataFactory.create_user(
        db,
        username="admin_tenant_test",
        role="admin",
        client_id=None,
        password="TestPass123!",
    )
    db.commit()

    auth_a = AuthenticatedClient(test_client, create_test_token(supervisor_a))
    auth_b = AuthenticatedClient(test_client, create_test_token(supervisor_b))
    auth_admin = AuthenticatedClient(test_client, create_test_token(admin_user))

    yield {
        "db": db,
        "auth_a": auth_a,
        "auth_b": auth_b,
        "auth_admin": auth_admin,
        "status_a_id": status_a_id,
        "status_b_id": status_b_id,
        "reason_a_id": reason_a_id,
        "reason_b_id": reason_b_id,
    }

    app.dependency_overrides.clear()


# =========================================================================
# Hold Status -- Cross-Tenant Rejection
# =========================================================================


class TestHoldStatusTenantIsolation:
    """Verify cross-tenant rejection for hold status update/deactivate."""

    def test_user_a_cannot_update_status_of_client_b(self, tenant_isolation_setup):
        """Supervisor A tries to PUT a hold status owned by Client B -> 404."""
        ctx = tenant_isolation_setup
        resp = ctx["auth_a"].put(
            f"/api/hold-catalogs/statuses/{ctx['status_b_id']}",
            json={"display_name": "Hacked by A"},
        )
        assert resp.status_code == 404, (
            f"Expected 404 for cross-tenant update, got {resp.status_code}: {resp.text}"
        )

    def test_user_a_cannot_deactivate_status_of_client_b(self, tenant_isolation_setup):
        """Supervisor A tries to DELETE a hold status owned by Client B -> 404."""
        ctx = tenant_isolation_setup
        resp = ctx["auth_a"].delete(
            f"/api/hold-catalogs/statuses/{ctx['status_b_id']}",
        )
        assert resp.status_code == 404, (
            f"Expected 404 for cross-tenant deactivate, got {resp.status_code}: {resp.text}"
        )

    def test_user_b_cannot_update_status_of_client_a(self, tenant_isolation_setup):
        """Supervisor B tries to PUT a hold status owned by Client A -> 404."""
        ctx = tenant_isolation_setup
        resp = ctx["auth_b"].put(
            f"/api/hold-catalogs/statuses/{ctx['status_a_id']}",
            json={"display_name": "Hacked by B"},
        )
        assert resp.status_code == 404

    def test_user_b_cannot_deactivate_status_of_client_a(self, tenant_isolation_setup):
        """Supervisor B tries to DELETE a hold status owned by Client A -> 404."""
        ctx = tenant_isolation_setup
        resp = ctx["auth_b"].delete(
            f"/api/hold-catalogs/statuses/{ctx['status_a_id']}",
        )
        assert resp.status_code == 404

    def test_user_a_can_update_own_status(self, tenant_isolation_setup):
        """Supervisor A can update their own client's status -> 200."""
        ctx = tenant_isolation_setup
        resp = ctx["auth_a"].put(
            f"/api/hold-catalogs/statuses/{ctx['status_a_id']}",
            json={"display_name": "Updated by A"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Updated by A"

    def test_user_a_can_deactivate_own_status(self, tenant_isolation_setup):
        """Supervisor A can deactivate their own client's status -> 204."""
        ctx = tenant_isolation_setup
        resp = ctx["auth_a"].delete(
            f"/api/hold-catalogs/statuses/{ctx['status_a_id']}",
        )
        assert resp.status_code == 204


# =========================================================================
# Hold Reason -- Cross-Tenant Rejection
# =========================================================================


class TestHoldReasonTenantIsolation:
    """Verify cross-tenant rejection for hold reason update/deactivate."""

    def test_user_a_cannot_update_reason_of_client_b(self, tenant_isolation_setup):
        """Supervisor A tries to PUT a hold reason owned by Client B -> 404."""
        ctx = tenant_isolation_setup
        resp = ctx["auth_a"].put(
            f"/api/hold-catalogs/reasons/{ctx['reason_b_id']}",
            json={"display_name": "Hacked by A"},
        )
        assert resp.status_code == 404

    def test_user_a_cannot_deactivate_reason_of_client_b(self, tenant_isolation_setup):
        """Supervisor A tries to DELETE a hold reason owned by Client B -> 404."""
        ctx = tenant_isolation_setup
        resp = ctx["auth_a"].delete(
            f"/api/hold-catalogs/reasons/{ctx['reason_b_id']}",
        )
        assert resp.status_code == 404

    def test_user_b_cannot_update_reason_of_client_a(self, tenant_isolation_setup):
        """Supervisor B tries to PUT a hold reason owned by Client A -> 404."""
        ctx = tenant_isolation_setup
        resp = ctx["auth_b"].put(
            f"/api/hold-catalogs/reasons/{ctx['reason_a_id']}",
            json={"display_name": "Hacked by B"},
        )
        assert resp.status_code == 404

    def test_user_b_cannot_deactivate_reason_of_client_a(self, tenant_isolation_setup):
        """Supervisor B tries to DELETE a hold reason owned by Client A -> 404."""
        ctx = tenant_isolation_setup
        resp = ctx["auth_b"].delete(
            f"/api/hold-catalogs/reasons/{ctx['reason_a_id']}",
        )
        assert resp.status_code == 404

    def test_user_b_can_update_own_reason(self, tenant_isolation_setup):
        """Supervisor B can update their own client's reason -> 200."""
        ctx = tenant_isolation_setup
        resp = ctx["auth_b"].put(
            f"/api/hold-catalogs/reasons/{ctx['reason_b_id']}",
            json={"display_name": "Updated by B"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Updated by B"

    def test_user_b_can_deactivate_own_reason(self, tenant_isolation_setup):
        """Supervisor B can deactivate their own client's reason -> 204."""
        ctx = tenant_isolation_setup
        resp = ctx["auth_b"].delete(
            f"/api/hold-catalogs/reasons/{ctx['reason_b_id']}",
        )
        assert resp.status_code == 204


# =========================================================================
# Admin Bypass -- Can Modify Any Client's Catalog Entries
# =========================================================================


class TestAdminBypassTenantFilter:
    """Admin users (client_id_assigned=None) can modify any client's entries."""

    def test_admin_can_update_status_of_client_a(self, tenant_isolation_setup):
        ctx = tenant_isolation_setup
        resp = ctx["auth_admin"].put(
            f"/api/hold-catalogs/statuses/{ctx['status_a_id']}",
            json={"display_name": "Admin Updated A"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Admin Updated A"

    def test_admin_can_update_status_of_client_b(self, tenant_isolation_setup):
        ctx = tenant_isolation_setup
        resp = ctx["auth_admin"].put(
            f"/api/hold-catalogs/statuses/{ctx['status_b_id']}",
            json={"display_name": "Admin Updated B"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Admin Updated B"

    def test_admin_can_deactivate_reason_of_client_a(self, tenant_isolation_setup):
        ctx = tenant_isolation_setup
        resp = ctx["auth_admin"].delete(
            f"/api/hold-catalogs/reasons/{ctx['reason_a_id']}",
        )
        assert resp.status_code == 204

    def test_admin_can_update_reason_of_client_b(self, tenant_isolation_setup):
        ctx = tenant_isolation_setup
        resp = ctx["auth_admin"].put(
            f"/api/hold-catalogs/reasons/{ctx['reason_b_id']}",
            json={"display_name": "Admin Updated Reason B"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Admin Updated Reason B"
