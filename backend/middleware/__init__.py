"""
Backend middleware for multi-tenant authorization and client isolation
"""
from .client_auth import verify_client_access, get_user_client_filter, ClientAccessError

__all__ = ["verify_client_access", "get_user_client_filter", "ClientAccessError"]
