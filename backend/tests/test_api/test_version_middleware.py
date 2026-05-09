"""
APIVersionMiddleware regression tests.

Covers the Location-header normalisation that was added after a real
production bug: requests arriving at /api/v1/<route> whose handler
emits a 3xx redirect (most commonly FastAPI's slash-redirect for
routes registered with a trailing slash) used to receive an absolute
Location pointing back at the backend host. In dev that bypasses the
Vite proxy and triggers a cross-origin redirect, which strips the
Authorization header → spurious 401 → forced /login. The middleware
now (a) re-adds /v1 to Location paths and (b) makes the Location
relative so the redirect stays same-origin.
"""

from fastapi.testclient import TestClient


class TestAPIVersionMiddlewareLocationRewrite:
    """The Location header must be relative and include /v1 when the
    original request was /api/v1/..."""

    def test_v1_slash_redirect_location_is_relative_and_keeps_v1(self, test_client: TestClient):
        """A slashless GET on a slash-routed v1 endpoint redirects with a
        path-only Location that includes /api/v1/.
        """
        # Quality entries route is `/api/quality/` (trailing slash) →
        # FastAPI emits 307 for the slashless form.
        response = test_client.get("/api/v1/quality", follow_redirects=False)

        assert response.status_code == 307
        location = response.headers.get("location", "")
        msg = f"Location should be relative and v1-prefixed; got {location!r}"
        assert location.startswith("/api/v1/"), msg
        # And the body of the path matches the route — i.e. /v1 was
        # restored, not silently dropped.
        assert location == "/api/v1/quality/"

    def test_non_v1_redirect_location_is_unchanged(self, test_client: TestClient):
        """Requests that did NOT arrive at /api/v1/... pass through
        unchanged — no /v1 inserted, no scheme stripping.
        """
        response = test_client.get("/api/quality", follow_redirects=False)

        assert response.status_code == 307
        location = response.headers.get("location", "")
        # Backwards compatibility: legacy /api/<path> behaviour is
        # whatever FastAPI emits natively — we don't rewrite it.
        msg = f"Non-v1 request must not gain /v1 in its Location; got {location!r}"
        assert "/api/v1/" not in location, msg

    def test_v1_redirect_location_query_string_preserved(self, test_client: TestClient):
        """If FastAPI's slash-redirect carried a query string forward,
        the rewriter preserves it on the relative Location.
        """
        response = test_client.get("/api/v1/quality?limit=5", follow_redirects=False)

        assert response.status_code == 307
        location = response.headers.get("location", "")
        assert location.startswith("/api/v1/quality/")
        assert "limit=5" in location
