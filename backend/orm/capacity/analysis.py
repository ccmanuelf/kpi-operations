"""
Capacity Analysis - Utilization calculations per line/week
Stores capacity analysis results following the 12-step calculation method.
"""

from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class CapacityAnalysis(Base):
    """
    CAPACITY_ANALYSIS table - Line capacity utilization analysis

    Purpose:
    - Store capacity analysis results per line per period
    - Implement the 12-step capacity calculation methodology
    - Identify bottlenecks and utilization issues

    12-Step Capacity Calculation:
    1. Working days in period
    2. Shifts per day
    3. Hours per shift
    4. Gross hours = days * shifts * hours
    5. Operators available
    6. Efficiency factor (e.g., 85%)
    7. Absenteeism factor (e.g., 5%)
    8. Net hours = gross * efficiency * (1 - absenteeism)
    9. Capacity hours = net * operators
    10. Demand hours (from orders/schedule)
    11. Utilization % = demand / capacity
    12. Bottleneck flag if utilization > threshold

    Multi-tenant: All records isolated by client_id
    """

    __tablename__ = "capacity_analysis"
    __table_args__ = (
        Index("ix_capacity_analysis_line_date", "client_id", "line_id", "analysis_date"),
        Index("ix_capacity_analysis_date", "client_id", "analysis_date"),
        Index("ix_capacity_analysis_bottleneck", "client_id", "is_bottleneck"),
        {"extend_existing": True},
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Analysis period/date (indexed via composite indexes in __table_args__)
    analysis_date: Mapped[date_type] = mapped_column(Date, nullable=False)

    # Line reference (indexed via composite index in __table_args__)
    line_id: Mapped[int] = mapped_column(Integer, ForeignKey("capacity_production_lines.id"), nullable=False)
    line_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Denormalized for reporting
    department: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Denormalized for reporting

    # Step 1-4: Time-based capacity inputs
    working_days: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    shifts_per_day: Mapped[Optional[int]] = mapped_column(Integer, default=1)
    hours_per_shift: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), default=8.0)

    # Step 5: Labor availability
    operators_available: Mapped[Optional[int]] = mapped_column(Integer, default=0)

    # Steps 6-7: Efficiency factors (0-1 scale)
    efficiency_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), default=0.85)
    absenteeism_factor: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), default=0.05)

    # Step 4: Gross hours calculation (days * shifts * hours)
    gross_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=0)

    # Step 8: Net hours (gross * efficiency * (1 - absenteeism))
    net_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=0)

    # Step 9: Capacity hours (net * operators)
    capacity_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=0)

    # Step 10: Demand from schedule
    demand_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=0)
    demand_units: Mapped[Optional[int]] = mapped_column(Integer, default=0)

    # Steps 11-12: Analysis results
    utilization_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), default=0)
    is_bottleneck: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)

    # Notes/metadata
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def calculate_metrics(self, bottleneck_threshold: float = 95.0) -> None:
        """
        Calculate derived metrics from input values.
        Call this after setting input values.

        Args:
            bottleneck_threshold: Utilization % above which line is considered bottleneck
        """
        # Step 4: Gross hours
        days = int(self.working_days or 0)
        shifts = int(self.shifts_per_day or 1)
        hours = float(self.hours_per_shift or 8.0)
        gross = days * shifts * hours
        self.gross_hours = Decimal(str(gross))

        # Step 8: Net hours (apply efficiency and absenteeism)
        eff = float(self.efficiency_factor or 0.85)
        abs_factor = 1 - float(self.absenteeism_factor or 0.05)
        net = gross * eff * abs_factor
        self.net_hours = Decimal(str(net))

        # Step 9: Capacity hours
        operators = int(self.operators_available or 0)
        capacity = net * operators
        self.capacity_hours = Decimal(str(capacity))

        # Steps 11-12: Utilization and bottleneck
        if capacity > 0:
            demand = float(self.demand_hours or 0)
            utilization = (demand / capacity) * 100
            self.utilization_percent = Decimal(str(utilization))
            self.is_bottleneck = utilization >= bottleneck_threshold
        else:
            self.utilization_percent = Decimal("0")
            self.is_bottleneck = False

    def available_capacity_hours(self) -> float:
        """Calculate available (unused) capacity hours."""
        return max(0, float(self.capacity_hours or 0) - float(self.demand_hours or 0))

    def over_capacity_hours(self) -> float:
        """Calculate over-capacity hours (negative available)."""
        return max(0, float(self.demand_hours or 0) - float(self.capacity_hours or 0))

    def __repr__(self):
        return f"<CapacityAnalysis(line={self.line_code}, date={self.analysis_date}, util={self.utilization_percent}%)>"
