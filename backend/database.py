"""
Database connection and session management with optimized connection pooling
SQLAlchemy setup for MariaDB/MySQL with production-ready pool configuration

Connection Pool Configuration:
- Pool Size: Number of connections kept in the pool (configurable via env)
- Max Overflow: Additional connections beyond pool_size when needed
- Pool Timeout: Seconds to wait for a connection before raising error
- Pool Recycle: Seconds before recycling connections (prevents stale connections)
- Pool Pre-ping: Test connection health before using (prevents invalid connections)
"""
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool, NullPool
from backend.config import settings
import logging

logger = logging.getLogger(__name__)

# Determine if we're using a database that supports connection pooling
is_mysql = "mysql" in settings.DATABASE_URL.lower()
is_sqlite = "sqlite" in settings.DATABASE_URL.lower()

# Create database engine with optimized connection pooling
# SQLite uses NullPool (no pooling) due to thread safety limitations
# MySQL/MariaDB uses QueuePool with configurable pool settings
if is_sqlite:
    # SQLite configuration: No pooling, check_same_thread=False
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
        poolclass=NullPool  # SQLite doesn't benefit from connection pooling
    )
    logger.info("Database engine created with SQLite (NullPool)")
else:
    # MySQL/MariaDB configuration: QueuePool with production settings
    engine = create_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        poolclass=QueuePool,
        pool_size=settings.DATABASE_POOL_SIZE,  # Base pool size: 20 connections
        max_overflow=settings.DATABASE_MAX_OVERFLOW,  # Additional connections: 10
        pool_timeout=settings.DATABASE_POOL_TIMEOUT,  # Wait timeout: 30 seconds
        pool_recycle=settings.DATABASE_POOL_RECYCLE,  # Recycle after: 3600 seconds (1 hour)
        pool_pre_ping=True  # Test connections before using (prevents invalid connections)
    )
    logger.info(
        f"Database engine created with connection pooling: "
        f"pool_size={settings.DATABASE_POOL_SIZE}, "
        f"max_overflow={settings.DATABASE_MAX_OVERFLOW}, "
        f"timeout={settings.DATABASE_POOL_TIMEOUT}s, "
        f"recycle={settings.DATABASE_POOL_RECYCLE}s"
    )

# Connection pool event listeners for monitoring and debugging
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log new database connections"""
    logger.debug("New database connection established")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log connection checkout from pool"""
    logger.debug("Connection checked out from pool")


@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """Log connection return to pool"""
    logger.debug("Connection returned to pool")


# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()


def get_db():
    """
    Dependency for FastAPI routes
    Yields database session and ensures cleanup
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_pool_status():
    """
    Get current connection pool statistics
    Returns dictionary with pool metrics for monitoring
    """
    if isinstance(engine.pool, NullPool):
        return {
            "pool_type": "NullPool",
            "description": "SQLite - No connection pooling"
        }

    pool = engine.pool
    return {
        "pool_type": "QueuePool",
        "pool_size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "total_connections": pool.size() + pool.overflow(),
        "max_capacity": settings.DATABASE_POOL_SIZE + settings.DATABASE_MAX_OVERFLOW,
        "utilization_percent": round(
            ((pool.checkedout()) / (settings.DATABASE_POOL_SIZE + settings.DATABASE_MAX_OVERFLOW)) * 100, 2
        ) if settings.DATABASE_POOL_SIZE + settings.DATABASE_MAX_OVERFLOW > 0 else 0,
        "configuration": {
            "pool_size": settings.DATABASE_POOL_SIZE,
            "max_overflow": settings.DATABASE_MAX_OVERFLOW,
            "pool_timeout": settings.DATABASE_POOL_TIMEOUT,
            "pool_recycle": settings.DATABASE_POOL_RECYCLE,
            "pool_pre_ping": True if not is_sqlite else False
        }
    }
