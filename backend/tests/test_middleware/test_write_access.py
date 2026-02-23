"""
Tests for backend.middleware.write_access

Verifies role-based write access control:
- require_capacity_write blocks POWERUSER (supervisor)
- require_capacity_write allows ADMIN, OPERATOR, LEADER
- require_operations_write allows all current roles (placeholder)
"""

import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from backend.middleware.write_access import require_capacity_write, require_operations_write
from backend.orm.user import UserRole


def _make_user(role: str) -> MagicMock:
    """Create a mock User with the given role string."""
    user = MagicMock()
    user.role = role
    user.user_id = f"test-{role}-001"
    return user


# ---------------------------------------------------------------------------
# require_capacity_write
# ---------------------------------------------------------------------------


class TestRequireCapacityWrite:
    """Tests for the require_capacity_write dependency."""

    def test_blocks_poweruser(self):
        """POWERUSER (supervisor) should be denied write access to Capacity Planning."""
        user = _make_user(UserRole.POWERUSER.value)
        with pytest.raises(HTTPException) as exc_info:
            require_capacity_write(current_user=user)
        assert exc_info.value.status_code == 403
        assert "Supervisors" in exc_info.value.detail
        assert "Capacity Planning" in exc_info.value.detail

    def test_blocks_poweruser_enum_value(self):
        """Should also block when role is the UserRole enum itself (not just string)."""
        user = _make_user(UserRole.POWERUSER)
        with pytest.raises(HTTPException) as exc_info:
            require_capacity_write(current_user=user)
        assert exc_info.value.status_code == 403

    def test_allows_admin(self):
        """ADMIN should have write access to Capacity Planning."""
        user = _make_user(UserRole.ADMIN.value)
        result = require_capacity_write(current_user=user)
        assert result is user

    def test_allows_operator(self):
        """OPERATOR should have write access to Capacity Planning."""
        user = _make_user(UserRole.OPERATOR.value)
        result = require_capacity_write(current_user=user)
        assert result is user

    def test_allows_leader(self):
        """LEADER should have write access to Capacity Planning."""
        user = _make_user(UserRole.LEADER.value)
        result = require_capacity_write(current_user=user)
        assert result is user


# ---------------------------------------------------------------------------
# require_operations_write
# ---------------------------------------------------------------------------


class TestRequireOperationsWrite:
    """Tests for the require_operations_write dependency (placeholder)."""

    @pytest.mark.parametrize("role", [
        UserRole.ADMIN.value,
        UserRole.POWERUSER.value,
        UserRole.OPERATOR.value,
        UserRole.LEADER.value,
    ])
    def test_allows_all_current_roles(self, role: str):
        """All existing roles should be allowed to write operations data."""
        user = _make_user(role)
        result = require_operations_write(current_user=user)
        assert result is user


# ---------------------------------------------------------------------------
# Integration: verify dependency is injected on capacity routes
# ---------------------------------------------------------------------------


class TestCapacityRouterDependencyInjection:
    """Verify that require_capacity_write is injected on capacity write routes."""

    def test_write_routes_have_dependency(self):
        """All POST/PUT/PATCH/DELETE routes on the capacity router should have
        require_capacity_write in their dependencies."""
        from backend.routes.capacity import router

        write_methods = {"POST", "PUT", "PATCH", "DELETE"}

        write_routes = [
            r for r in router.routes
            if hasattr(r, "methods") and r.methods & write_methods
        ]
        assert len(write_routes) > 0, "Expected at least one write route"

        for route in write_routes:
            dep_callables = [d.dependency for d in route.dependencies if hasattr(d, "dependency")]
            assert require_capacity_write in dep_callables, (
                f"Route {route.path} ({route.methods}) missing require_capacity_write dependency"
            )

    def test_get_routes_no_write_dependency(self):
        """GET-only routes should NOT have require_capacity_write."""
        from backend.routes.capacity import router

        get_only_routes = [
            r for r in router.routes
            if hasattr(r, "methods") and r.methods == {"GET"}
        ]
        # It's acceptable if there are no GET-only routes
        for route in get_only_routes:
            dep_callables = [d.dependency for d in route.dependencies if hasattr(d, "dependency")]
            assert require_capacity_write not in dep_callables, (
                f"GET route {route.path} should NOT have require_capacity_write dependency"
            )
