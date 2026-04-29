"""
Capacity KPI Commitment - KPI targets and actuals tracking
Links committed KPI targets to schedules for variance analysis.
"""

from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class CapacityKPICommitment(Base):
    """
    CAPACITY_KPI_COMMITMENT table - KPI targets and actuals

    Purpose:
    - Store KPI commitments when schedule is committed
    - Track actual values against commitments
    - Calculate variance for performance analysis

    Standard KPIs:
    - efficiency: Production efficiency percentage
    - quality: Quality/yield percentage
    - otd: On-Time Delivery percentage
    - utilization: Capacity utilization percentage
    - cost_per_unit: Production cost per unit

    Multi-tenant: All records isolated by client_id
    """

    __tablename__ = "capacity_kpi_commitment"
    __table_args__ = (
        Index("ix_capacity_kpi_schedule", "client_id", "schedule_id"),
        Index("ix_capacity_kpi_key", "client_id", "kpi_key"),
        Index("ix_capacity_kpi_period", "client_id", "period_start", "period_end"),
        {"extend_existing": True},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Schedule reference (indexed via composite index in __table_args__)
    schedule_id: Mapped[int] = mapped_column(Integer, ForeignKey("capacity_schedule.id"), nullable=False)

    # KPI identification (indexed via composite index in __table_args__)
    kpi_key: Mapped[str] = mapped_column(String(50), nullable=False)  # efficiency, quality, otd, etc.
    kpi_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Human-readable name

    # Period covered (indexed via composite index in __table_args__)
    period_start: Mapped[date_type] = mapped_column(Date, nullable=False)
    period_end: Mapped[date_type] = mapped_column(Date, nullable=False)

    # Target and actual values
    committed_value: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    actual_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)

    # Variance calculations
    variance: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)  # actual - committed
    variance_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)  # variance %

    # Notes/metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def calculate_variance(self) -> None:
        """
        Calculate variance from committed and actual values.
        Call this after setting actual_value.
        """
        if self.actual_value is not None and self.committed_value is not None:
            committed = float(self.committed_value)
            actual = float(self.actual_value)

            # variance/variance_percent are Mapped[Decimal] in the ORM,
            # so write Decimal values rather than floats. Wrapping
            # `actual - committed` in Decimal(str(...)) keeps precision
            # parity with how the values came in.
            self.variance = Decimal(str(actual - committed))

            if committed != 0:
                self.variance_percent = Decimal(str(((actual - committed) / committed) * 100))
            else:
                self.variance_percent = Decimal("0") if actual == 0 else Decimal("100")

    def is_on_target(self, tolerance_percent: float = 5.0) -> bool:
        """
        Check if actual is within tolerance of committed.

        Args:
            tolerance_percent: Acceptable variance percentage (default 5%)

        Returns:
            True if within tolerance, False otherwise
        """
        if self.variance_percent is None:
            return False
        return abs(float(self.variance_percent)) <= tolerance_percent

    def is_above_target(self) -> bool:
        """Check if actual exceeds committed (positive variance)."""
        if self.variance is None:
            return False
        return float(self.variance) > 0

    def is_below_target(self) -> bool:
        """Check if actual is below committed (negative variance)."""
        if self.variance is None:
            return False
        return float(self.variance) < 0

    def __repr__(self) -> str:
        return f"<CapacityKPICommitment(schedule_id={self.schedule_id}, kpi={self.kpi_key}, committed={self.committed_value}, actual={self.actual_value})>"
