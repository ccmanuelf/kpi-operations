"""
Health Check and Database Monitoring Routes
Provides endpoints for system health and connection pool monitoring
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Dict, Any
import logging

from backend.database import get_db, get_pool_status

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["Health"])


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
        "version": "1.0.0"
    }


@router.get("/database", response_model=Dict[str, Any])
async def database_health(db: Session = Depends(get_db)):
    """
    Database health check
    Tests database connectivity and returns basic status
    """
    try:
        # Execute simple query to test connection
        result = db.execute(text("SELECT 1"))
        result.fetchone()

        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
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

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "pool": pool_stats
        }
    except Exception as e:
        logger.error(f"Pool status check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve pool status: {str(e)}"
        )


@router.get("/detailed", response_model=Dict[str, Any])
async def detailed_health_check(db: Session = Depends(get_db)):
    """
    Comprehensive health check
    Combines service, database, and connection pool status
    """
    try:
        # Database connectivity test
        db.execute(text("SELECT 1"))
        db_status = "connected"

        # Get pool statistics
        pool_stats = get_pool_status()

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": {
                "name": "KPI Operations API",
                "version": "1.0.0",
                "uptime": "N/A"  # Can be implemented with start time tracking
            },
            "database": {
                "status": db_status,
                "pool": pool_stats
            }
        }
    except Exception as e:
        logger.error(f"Detailed health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )
