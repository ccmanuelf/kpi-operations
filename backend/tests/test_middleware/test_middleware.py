"""
Tests for Backend Middleware
Sprint 5 — Task 5.2: Tests for security headers, rate limiting, and client auth.

Middleware under test:
1. SecurityHeadersMiddleware (security_headers.py) — 6 security headers
2. RateLimitMiddleware / helpers (rate_limit.py) — rate limiting behaviour
3. Client auth helpers (client_auth.py) — tenant isolation logic

Middleware tests use FastAPI TestClient at the HTTP level.
Client auth tests exercise pure Python functions with real DB (transactional_db).
"""

import pytest
from datetime import datetime
from decimal import Decimal
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.middleware.security_headers import SecurityHeadersMiddleware
from backend.middleware.rate_limit import (
    RateLimitMiddleware,
    RateLimitConfig,
    limiter,
    get_rate_limit_key,
    configure_rate_limiting,
)
from backend.middleware.client_auth import (
    ClientAccessError,
    get_user_client_filter,
    verify_client_access,
    build_client_filter_clause,
    _get_clients_from_legacy_field,
)
from backend.schemas.user import User, UserRole
from backend.schemas.work_order import WorkOrder
from backend.tests.fixtures.factories import TestDataFactory


# ============================================================================
# Helper — create a minimal FastAPI app with the middleware under test
# ============================================================================


def _create_app_with_security_headers():
    """Build a tiny FastAPI app that uses SecurityHeadersMiddleware."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ping")
    def ping():
        return {"status": "ok"}

    return app


def _create_app_with_rate_limit_headers():
    """Build a tiny FastAPI app that uses RateLimitMiddleware."""
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/ping")
    def ping():
        return {"status": "ok"}

    return app


# ============================================================================
# 1. SecurityHeadersMiddleware Tests
# ============================================================================


class TestSecurityHeadersMiddleware:
    """Verify all 6 security headers are injected into every response."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        app = _create_app_with_security_headers()
        self.client = TestClient(app)

    def test_x_content_type_options(self):
        """X-Content-Type-Options is set to nosniff."""
        resp = self.client.get("/ping")
        assert resp.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_frame_options(self):
        """X-Frame-Options is set to DENY."""
        resp = self.client.get("/ping")
        assert resp.headers["X-Frame-Options"] == "DENY"

    def test_x_xss_protection(self):
        """X-XSS-Protection is set to 1; mode=block."""
        resp = self.client.get("/ping")
        assert resp.headers["X-XSS-Protection"] == "1; mode=block"

    def test_referrer_policy(self):
        """Referrer-Policy is set to strict-origin-when-cross-origin."""
        resp = self.client.get("/ping")
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_permissions_policy(self):
        """Permissions-Policy disables camera, microphone, geolocation."""
        resp = self.client.get("/ping")
        assert (
            resp.headers["Permissions-Policy"]
            == "camera=(), microphone=(), geolocation=()"
        )

    def test_hsts_not_set_for_localhost(self):
        """HSTS header is NOT set for localhost requests."""
        # TestClient uses 'testserver' as default host, so we must
        # explicitly set the Host header to localhost.
        resp = self.client.get("/ping", headers={"Host": "localhost:8000"})
        assert "Strict-Transport-Security" not in resp.headers

    def test_hsts_set_for_non_localhost(self):
        """HSTS header IS set when Host is not localhost."""
        resp = self.client.get("/ping", headers={"Host": "api.example.com"})
        assert "Strict-Transport-Security" in resp.headers
        assert "max-age=31536000" in resp.headers["Strict-Transport-Security"]
        assert "includeSubDomains" in resp.headers["Strict-Transport-Security"]

    def test_all_six_headers_present(self):
        """All 6 documented security headers present on a non-localhost request."""
        resp = self.client.get("/ping", headers={"Host": "prod.example.com"})

        expected_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Permissions-Policy",
            "Strict-Transport-Security",
        ]
        for header in expected_headers:
            assert header in resp.headers, f"Missing header: {header}"


# ============================================================================
# 2. RateLimitMiddleware Tests
# ============================================================================


class TestRateLimitMiddleware:
    """Verify rate-limit headers are added to responses."""

    @pytest.fixture(autouse=True)
    def setup_client(self):
        app = _create_app_with_rate_limit_headers()
        self.client = TestClient(app)

    def test_rate_limit_header_present(self):
        """X-RateLimit-Limit header is set to 100."""
        resp = self.client.get("/ping")
        assert resp.headers["X-RateLimit-Limit"] == "100"

    def test_rate_limit_reset_header_present(self):
        """X-RateLimit-Reset header is a numeric timestamp."""
        resp = self.client.get("/ping")
        reset = resp.headers.get("X-RateLimit-Reset")
        assert reset is not None
        assert int(reset) > 0

    def test_rate_limit_policy_header_present(self):
        """X-RateLimit-Policy header describes the policy."""
        resp = self.client.get("/ping")
        assert resp.headers["X-RateLimit-Policy"] == "100 requests per minute"

    def test_response_200_ok(self):
        """Endpoint returns 200 when rate limit is not exceeded."""
        resp = self.client.get("/ping")
        assert resp.status_code == 200


class TestRateLimitConfig:
    """Verify the RateLimitConfig constants."""

    def test_general_limit(self):
        assert RateLimitConfig.GENERAL_LIMIT == "100/minute"

    def test_auth_limit(self):
        assert RateLimitConfig.AUTH_LIMIT == "10/minute"

    def test_sensitive_limit(self):
        assert RateLimitConfig.SENSITIVE_LIMIT == "5/minute"

    def test_upload_limit(self):
        assert RateLimitConfig.UPLOAD_LIMIT == "20/minute"

    def test_report_limit(self):
        assert RateLimitConfig.REPORT_LIMIT == "10/minute"


class TestRateLimitHelpers:
    """Test helper functions in the rate_limit module."""

    def test_get_rate_limit_key_without_user(self):
        """Key is the client IP when no user is authenticated."""
        # Build a mock-like request with minimal attributes
        from starlette.testclient import TestClient

        app = FastAPI()

        captured_key = {}

        @app.get("/key-check")
        def key_check(request: Request):
            captured_key["value"] = get_rate_limit_key(request)
            return {"ok": True}

        client = TestClient(app)
        client.get("/key-check")
        # Should be an IP string (testclient defaults to 'testclient')
        assert isinstance(captured_key["value"], str)
        assert len(captured_key["value"]) > 0

    def test_configure_rate_limiting_returns_app(self):
        """configure_rate_limiting returns the app instance."""
        app = FastAPI()
        result = configure_rate_limiting(app)
        assert result is app


# ============================================================================
# 3. Client Auth Middleware Tests
# ============================================================================


class TestClientAccessErrorException:
    """ClientAccessError is a proper HTTPException with 403 status."""

    def test_default_detail(self):
        err = ClientAccessError()
        assert err.status_code == 403
        assert "Access denied" in err.detail

    def test_custom_detail(self):
        err = ClientAccessError(detail="No access for you")
        assert err.detail == "No access for you"


class TestGetUserClientFilter:
    """get_user_client_filter returns None for admins, list for operators."""

    def test_admin_returns_none(self):
        """ADMIN users have unrestricted access (None = no filter)."""
        admin = User(
            user_id="U-1",
            username="admin",
            email="a@t.com",
            role=UserRole.ADMIN,
            client_id_assigned=None,
            is_active=True,
        )
        assert get_user_client_filter(admin) is None

    def test_poweruser_returns_none(self):
        """POWERUSER users have unrestricted access."""
        pu = User(
            user_id="U-2",
            username="power",
            email="p@t.com",
            role=UserRole.POWERUSER,
            client_id_assigned=None,
            is_active=True,
        )
        assert get_user_client_filter(pu) is None

    def test_operator_single_client(self):
        """OPERATOR with one client returns list of one."""
        op = User(
            user_id="U-3",
            username="op",
            email="op@t.com",
            role=UserRole.OPERATOR,
            client_id_assigned="CLIENT-A",
            is_active=True,
        )
        result = get_user_client_filter(op)
        assert result == ["CLIENT-A"]

    def test_leader_multi_client(self):
        """LEADER with comma-separated clients returns parsed list."""
        leader = User(
            user_id="U-4",
            username="lead",
            email="lead@t.com",
            role=UserRole.LEADER,
            client_id_assigned="CLIENT-A, CLIENT-B",
            is_active=True,
        )
        result = get_user_client_filter(leader)
        assert result == ["CLIENT-A", "CLIENT-B"]

    def test_operator_no_assignment_raises(self):
        """OPERATOR with no client assignment raises ClientAccessError."""
        op = User(
            user_id="U-5",
            username="op2",
            email="op2@t.com",
            role=UserRole.OPERATOR,
            client_id_assigned=None,
            is_active=True,
        )
        with pytest.raises(ClientAccessError):
            get_user_client_filter(op)


class TestVerifyClientAccess:
    """verify_client_access enforces tenant isolation."""

    def test_admin_can_access_any_client(self):
        """ADMIN users pass verification for any client_id."""
        admin = User(
            user_id="U-1",
            username="admin",
            email="a@t.com",
            role=UserRole.ADMIN,
            client_id_assigned=None,
            is_active=True,
        )
        assert verify_client_access(admin, "ANY-CLIENT") is True

    def test_operator_can_access_own_client(self):
        """OPERATOR can access their assigned client."""
        op = User(
            user_id="U-2",
            username="op",
            email="op@t.com",
            role=UserRole.OPERATOR,
            client_id_assigned="CLIENT-A",
            is_active=True,
        )
        assert verify_client_access(op, "CLIENT-A") is True

    def test_operator_cannot_access_other_client(self):
        """OPERATOR cannot access a client they are not assigned to."""
        op = User(
            user_id="U-3",
            username="op",
            email="op@t.com",
            role=UserRole.OPERATOR,
            client_id_assigned="CLIENT-A",
            is_active=True,
        )
        with pytest.raises(ClientAccessError):
            verify_client_access(op, "CLIENT-B")

    def test_leader_multi_client_access(self):
        """LEADER with multiple clients can access each."""
        leader = User(
            user_id="U-4",
            username="lead",
            email="lead@t.com",
            role=UserRole.LEADER,
            client_id_assigned="CLIENT-A,CLIENT-B",
            is_active=True,
        )
        assert verify_client_access(leader, "CLIENT-A") is True
        assert verify_client_access(leader, "CLIENT-B") is True

    def test_leader_multi_client_denied_other(self):
        """LEADER with CLIENT-A,CLIENT-B cannot access CLIENT-C."""
        leader = User(
            user_id="U-5",
            username="lead",
            email="lead@t.com",
            role=UserRole.LEADER,
            client_id_assigned="CLIENT-A,CLIENT-B",
            is_active=True,
        )
        with pytest.raises(ClientAccessError):
            verify_client_access(leader, "CLIENT-C")


class TestBuildClientFilterClause:
    """build_client_filter_clause returns None or an IN clause."""

    def test_admin_returns_none(self):
        """ADMIN produces no filter clause (None)."""
        admin = User(
            user_id="U-1",
            username="admin",
            email="a@t.com",
            role=UserRole.ADMIN,
            client_id_assigned=None,
            is_active=True,
        )
        clause = build_client_filter_clause(admin, WorkOrder.client_id)
        assert clause is None

    def test_operator_returns_in_clause(self):
        """OPERATOR produces an IN clause matching assigned client."""
        op = User(
            user_id="U-2",
            username="op",
            email="op@t.com",
            role=UserRole.OPERATOR,
            client_id_assigned="CLIENT-A",
            is_active=True,
        )
        clause = build_client_filter_clause(op, WorkOrder.client_id)
        # clause is a SQLAlchemy BinaryExpression (IN); it should not be None
        assert clause is not None


class TestLegacyClientFieldParsing:
    """_get_clients_from_legacy_field handles edge cases."""

    def test_none_returns_none(self):
        user = User(
            user_id="U-1",
            username="x",
            email="x@t.com",
            role=UserRole.OPERATOR,
            client_id_assigned=None,
            is_active=True,
        )
        assert _get_clients_from_legacy_field(user) is None

    def test_empty_string_returns_none(self):
        user = User(
            user_id="U-2",
            username="x",
            email="x@t.com",
            role=UserRole.OPERATOR,
            client_id_assigned="",
            is_active=True,
        )
        assert _get_clients_from_legacy_field(user) is None

    def test_whitespace_only_returns_none(self):
        user = User(
            user_id="U-3",
            username="x",
            email="x@t.com",
            role=UserRole.OPERATOR,
            client_id_assigned="  , , ",
            is_active=True,
        )
        assert _get_clients_from_legacy_field(user) is None

    def test_single_client_parsed(self):
        user = User(
            user_id="U-4",
            username="x",
            email="x@t.com",
            role=UserRole.OPERATOR,
            client_id_assigned="BOOT-LINE-A",
            is_active=True,
        )
        result = _get_clients_from_legacy_field(user)
        assert result == ["BOOT-LINE-A"]

    def test_multiple_clients_parsed_with_whitespace(self):
        user = User(
            user_id="U-5",
            username="x",
            email="x@t.com",
            role=UserRole.OPERATOR,
            client_id_assigned=" BOOT-LINE-A , CLIENT-B , CLIENT-C ",
            is_active=True,
        )
        result = _get_clients_from_legacy_field(user)
        assert result == ["BOOT-LINE-A", "CLIENT-B", "CLIENT-C"]
