"""
Shift coverage database schema (SQLAlchemy)
PHASE 3: Shift coverage tracking
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class ShiftCoverage(Base):
    """Shift coverage table"""

    __tablename__ = "shift_coverage"
    __table_args__ = {"extend_existing": True}

    coverage_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    shift_id: Mapped[int] = mapped_column(Integer, ForeignKey("SHIFT.shift_id"), nullable=False)
    coverage_date: Mapped[date] = mapped_column(Date, nullable=False)
    required_employees: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_employees: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))  # Calculated field
    notes: Mapped[Optional[str]] = mapped_column(Text)
    entered_by: Mapped[int] = mapped_column(Integer, ForeignKey("USER.user_id"), nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )
