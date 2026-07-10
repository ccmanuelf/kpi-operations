"""Role ↔ client-assignment invariant on the admin user API (all-client roles carry
no client; scoped roles require one). Backend mirror of the Add-User UI rules."""

STRONG = "Str0ng#Pass1"  # pragma: allowlist secret


def _payload(**over):
    base = {
        "username": "rc_user",
        "email": "rc_user@example.com",
        "password": STRONG,
        "full_name": "RC User",
        "role": "operator",
        "client_id_assigned": "CLIENT-A",
    }
    base.update(over)
    return base


class TestCreateRoleClientInvariant:
    def test_admin_with_client_rejected(self, test_client, admin_auth_headers):
        r = test_client.post(
            "/api/users", json=_payload(username="adm1", email="a1@e.com", role="admin"), headers=admin_auth_headers
        )
        assert r.status_code == 422

    def test_poweruser_with_client_rejected(self, test_client, admin_auth_headers):
        r = test_client.post(
            "/api/users", json=_payload(username="pow1", email="p1@e.com", role="poweruser"), headers=admin_auth_headers
        )
        assert r.status_code == 422

    def test_operator_without_client_rejected(self, test_client, admin_auth_headers):
        r = test_client.post(
            "/api/users",
            json=_payload(username="opt1", email="o1@e.com", role="operator", client_id_assigned=None),
            headers=admin_auth_headers,
        )
        assert r.status_code == 422

    def test_viewer_without_client_rejected(self, test_client, admin_auth_headers):
        r = test_client.post(
            "/api/users",
            json=_payload(username="vwr1", email="v1@e.com", role="viewer", client_id_assigned=""),
            headers=admin_auth_headers,
        )
        assert r.status_code == 422

    def test_admin_without_client_ok(self, test_client, admin_auth_headers):
        r = test_client.post(
            "/api/users",
            json=_payload(username="adm2", email="a2@e.com", role="admin", client_id_assigned=None),
            headers=admin_auth_headers,
        )
        assert r.status_code == 201

    def test_operator_with_client_ok(self, test_client, admin_auth_headers):
        r = test_client.post(
            "/api/users", json=_payload(username="opt2", email="o2@e.com", role="operator"), headers=admin_auth_headers
        )
        assert r.status_code == 201

    def test_leader_with_multi_client_ok(self, test_client, admin_auth_headers):
        r = test_client.post(
            "/api/users",
            json=_payload(username="ldr1", email="l1@e.com", role="leader", client_id_assigned="C1,C2"),
            headers=admin_auth_headers,
        )
        assert r.status_code == 201


class TestUpdateRoleClientInvariant:
    def _create_operator(self, test_client, admin_auth_headers, uname):
        r = test_client.post(
            "/api/users",
            json=_payload(username=uname, email=f"{uname}@e.com", role="operator", client_id_assigned="CLIENT-A"),
            headers=admin_auth_headers,
        )
        assert r.status_code == 201
        return r.json()["user_id"]

    def test_update_to_admin_keeping_client_rejected(self, test_client, admin_auth_headers):
        uid = self._create_operator(test_client, admin_auth_headers, "upd_usr1")
        r = test_client.put(f"/api/users/{uid}", json={"role": "admin"}, headers=admin_auth_headers)
        assert r.status_code == 422

    def test_update_to_admin_clearing_client_ok(self, test_client, admin_auth_headers):
        uid = self._create_operator(test_client, admin_auth_headers, "upd_usr2")
        r = test_client.put(
            f"/api/users/{uid}", json={"role": "admin", "client_id_assigned": ""}, headers=admin_auth_headers
        )
        assert r.status_code == 200

    def test_update_clearing_client_on_scoped_role_rejected(self, test_client, admin_auth_headers):
        uid = self._create_operator(test_client, admin_auth_headers, "upd_usr3")
        r = test_client.put(f"/api/users/{uid}", json={"client_id_assigned": ""}, headers=admin_auth_headers)
        assert r.status_code == 422
