"""
Equipment ORM schema (SQLAlchemy)
Machine/Equipment master registry for the production floor.
Equipment can be assigned to a production line or marked as shared (common resource).
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class Equipment(Base):
    """EQUIPMENT table ORM - Machine/Equipment master registry."""

    __tablename__ = "EQUIPMENT"
    __table_args__ = (
        UniqueConstraint("client_id", "equipment_code", name="uq_equipment_client_code"),
        CheckConstraint(
            "status IN ('ACTIVE', 'MAINTENANCE', 'RETIRED')",
            name="ck_equipment_status",
        ),
        {"extend_existing": True},
    )

    equipment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)
    line_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("PRODUCTION_LINE.line_id"), nullable=True, index=True
    )  # NULL for shared equipment
    equipment_code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "MCH-001"
    equipment_name: Mapped[str] = mapped_column(String(100), nullable=False)
    equipment_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # "Sewing Machine", etc.
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # True = common resource
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")  # ACTIVE/MAINTENANCE/RETIRED
    last_maintenance_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    next_maintenance_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
