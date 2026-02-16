"""
Health Check and Database Monitoring Routes
Provides endpoints for system health and connection pool monitoring

Enhanced with:
- DEP-001: System metrics (memory, disk, CPU)
- DEP-002: Configuration validation status
- Latency measurements for database queries
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Dict, Any, Optional
import logging
import time
import os
import sys

# System metrics - psutil is optional for lightweight deployments
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from backend.database import get_db, get_pool_status
from backend.config import settings, validate_production_config, ConfigValidationResult

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])

# Named constant for database ping query (used in health checks)
_DB_PING_QUERY = text("SELECT 1")

# Application start time for uptime calculation
APP_START_TIME = datetime.utcnow()


@router.get("/", response_model=Dict[str, Any])
async def health_check():
    """
    Basic health check endpoint
    Returns service status and timestamp
    """
    return {
        "status": "healthy",
        "service": "KPI Operations API",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@router.get("/database", response_model=Dict[str, Any])
async def database_health(db: Session = Depends(get_db)):
    """
    Database health check
    Tests database connectivity and returns basic status
    """
    try:
        # Execute simple query to test connection
        result = db.execute(_DB_PING_QUERY)
        result.fetchone()

        return {"status": "healthy", "database": "connected", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Database connection failed: {str(e)}"
        )


@router.get("/pool", response_model=Dict[str, Any])
async def connection_pool_status():
    """
    Connection pool monitoring endpoint
    Returns detailed statistics about database connection pool

    Metrics include:
    - Pool size and configuration
    - Active connections
    - Available connections
    - Overflow connections
    - Pool utilization percentage
    """
    try:
        pool_stats = get_pool_status()

        return {"status": "healthy", "timestamp": datetime.utcnow().isoformat(), "pool": pool_stats}
    except Exception as e:
        logger.error(f"Pool status check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve pool status: {str(e)}"
        )


@router.get("/detailed", response_model=Dict[str, Any])
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Comprehensive health check with system metrics (DEP-001)

    Combines service, database, connection pool status, and system metrics.
    Returns detailed health information for monitoring and alerting.

    Metrics include:
    - Service status and uptime
    - Database connectivity with latency measurement
    - Connection pool statistics
    - Memory usage (if psutil available)
    - Disk usage (if psutil available)
    - CPU usage (if psutil available)
    - Configuration validation status (DEP-002)
    """
    overall_status = "healthy"
    checks = {}

    # Calculate uptime
    uptime_seconds = (datetime.utcnow() - APP_START_TIME).total_seconds()
    uptime_formatted = _format_uptime(uptime_seconds)

    # Database connectivity test with latency measurement
    try:
        start_time = time.perf_counter()
        db.execute(_DB_PING_QUERY)
        db_latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        checks["database"] = {"status": "healthy", "latency_ms": db_latency_ms, "pool": get_pool_status()}

        # Warn if latency is high
        if db_latency_ms > 100:
            checks["database"]["status"] = "warning"
            checks["database"]["message"] = "High latency detected"
            if overall_status == "healthy":
                overall_status = "degraded"

    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "unhealthy"

    # Memory usage check (DEP-001)
    if PSUTIL_AVAILABLE:
        try:
            memory = psutil.virtual_memory()
            memory_status = "healthy"

            if memory.percent >= 95:
                memory_status = "critical"
                overall_status = "unhealthy"
            elif memory.percent >= 90:
                memory_status = "warning"
                if overall_status == "healthy":
                    overall_status = "degraded"

            checks["memory"] = {
                "status": memory_status,
                "used_percent": round(memory.percent, 1),
                "available_mb": round(memory.available / (1024 * 1024), 0),
                "total_mb": round(memory.total / (1024 * 1024), 0),
            }
        except Exception as e:
            logger.warning(f"Memory check failed: {str(e)}")
            checks["memory"] = {"status": "unknown", "error": str(e)}
    else:
        checks["memory"] = {"status": "unavailable", "message": "psutil not installed"}

    # Disk usage check (DEP-001)
    if PSUTIL_AVAILABLE:
        try:
            disk = psutil.disk_usage("/")
            disk_status = "healthy"

            if disk.percent >= 95:
                disk_status = "critical"
                overall_status = "unhealthy"
            elif disk.percent >= 90:
                disk_status = "warning"
                if overall_status == "healthy":
                    overall_status = "degraded"

            checks["disk"] = {
                "status": disk_status,
                "used_percent": round(disk.percent, 1),
                "free_gb": round(disk.free / (1024 * 1024 * 1024), 2),
                "total_gb": round(disk.total / (1024 * 1024 * 1024), 2),
            }
        except Exception as e:
            logger.warning(f"Disk check failed: {str(e)}")
            checks["disk"] = {"status": "unknown", "error": str(e)}
    else:
        checks["disk"] = {"status": "unavailable", "message": "psutil not installed"}

    # CPU usage check (DEP-001)
    if PSUTIL_AVAILABLE:
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_status = "healthy"

            if cpu_percent >= 95:
                cpu_status = "critical"
                if overall_status == "healthy":
                    overall_status = "degraded"
            elif cpu_percent >= 80:
                cpu_status = "warning"

            checks["cpu"] = {"status": cpu_status, "used_percent": round(cpu_percent, 1), "cores": psutil.cpu_count()}
        except Exception as e:
            logger.warning(f"CPU check failed: {str(e)}")
            checks["cpu"] = {"status": "unknown", "error": str(e)}
    else:
        checks["cpu"] = {"status": "unavailable", "message": "psutil not installed"}

    # Configuration validation check (DEP-002)
    try:
        config_result = validate_production_config()
        config_status = "healthy"

        if config_result.has_critical_errors:
            config_status = "critical"
            overall_status = "unhealthy"
        elif config_result.has_warnings:
            config_status = "warning"
            if overall_status == "healthy":
                overall_status = "degraded"

        checks["configuration"] = {
            "status": config_status,
            "environment": config_result.environment,
            "warnings": config_result.warnings if config_result.warnings else None,
            "errors": config_result.errors if config_result.errors else None,
        }
    except Exception as e:
        logger.warning(f"Configuration check failed: {str(e)}")
        checks["configuration"] = {"status": "unknown", "error": str(e)}

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "service": {
            "name": "KPI Operations API",
            "version": "1.0.0",
            "uptime": uptime_formatted,
            "uptime_seconds": int(uptime_seconds),
            "started_at": APP_START_TIME.isoformat(),
        },
        "checks": checks,
    }


@router.get("/ready", response_model=Dict[str, Any])
async def readiness_check(db: Session = Depends(get_db)):
    """
    Kubernetes-style readiness probe

    Returns 200 if the service is ready to accept traffic.
    Returns 503 if any critical dependency is unavailable.
    """
    try:
        # Test database connection
        db.execute(_DB_PING_QUERY)

        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f"Readiness check failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service not ready")


@router.get("/live", response_model=Dict[str, Any])
async def liveness_check():
    """
    Kubernetes-style liveness probe

    Returns 200 if the service process is alive.
    Used by orchestrators to determine if the service needs to be restarted.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": int((datetime.utcnow() - APP_START_TIME).total_seconds()),
    }


def _format_uptime(seconds: float) -> str:
    """
    Format uptime in human-readable format

    Args:
        seconds: Total seconds of uptime

    Returns:
        Formatted string like "2d 3h 45m 12s"
    """
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)
