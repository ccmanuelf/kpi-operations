"""
METRIC_CALCULATION_RESULT table — Phase 3 dual-view architecture.

Stores both the standard and site-adjusted result for every calculation run.
The `assumptions_snapshot` column captures the exact assumption values that
were active at calculation time, so historical results stay reproducible
even after assumptions later change or retire.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class MetricCalculationResult(Base):
    """One row per dual-view calculation run.

    `standard_value` and `site_adjusted_value` are stored as JSON strings —
    metric values may be Decimal, dict, list, or nested objects depending on
    the metric. Routes parse them on read.
    """

    __tablename__ = "METRIC_CALCULATION_RESULT"
    __table_args__ = (
        Index("ix_mcr_client_metric_calculated", "client_id", "metric_name", "calculated_at"),
        Index("ix_mcr_client_period", "client_id", "period_start", "period_end"),
        {"extend_existing": True},
    )

    result_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    client_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True
    )

    metric_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Both values stored as JSON-encoded strings — metric values vary in shape
    # (Decimal for OEE, nested dicts for FPY breakdown, etc.).
    standard_value_json: Mapped[str] = mapped_column(Text, nullable=False)
    site_adjusted_value_json: Mapped[str] = mapped_column(Text, nullable=False)

    # Numeric delta convenience columns. Populated only when both values are
    # scalar numerics (Decimal/float/int). NULL for nested/dict-shaped metrics.
    delta: Mapped[Optional[float]] = mapped_column(Float)
    delta_pct: Mapped[Optional[float]] = mapped_column(Float)

    # JSON snapshot of assumptions that affected the site_adjusted run.
    # Format: {assumption_name: {value, assumption_id, approved_by, approved_at}}.
    # Empty {} when no assumptions were active at calculation time.
    assumptions_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    # JSON snapshot of inputs the calculation consumed. The inspector UI shows
    # this so an auditor can see exactly which numbers fed the metric. Format
    # is metric-specific (see each *CalculationService for shape).
    inputs_snapshot_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    calculated_by: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("USER.user_id"), nullable=True
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), index=True
    )
