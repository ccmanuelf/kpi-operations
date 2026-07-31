"""
Regression guard for ISSUE-012 (e2e-sweep remediation): the backend must
accept each of frontend/src's canonical collection-root call paths on the
FIRST request, not via a 307 redirect_slashes bounce.

Scope: this test only pins the BACKEND side — that `_CANONICAL_FRONTEND_PATHS`
below (a hand-copied snapshot of what frontend/src currently calls) resolves
without a redirect. It does NOT verify that frontend/src still calls these
exact strings — if a frontend caller regressed back to a slash-less path,
THIS test would keep passing (it never re-reads frontend source). That side
is pinned by frontend/src/services/__tests__/dataEntry.spec.ts, which asserts
the literal path string `dataEntry.ts` passes to axios. The two tests
together close the loop: frontend spec pins the call string, this test pins
that the call string is redirect-free on the backend.

Why this matters: behind a reverse proxy that doesn't trust
X-Forwarded-Proto (the VM's Caddy -> gunicorn/UvicornWorker hop before the
docker-compose.prod.yml fix), a redirect_slashes 307's Location header
reports scheme="http" even when the browser is on https. The browser then
blocks the follow-up request as mixed content, and the screen goes dead
(captured casualty: Quality Entry, "Failed to load quality entries" via
GET /api/quality with no trailing slash against a router registered at
"/api/quality/").

This test does NOT touch DB state and does NOT disable redirect_slashes —
it asserts each canonical path lands on a router-registered path so no
redirect is ever issued for it. A redirect for one of these paths (3xx
here) is the regression this guards against; the specific status code
otherwise (200/401/422/...) is not the point.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app

# (method, path) — a hand-copied SNAPSHOT of the exact strings frontend/src
# callers currently pass to axios for every backend router registered with a
# trailing-slash collection root (`APIRouter(prefix=...)` +
# `@router.get("/")` / `@router.post("/")`) that frontend/src actually
# calls. Sourced by introspecting `app.routes` and cross-referencing
# frontend/src/services/api/*.ts + composables/*.ts callers (see
# task-2-report.md for the full alignment table). Being a snapshot, this
# list does not automatically track frontend/src — see the module docstring
# for how frontend/src/services/__tests__/dataEntry.spec.ts covers that gap
# for the quality paths specifically.
#
# GET /api/quality/ and POST /api/quality/ were the misaligned pair fixed
# by this task (frontend/src/services/api/dataEntry.ts); the rest were
# already aligned and are covered here as a regression net for the same
# router-registration pattern.
_CANONICAL_FRONTEND_PATHS: list[tuple[str, str]] = [
    ("GET", "/api/quality/"),
    ("POST", "/api/quality/"),
    ("GET", "/api/alerts/"),
    ("GET", "/api/alerts/summary"),
    ("POST", "/api/client-config/"),
    ("GET", "/api/production-lines/"),
    ("GET", "/api/shifts/"),
    ("GET", "/api/v2/simulation/"),
]

_REDIRECT_CODES = {301, 302, 303, 307, 308}


@pytest.fixture(scope="module")
def path_alignment_client():
    return TestClient(app)


@pytest.mark.parametrize("method,path", _CANONICAL_FRONTEND_PATHS)
def test_frontend_call_path_is_not_redirected(path_alignment_client: TestClient, method: str, path: str) -> None:
    """The frontend's literal call string must match a registered route
    exactly — no redirect_slashes bounce, regardless of auth outcome."""
    resp = path_alignment_client.request(method, path, follow_redirects=False)

    assert resp.status_code not in _REDIRECT_CODES, (
        f"{method} {path} returned {resp.status_code} — a redirect means the "
        "frontend's exact call string does not match the router's registered "
        "path (missing/extra trailing slash). Behind a proxy that doesn't "
        "trust X-Forwarded-Proto, this downgrades https->http and the "
        "browser blocks it as mixed content (ISSUE-012)."
    )
