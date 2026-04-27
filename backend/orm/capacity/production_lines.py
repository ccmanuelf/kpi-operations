"""
Capacity Production Lines - Line capacity specifications
Defines production lines with capacity parameters for capacity planning.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class CapacityProductionLine(Base):
    """
    CAPACITY_PRODUCTION_LINES table - Production line capacity configuration

    Purpose:
    - Define available production lines
    - Store capacity parameters (units/hour, operators, efficiency)
    - Track line-specific absenteeism and efficiency factors

    Multi-tenant: All records isolated by client_id
    """

    __tablename__ = "capacity_production_lines"
    __table_args__ = {"extend_existing": True}

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Line identification
    line_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    line_name: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # CUTTING/SEWING/FINISHING/etc.

    # Capacity parameters
    standard_capacity_units_per_hour: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=0)
    max_operators: Mapped[Optional[int]] = mapped_column(Integer, default=10)

    # Efficiency factor (0-1 scale, e.g., 0.85 = 85%)
    efficiency_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), default=0.85)

    # Absenteeism factor (0-1 scale, e.g., 0.05 = 5%)
    absenteeism_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), default=0.05)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Notes/metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def effective_capacity_per_hour(self) -> float:
        """Calculate effective capacity considering efficiency and absenteeism."""
        base = float(self.standard_capacity_units_per_hour or 0)
        eff = float(self.efficiency_factor or 0.85)
        abs_factor = 1 - float(self.absenteeism_factor or 0.05)
        return base * eff * abs_factor

    def __repr__(self):
        return f"<CapacityProductionLine(client_id={self.client_id}, code={self.line_code}, dept={self.department})>"
