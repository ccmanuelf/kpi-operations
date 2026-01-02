"""
Shift ORM schema (SQLAlchemy)
"""
from sqlalchemy import Column, Integer, String, Boolean, Time, TIMESTAMP
from sqlalchemy.sql import func
from backend.database import Base


class Shift(Base):
    """Shift table ORM"""
    __tablename__ = "shift"

    shift_id = Column(Integer, primary_key=True, autoincrement=True)
    shift_name = Column(String(50), unique=True, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
