"""
Self-registration lockdown tests (Run 7 C-2).

POST /api/auth/register was an unauthenticated endpoint that accepted a
caller-supplied role (including 'admin'). These tests pin the new contract:

- registration is available only in DEMO_MODE (403 otherwise)
- the created account is always role='operator' (lowercase, matching every
  authorization guard) regardless of what the caller sends
- a self-registered account cannot reach admin endpoints
"""

import uuid

from backend.config import settings


def _payload(**overrides):
    uid = uuid.uuid4().hex[:8]
    base = {
        "username": f"lockdown_{uid}",
        "email": f"lockdown_{uid}@test.com",
        "password": "SecurePassword123!",
        "full_name": "Lockdown Test User",
    }
    base.update(overrides)
    return base


class TestRegisterLockdown:
    def test_register_disabled_when_demo_mode_off(self, test_client, monkeypatch):
        """Outside demo mode, self-registration returns 403."""
        monkeypatch.setattr(settings, "DEMO_MODE", False)
        response = test_client.post("/api/auth/register", json=_payload())
        assert response.status_code == 403

    def test_register_enabled_in_demo_mode(self, test_client):
        """In demo mode (suite default), self-registration works."""
        response = test_client.post("/api/auth/register", json=_payload())
        assert response.status_code == 201

    def test_register_ignores_requested_admin_role(self, test_client):
        """A caller-supplied role is discarded; the account is always operator."""
        response = test_client.post("/api/auth/register", json=_payload(role="admin"))
        assert response.status_code == 201
        assert response.json()["role"] == "operator"

    def test_register_stores_lowercase_enum_role(self, test_client):
        """Stored role must match the lowercase guards (no role.upper() artifact)."""
        response = test_client.post("/api/auth/register", json=_payload())
        assert response.status_code == 201
        assert response.json()["role"] == "operator"

    def test_register_cannot_self_assign_client(self, test_client):
        """A caller-supplied client_id_assigned is discarded (tenant isolation)."""
        response = test_client.post("/api/auth/register", json=_payload(client_id_assigned="ACME-MFG"))
        assert response.status_code == 201
        assert response.json()["client_id_assigned"] is None

    def test_registered_user_cannot_reach_admin_endpoints(self, test_client):
        """End to end: register requesting admin, log in, get denied on /api/users."""
        payload = _payload(role="admin")
        register = test_client.post("/api/auth/register", json=payload)
        assert register.status_code == 201

        login = test_client.post(
            "/api/auth/login", json={"username": payload["username"], "password": payload["password"]}
        )
        assert login.status_code == 200
        token = login.json()["access_token"]

        response = test_client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403
