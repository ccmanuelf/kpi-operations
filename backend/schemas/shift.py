"""
Shift ORM schema (SQLAlchemy)
"""

from sqlalchemy import Column, Integer, String, Boolean, Time, TIMESTAMP, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from backend.database import Base


class Shift(Base):
    """Shift table ORM"""

    __tablename__ = "SHIFT"
    __table_args__ = (
        UniqueConstraint("client_id", "shift_name", name="uq_shift_client_name"),
        {"extend_existing": True},
    )

    shift_id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)
    shift_name = Column(String(50), nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())
