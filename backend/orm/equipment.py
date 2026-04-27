"""
Equipment ORM schema (SQLAlchemy)
Machine/Equipment master registry for the production floor.
Equipment can be assigned to a production line or marked as shared (common resource).
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
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

    equipment_id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)
    line_id = Column(
        Integer, ForeignKey("PRODUCTION_LINE.line_id"), nullable=True, index=True
    )  # NULL for shared equipment
    equipment_code = Column(String(50), nullable=False)  # e.g., "MCH-001"
    equipment_name = Column(String(100), nullable=False)  # e.g., "Brother Industrial Sewing Machine"
    equipment_type = Column(String(50), nullable=True)  # e.g., "Sewing Machine", "Cutting Table", "Press"
    is_shared = Column(Boolean, default=False, nullable=False)  # True = common resource across lines
    status = Column(String(20), nullable=False, default="ACTIVE")  # ACTIVE, MAINTENANCE, RETIRED
    last_maintenance_date = Column(Date, nullable=True)
    next_maintenance_date = Column(Date, nullable=True)
    notes = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
