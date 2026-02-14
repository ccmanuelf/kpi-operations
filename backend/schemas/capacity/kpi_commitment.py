"""
Capacity KPI Commitment - KPI targets and actuals tracking
Links committed KPI targets to schedules for variance analysis.
"""

from sqlalchemy import Column, Integer, String, Date, Numeric, ForeignKey, Text, Index
from sqlalchemy.sql import func
from sqlalchemy import DateTime
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
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Schedule reference (indexed via composite index in __table_args__)
    schedule_id = Column(Integer, ForeignKey("capacity_schedule.id"), nullable=False)

    # KPI identification (indexed via composite index in __table_args__)
    kpi_key = Column(String(50), nullable=False)  # efficiency, quality, otd, etc.
    kpi_name = Column(String(100), nullable=True)  # Human-readable name

    # Period covered (indexed via composite index in __table_args__)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # Target and actual values
    committed_value = Column(Numeric(12, 4), nullable=False)
    actual_value = Column(Numeric(12, 4), nullable=True)

    # Variance calculations
    variance = Column(Numeric(12, 4), nullable=True)  # actual - committed
    variance_percent = Column(Numeric(6, 2), nullable=True)  # ((actual - committed) / committed) * 100

    # Notes/metadata
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def calculate_variance(self) -> None:
        """
        Calculate variance from committed and actual values.
        Call this after setting actual_value.
        """
        if self.actual_value is not None and self.committed_value is not None:
            committed = float(self.committed_value)
            actual = float(self.actual_value)

            self.variance = actual - committed

            if committed != 0:
                self.variance_percent = ((actual - committed) / committed) * 100
            else:
                self.variance_percent = 0 if actual == 0 else 100

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

    def __repr__(self):
        return f"<CapacityKPICommitment(schedule_id={self.schedule_id}, kpi={self.kpi_key}, committed={self.committed_value}, actual={self.actual_value})>"
