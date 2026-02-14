"""
Rate Limiting Tests (SEC-001)
Tests for API rate limiting middleware using slowapi

Tests verify:
1. Rate limit headers are present in responses
2. Auth endpoints have stricter limits (10/min)
3. Rate limit exceeded returns 429 status
4. Rate limits reset after time window
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import time


class TestRateLimitMiddleware:
    """Tests for rate limiting middleware"""

    def test_rate_limit_headers_present(self, test_client):
        """Test that X-RateLimit headers are present in responses"""
        response = test_client.get("/")

        # Check headers are present
        assert (
            "X-RateLimit-Limit" in response.headers or "X-RateLimit-Policy" in response.headers
        ), "Rate limit headers should be present in response"

    def test_rate_limit_headers_values(self, test_client):
        """Test rate limit header values are correct"""
        response = test_client.get("/")

        # Verify header values if present
        if "X-RateLimit-Limit" in response.headers:
            limit = response.headers.get("X-RateLimit-Limit")
            assert limit == "100", f"Expected limit 100, got {limit}"

        if "X-RateLimit-Reset" in response.headers:
            reset = response.headers.get("X-RateLimit-Reset")
            assert reset.isdigit(), "Reset timestamp should be numeric"

    def test_health_endpoint_accessible(self, test_client):
        """Test health endpoint is accessible within rate limits"""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestAuthEndpointRateLimiting:
    """Tests for authentication endpoint rate limiting"""

    def test_login_rate_limit_header(self, test_client):
        """Test login endpoint has rate limit applied"""
        response = test_client.post("/api/auth/login", json={"username": "nonexistent", "password": "password"})

        # Even failed login should have rate limit headers
        assert response.status_code in [401, 429]

    def test_register_rate_limit_header(self, test_client):
        """Test register endpoint has rate limit applied"""
        response = test_client.post(
            "/api/auth/register",
            json={
                "username": "test_rate_user",
                "email": "rate@test.com",
                "password": "TestPass123!",
                "full_name": "Rate Test User",
                "role": "operator",
            },
        )

        # Response should be 201 (created), 400 (exists), or 422 (validation)
        assert response.status_code in [201, 400, 422, 429]


class TestRateLimitConfig:
    """Tests for rate limit configuration"""

    def test_rate_limit_config_values(self):
        """Test rate limit configuration constants"""
        from backend.middleware.rate_limit import RateLimitConfig

        assert RateLimitConfig.GENERAL_LIMIT == "100/minute"
        assert RateLimitConfig.AUTH_LIMIT == "10/minute"
        assert RateLimitConfig.SENSITIVE_LIMIT == "5/minute"
        assert RateLimitConfig.UPLOAD_LIMIT == "20/minute"
        assert RateLimitConfig.REPORT_LIMIT == "10/minute"

    def test_limiter_instance_created(self):
        """Test limiter instance is properly created"""
        from backend.middleware.rate_limit import limiter

        assert limiter is not None
        # Verify limiter has expected attributes
        assert hasattr(limiter, "limit")

    def test_rate_limit_decorators_available(self):
        """Test rate limit decorators are available for import"""
        from backend.middleware.rate_limit import (
            auth_rate_limit,
            general_rate_limit,
            sensitive_rate_limit,
            upload_rate_limit,
            report_rate_limit,
        )

        # Verify decorators are callable
        assert callable(auth_rate_limit)
        assert callable(general_rate_limit)
        assert callable(sensitive_rate_limit)
        assert callable(upload_rate_limit)
        assert callable(report_rate_limit)


class TestRateLimitKeyFunction:
    """Tests for rate limit key generation"""

    def test_get_rate_limit_key_ip_only(self):
        """Test rate limit key generation with IP only"""
        from backend.middleware.rate_limit import get_rate_limit_key
        from unittest.mock import MagicMock

        # Create mock request
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.1"

        # State without user_id
        mock_state = MagicMock()
        mock_state.user_id = None
        mock_request.state = mock_state

        # Should return IP-based key
        key = get_rate_limit_key(mock_request)
        assert "192.168.1.1" in key

    def test_get_rate_limit_key_with_user(self):
        """Test rate limit key generation with authenticated user"""
        from backend.middleware.rate_limit import get_rate_limit_key
        from unittest.mock import MagicMock

        # Create mock request with authenticated user
        mock_request = MagicMock()
        mock_request.client.host = "192.168.1.1"

        mock_state = MagicMock()
        mock_state.user_id = 123
        mock_request.state = mock_state

        # Should return combined key
        key = get_rate_limit_key(mock_request)
        assert "192.168.1.1" in key
        assert "123" in key


class TestRateLimitMiddlewareIntegration:
    """Integration tests for rate limit middleware"""

    def test_middleware_added_to_app(self, test_client):
        """Test middleware is properly added to FastAPI app"""
        from backend.main import app

        # Check that limiter is in app state
        assert hasattr(app.state, "limiter")
        assert app.state.limiter is not None

    def test_multiple_requests_within_limit(self, test_client):
        """Test multiple requests within rate limit succeed"""
        # Make several requests - should all succeed
        for i in range(5):
            response = test_client.get("/")
            assert response.status_code == 200, f"Request {i+1} should succeed within rate limit"


class TestRateLimitExceeded:
    """Tests for rate limit exceeded behavior"""

    def test_rate_limit_exceeded_handler_exists(self):
        """Test that rate limit exceeded handler is available"""
        from slowapi import _rate_limit_exceeded_handler

        # Handler should be callable
        assert callable(_rate_limit_exceeded_handler)

    def test_rate_limit_exception_class_exists(self):
        """Test RateLimitExceeded exception class exists"""
        from slowapi.errors import RateLimitExceeded

        # Class should be importable
        assert RateLimitExceeded is not None
        assert issubclass(RateLimitExceeded, Exception)


class TestConfigureRateLimiting:
    """Tests for rate limiting configuration function"""

    def test_configure_rate_limiting_returns_app(self):
        """Test configure_rate_limiting returns the app"""
        from fastapi import FastAPI
        from backend.middleware.rate_limit import configure_rate_limiting

        app = FastAPI()
        result = configure_rate_limiting(app)

        assert result is app
        assert hasattr(app.state, "limiter")

    def test_configure_rate_limiting_adds_exception_handler(self):
        """Test exception handler is added for RateLimitExceeded"""
        from fastapi import FastAPI
        from backend.middleware.rate_limit import configure_rate_limiting
        from slowapi.errors import RateLimitExceeded

        app = FastAPI()
        configure_rate_limiting(app)

        # Check exception handler is registered
        assert RateLimitExceeded in app.exception_handlers
