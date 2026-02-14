"""
Authentication Test Fixtures
Provides pre-authenticated test clients for different user roles.
Uses real JWT tokens instead of mocks.
"""

from typing import Optional, Dict, Any
from datetime import timedelta
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.auth.jwt import create_access_token, get_password_hash
from backend.schemas.user import User


def create_test_user(
    db: Session,
    username: str,
    role: str = "operator",
    client_id: Optional[str] = None,
    password: str = "TestPass123!",
    **kwargs,
) -> User:
    """
    Create a test user in the database with proper password hashing.

    Args:
        db: Database session
        username: Unique username
        role: User role (admin, supervisor, leader, operator, viewer)
        client_id: Assigned client ID for tenant isolation
        password: Plain text password (will be hashed)
        **kwargs: Additional user fields

    Returns:
        Created User object
    """
    user = User(
        username=username,
        email=kwargs.get("email", f"{username}@test.com"),
        password_hash=get_password_hash(password),
        full_name=kwargs.get("full_name", f"Test User {username}"),
        role=role,
        client_id_assigned=client_id,
        is_active=kwargs.get("is_active", True),
    )
    db.add(user)
    db.flush()
    return user


def create_test_token(user: User, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a real JWT token for a test user.

    Args:
        user: User object to create token for
        expires_delta: Token expiration time (default: 60 minutes for tests)

    Returns:
        JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=60)

    token_data = {
        "sub": user.username,
        "user_id": user.user_id,
        "role": user.role,
        "client_ids": user.client_id_assigned,
    }

    return create_access_token(data=token_data, expires_delta=expires_delta)


class AuthenticatedClient:
    """
    Wrapper around TestClient that automatically includes auth headers.
    Provides a cleaner API for authenticated route testing.
    """

    def __init__(self, client: TestClient, token: str):
        """
        Initialize authenticated client.

        Args:
            client: FastAPI TestClient
            token: JWT authentication token
        """
        self._client = client
        self._token = token
        self._headers = {"Authorization": f"Bearer {token}"}

    @property
    def token(self) -> str:
        """Get the authentication token"""
        return self._token

    @property
    def headers(self) -> Dict[str, str]:
        """Get the authentication headers"""
        return self._headers.copy()

    def get(self, url: str, **kwargs) -> Any:
        """Make authenticated GET request"""
        headers = kwargs.pop("headers", {})
        headers.update(self._headers)
        return self._client.get(url, headers=headers, **kwargs)

    def post(self, url: str, **kwargs) -> Any:
        """Make authenticated POST request"""
        headers = kwargs.pop("headers", {})
        headers.update(self._headers)
        return self._client.post(url, headers=headers, **kwargs)

    def put(self, url: str, **kwargs) -> Any:
        """Make authenticated PUT request"""
        headers = kwargs.pop("headers", {})
        headers.update(self._headers)
        return self._client.put(url, headers=headers, **kwargs)

    def patch(self, url: str, **kwargs) -> Any:
        """Make authenticated PATCH request"""
        headers = kwargs.pop("headers", {})
        headers.update(self._headers)
        return self._client.patch(url, headers=headers, **kwargs)

    def delete(self, url: str, **kwargs) -> Any:
        """Make authenticated DELETE request"""
        headers = kwargs.pop("headers", {})
        headers.update(self._headers)
        return self._client.delete(url, headers=headers, **kwargs)

    def head(self, url: str, **kwargs) -> Any:
        """Make authenticated HEAD request"""
        headers = kwargs.pop("headers", {})
        headers.update(self._headers)
        return self._client.head(url, headers=headers, **kwargs)

    def options(self, url: str, **kwargs) -> Any:
        """Make authenticated OPTIONS request"""
        headers = kwargs.pop("headers", {})
        headers.update(self._headers)
        return self._client.options(url, headers=headers, **kwargs)


def get_admin_client(
    test_client: TestClient, db: Session, username: str = "test_admin", client_ids: Optional[str] = None
) -> AuthenticatedClient:
    """
    Get an authenticated client with admin role.
    Admin users can access all clients.

    Args:
        test_client: FastAPI TestClient
        db: Database session
        username: Username for the admin user
        client_ids: Optional client IDs (None = all clients)

    Returns:
        AuthenticatedClient with admin privileges
    """
    user = create_test_user(db, username=username, role="admin", client_id=client_ids, full_name="Test Admin User")
    db.commit()

    token = create_test_token(user)
    return AuthenticatedClient(test_client, token)


def get_supervisor_client(
    test_client: TestClient, db: Session, client_id: str, username: str = "test_supervisor"
) -> AuthenticatedClient:
    """
    Get an authenticated client with supervisor role.
    Supervisors have elevated access within their assigned client.

    Args:
        test_client: FastAPI TestClient
        db: Database session
        client_id: Client ID the supervisor is assigned to
        username: Username for the supervisor user

    Returns:
        AuthenticatedClient with supervisor privileges
    """
    user = create_test_user(
        db, username=username, role="supervisor", client_id=client_id, full_name="Test Supervisor User"
    )
    db.commit()

    token = create_test_token(user)
    return AuthenticatedClient(test_client, token)


def get_leader_client(
    test_client: TestClient, db: Session, client_ids: str, username: str = "test_leader"
) -> AuthenticatedClient:
    """
    Get an authenticated client with leader role.
    Leaders can access multiple clients (comma-separated).

    Args:
        test_client: FastAPI TestClient
        db: Database session
        client_ids: Comma-separated client IDs the leader can access
        username: Username for the leader user

    Returns:
        AuthenticatedClient with leader privileges
    """
    user = create_test_user(db, username=username, role="leader", client_id=client_ids, full_name="Test Leader User")
    db.commit()

    token = create_test_token(user)
    return AuthenticatedClient(test_client, token)


def get_operator_client(
    test_client: TestClient, db: Session, client_id: str, username: str = "test_operator"
) -> AuthenticatedClient:
    """
    Get an authenticated client with operator role.
    Operators have basic access to their assigned client only.

    Args:
        test_client: FastAPI TestClient
        db: Database session
        client_id: Client ID the operator is assigned to
        username: Username for the operator user

    Returns:
        AuthenticatedClient with operator privileges
    """
    user = create_test_user(db, username=username, role="operator", client_id=client_id, full_name="Test Operator User")
    db.commit()

    token = create_test_token(user)
    return AuthenticatedClient(test_client, token)


def get_viewer_client(
    test_client: TestClient, db: Session, client_id: str, username: str = "test_viewer"
) -> AuthenticatedClient:
    """
    Get an authenticated client with viewer role.
    Viewers have read-only access to their assigned client.

    Args:
        test_client: FastAPI TestClient
        db: Database session
        client_id: Client ID the viewer is assigned to
        username: Username for the viewer user

    Returns:
        AuthenticatedClient with viewer privileges (read-only)
    """
    user = create_test_user(db, username=username, role="viewer", client_id=client_id, full_name="Test Viewer User")
    db.commit()

    token = create_test_token(user)
    return AuthenticatedClient(test_client, token)


def get_multi_tenant_client(
    test_client: TestClient, db: Session, client_ids: str, role: str = "supervisor", username: str = "test_multi_tenant"
) -> AuthenticatedClient:
    """
    Get an authenticated client with access to multiple clients.
    Used for testing multi-tenant isolation.

    Args:
        test_client: FastAPI TestClient
        db: Database session
        client_ids: Comma-separated client IDs
        role: User role
        username: Username for the user

    Returns:
        AuthenticatedClient with multi-tenant access
    """
    user = create_test_user(db, username=username, role=role, client_id=client_ids, full_name="Test Multi-Tenant User")
    db.commit()

    token = create_test_token(user)
    return AuthenticatedClient(test_client, token)


# Pytest fixtures for easy integration
def create_authenticated_clients_fixture(test_client, db):
    """
    Factory function to create multiple authenticated clients.
    Returns a dict with all role-based clients.
    """
    from .factories import TestDataFactory

    # Create test clients
    client_a = TestDataFactory.create_client(db, client_id="CLIENT-A", client_name="Test Client A")
    client_b = TestDataFactory.create_client(db, client_id="CLIENT-B", client_name="Test Client B")
    db.commit()

    return {
        "admin": get_admin_client(test_client, db, username="fixture_admin"),
        "supervisor_a": get_supervisor_client(test_client, db, "CLIENT-A", username="fixture_supervisor_a"),
        "supervisor_b": get_supervisor_client(test_client, db, "CLIENT-B", username="fixture_supervisor_b"),
        "operator_a": get_operator_client(test_client, db, "CLIENT-A", username="fixture_operator_a"),
        "operator_b": get_operator_client(test_client, db, "CLIENT-B", username="fixture_operator_b"),
        "viewer_a": get_viewer_client(test_client, db, "CLIENT-A", username="fixture_viewer_a"),
        "leader_multi": get_leader_client(test_client, db, "CLIENT-A,CLIENT-B", username="fixture_leader"),
        "clients": {"a": client_a, "b": client_b},
    }
