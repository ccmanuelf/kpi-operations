"""
Test Fixtures Package
Provides factories, authentication fixtures, and seed data utilities
"""
from .factories import TestDataFactory
from .auth_fixtures import (
    create_test_user,
    create_test_token,
    AuthenticatedClient,
    get_admin_client,
    get_supervisor_client,
    get_operator_client,
    get_viewer_client,
)
from .seed_data import (
    seed_minimal_data,
    seed_comprehensive_data,
    seed_multi_tenant_data,
)

__all__ = [
    # Factories
    "TestDataFactory",
    # Auth fixtures
    "create_test_user",
    "create_test_token",
    "AuthenticatedClient",
    "get_admin_client",
    "get_supervisor_client",
    "get_operator_client",
    "get_viewer_client",
    # Seed data
    "seed_minimal_data",
    "seed_comprehensive_data",
    "seed_multi_tenant_data",
]
