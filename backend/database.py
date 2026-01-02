"""
Database connection and session management
SQLAlchemy setup for MariaDB
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from backend.config import settings

# Create database engine
# For SQLite, use check_same_thread=False and simplified pool settings
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True if "mysql" in settings.DATABASE_URL else False,
    pool_size=10 if "mysql" in settings.DATABASE_URL else 5,
    max_overflow=20 if "mysql" in settings.DATABASE_URL else 10
)

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
