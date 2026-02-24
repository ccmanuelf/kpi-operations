"""
Test Data Factory — Re-export stub.
The canonical implementation lives at backend/db/factories.py (Docker-included).
This file re-exports TestDataFactory for backward compatibility with test imports.
"""

from backend.db.factories import TestDataFactory

__all__ = ["TestDataFactory"]
