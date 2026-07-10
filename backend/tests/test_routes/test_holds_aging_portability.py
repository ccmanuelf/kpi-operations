"""The WIP-aging endpoints must return 200 (they build date-diff SQL via the
portable date_diff_days expression). On SQLite this also proves no behavior
regression; the MariaDB execution proof lives in test_mariadb_portability.py.
"""


def test_wip_aging_top_returns_200(test_client, admin_auth_headers):
    resp = test_client.get("/api/kpi/wip-aging/top", headers=admin_auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_wip_aging_trend_returns_200(test_client, admin_auth_headers):
    resp = test_client.get(
        "/api/kpi/wip-aging/trend?start_date=2026-06-01&end_date=2026-06-03",
        headers=admin_auth_headers,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
