"""
ProductionLine ORM schema (SQLAlchemy)
Operational production line entity for factory topology management.
Distinct from CapacityProductionLine which is used for capacity planning.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base


class ProductionLine(Base):
    """
    PRODUCTION_LINE table - Operational production line entity.

    Purpose:
    - Track factory areas (cutting, kitting, embroidery, sewing, inspection, packaging)
    - Support self-referential hierarchy (parent sections with child sub-lines)
    - Soft-delete via is_active flag

    Multi-tenant: All records isolated by client_id.
    """

    __tablename__ = "PRODUCTION_LINE"
    __table_args__ = (
        UniqueConstraint("client_id", "line_code", name="uq_production_line_client_code"),
        CheckConstraint(
            "line_type IN ('DEDICATED', 'SHARED', 'SECTION')",
            name="ck_production_line_type",
        ),
        {"extend_existing": True},
    )

    line_id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)
    line_code = Column(String(50), nullable=False)  # e.g., "SEW-01", "CUT-01"
    line_name = Column(String(100), nullable=False)  # e.g., "Sewing Line 1"
    department = Column(String(50), nullable=True)  # CUTTING, SEWING, FINISHING, etc.
    line_type = Column(String(20), nullable=False, default="DEDICATED")
    parent_line_id = Column(Integer, ForeignKey("PRODUCTION_LINE.line_id"), nullable=True)
    max_operators = Column(Integer, nullable=True)

    # Bridge to Capacity Planning: links operational line to its capacity counterpart.
    # NULL means the line exists only in the operational context.
    capacity_line_id = Column(
        Integer,
        ForeignKey("capacity_production_lines.id"),
        nullable=True,
    )

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Self-referential: remote_side points to the "one" side (parent's PK)
    parent = relationship(
        "ProductionLine",
        remote_side=[line_id],
        backref="children",
    )

    def __repr__(self):
        return (
            f"<ProductionLine(line_id={self.line_id}, client_id={self.client_id}, "
            f"code={self.line_code}, dept={self.department})>"
        )
