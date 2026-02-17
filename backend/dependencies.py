"""Shared FastAPI dependencies for route handlers."""

from fastapi import Query


class PaginationParams:
    """Common pagination parameters as a FastAPI dependency.

    Usage: pagination: PaginationParams = Depends()
    """

    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    ):
        self.skip = skip
        self.limit = limit
