"""
Shift ORM schema (SQLAlchemy)
"""

from datetime import datetime, time
from typing import Optional

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class Shift(Base):
    """Shift table ORM"""

    __tablename__ = "SHIFT"
    __table_args__ = (
        UniqueConstraint("client_id", "shift_name", name="uq_shift_client_name"),
        {"extend_existing": True},
    )

    shift_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)
    line_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("PRODUCTION_LINE.line_id"), nullable=True, index=True
    )
    shift_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, server_default=func.now())
