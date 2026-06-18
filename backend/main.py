"""
Manufacturing KPI Platform - FastAPI Backend
Main application with modular routes

API Versioning:
  The canonical API prefix is /api/v1/. A path-rewriting middleware
  strips the /v1 segment so existing route handlers (mounted at /api/)
  continue to work unchanged.  Clients may use either prefix:
    - /api/v1/health/live  (canonical, versioned)
    - /api/health/live     (legacy, backward-compatible)
"""

from typing import Any, Dict

from fastapi import FastAPI
from datetime import datetime, timezone
import logging

from backend.bootstrap.lifecycle import lifespan
from backend.bootstrap.openapi import tags_metadata
from backend.bootstrap.routers import register_routers
from backend.bootstrap.app_config import configure_middleware, register_exception_handlers

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Manufacturing KPI Platform API",
    description="FastAPI backend for production tracking and KPI calculation",
    version="1.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)

configure_middleware(app)
register_exception_handlers(app)


# ============================================================================
# HEALTH CHECK
# ============================================================================


@app.get("/")
def root() -> Dict[str, Any]:
    """API health check"""
    return {
        "status": "healthy",
        "service": "Manufacturing KPI Platform API",
        "version": "1.0.0",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


# ============================================================================
# MODULAR ROUTE REGISTRATION
# ============================================================================
register_routers(app)


if __name__ == "__main__":
    import uvicorn

    # 0.0.0.0 is required for Docker / Render container networking;
    # the production entrypoint uses uvicorn via gunicorn in the
    # Dockerfile, this branch is the local-development runner.
    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104
