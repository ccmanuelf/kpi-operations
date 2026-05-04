"""
Smoke test: every paramless GET returns non-500.

This is a regression guard for schema-drift bugs where handler code
references ORM columns/modules/classes that don't exist on the current
schema. The D2 closeout audit (2026-05-03) surfaced three such bugs in
production code paths that had ZERO direct test coverage:

  1. /api/my-shift/{summary,stats,activity} → ProductionEntry.date,
     QualityEntry.defect_quantity, etc. — none exist on current ORM
  2. /api/alerts/config/ → AlertCategory enum vs DB-seeded values drift
  3. /api/reports/{type}/excel → from backend.orm.quality import
     QualityInspection — module doesn't exist

Cost of this test: a few seconds per CI run.
Coverage: every URL the OpenAPI spec advertises with no required
inputs that an admin can simply fetch and expect a non-500 response.

What this test deliberately does NOT do:
  - assert specific status codes (200 vs 401 vs 404 are all fine; only
    5xx is a backend regression)
  - assert response payload shapes (that's the job of the per-route
    suites)
  - cover POST/PUT/DELETE (those need bodies — they're tested per-route)
  - cover endpoints with required path or query params (those tests
    live with the per-route suites that know the right values)

Add an entry to `_KNOWN_NON_GET_OR_INFRA` if a path is a known
non-application endpoint (e.g. /metrics from a middleware) that should
be skipped without flagging.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Set

import pytest
from fastapi.testclient import TestClient

from backend.auth.jwt import get_current_user
from backend.main import app


# Paths the smoke test deliberately skips. Empty for now; reserve for
# infra/middleware/static endpoints that don't represent app behavior.
_SKIP_PATHS: Set[str] = set()


def _mock_admin() -> SimpleNamespace:
    """Mock admin user for routes that pass through `Depends(get_current_user)`.

    SimpleNamespace (not MagicMock) so attribute access doesn't
    auto-create mock objects that fail Pydantic string validation when
    routes like `GET /api/auth/me` or `GET /api/predictions/dashboard/all`
    serialize the user. Carries every field downstream Pydantic models
    are known to read.
    """
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        # Identity
        id=1,
        user_id="USER-SMOKE",
        username="smoke_admin",
        email="smoke_admin@test.local",
        full_name="Smoke Admin",
        # Role / multi-tenancy
        role="admin",
        client_id="ACME-MFG",
        client_id_assigned=None,
        # State
        is_active=True,
        # Timestamps
        created_at=now,
        updated_at=now,
        last_login=None,
    )


def _has_required_path_or_query(operation: Dict[str, Any]) -> bool:
    """True when the GET operation requires a path or query param.

    We skip these because:
      - path params: we'd need to know a real ID (handled by per-route suites)
      - required query: the test would need to know domain-specific values
    """
    for p in operation.get("parameters", []):
        in_ = p.get("in")
        if in_ == "path":
            return True
        if in_ == "query" and p.get("required"):
            return True
    return False


def _collect_paramless_gets(spec: Dict[str, Any]) -> List[str]:
    """Walk the OpenAPI spec, return paths that have a paramless GET."""
    out: List[str] = []
    for path, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue
        op = methods.get("get")
        if not op:
            continue
        if "{" in path:  # path templating
            continue
        if path in _SKIP_PATHS:
            continue
        if _has_required_path_or_query(op):
            continue
        out.append(path)
    return sorted(out)


@pytest.fixture(scope="module")
def smoke_client():
    """TestClient with admin auth pre-wired (bypasses Depends(get_current_user))."""
    app.dependency_overrides[get_current_user] = _mock_admin
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_smoke_no_5xx_on_paramless_get(smoke_client: TestClient) -> None:
    """For every paramless GET, the server must not 5xx.

    A 500 here means a handler is broken — likely schema drift, broken
    import, or a routing-shadow bug. 401/403/404 are acceptable: those
    are role/auth/missing-data outcomes the front-end can render.
    """
    spec = smoke_client.get("/openapi.json").json()
    paths = _collect_paramless_gets(spec)
    assert paths, "OpenAPI spec returned no paramless GETs — fixture is wrong"

    failures: List[str] = []
    for path in paths:
        resp = smoke_client.get(path)
        if resp.status_code >= 500:
            # Capture body for diagnostics — truncate to keep test output sane.
            body = resp.text[:200]
            failures.append(f"{resp.status_code} {path} :: {body}")

    assert not failures, (
        f"{len(failures)} paramless GET(s) returned 5xx — likely schema drift, "
        f"broken imports, or routing-shadow bugs:\n" + "\n".join(failures)
    )


def test_smoke_collected_paths_under_test(smoke_client: TestClient) -> None:
    """Sanity check: we're collecting a non-trivial number of paths.

    Guards against the OpenAPI fetch silently returning empty (e.g. if
    the test client runs without the lifespan context that registers
    routes). At time of D2-closeout the count was ~120; if it drops by
    more than ~20% something is wrong with the fixture.
    """
    spec = smoke_client.get("/openapi.json").json()
    paths = _collect_paramless_gets(spec)
    assert len(paths) >= 80, (
        f"Only {len(paths)} paramless GET paths collected — expected at "
        "least 80. The smoke test is likely under-covering the API surface."
    )
