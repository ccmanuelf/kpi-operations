"""
Capacity Schedule - Production schedule
Two-table structure: Header (schedule metadata) and Detail (schedule line items).
"""

from sqlalchemy import Column, Integer, String, Date, Numeric, Boolean, ForeignKey, Text, Enum as SQLEnum, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from backend.database import Base
import enum


class ScheduleStatus(str, enum.Enum):
    """
    Schedule status lifecycle

    Workflow:
    DRAFT -> COMMITTED -> ACTIVE -> COMPLETED
              |
              v
         CANCELLED
    """

    DRAFT = "DRAFT"  # Being created/edited
    COMMITTED = "COMMITTED"  # Finalized, KPIs locked
    ACTIVE = "ACTIVE"  # In execution
    COMPLETED = "COMPLETED"  # Finished
    CANCELLED = "CANCELLED"  # Cancelled


class CapacitySchedule(Base):
    """
    CAPACITY_SCHEDULE table - Production schedule header

    Purpose:
    - Define production schedules with period and status
    - Track commitment date and user
    - Store KPI commitments as JSON when committed

    Multi-tenant: All records isolated by client_id
    """

    __tablename__ = "capacity_schedule"
    __table_args__ = (
        Index("ix_capacity_schedule_period", "client_id", "period_start", "period_end"),
        Index("ix_capacity_schedule_status", "client_id", "status"),
        {"extend_existing": True},
    )

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Schedule identification
    schedule_name = Column(String(100), nullable=False)

    # Period covered (indexed via composite index in __table_args__)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # Status tracking (indexed via composite index in __table_args__)
    status = Column(SQLEnum(ScheduleStatus), default=ScheduleStatus.DRAFT)

    # Commitment tracking
    committed_at = Column(Date, nullable=True)
    committed_by = Column(Integer, nullable=True)  # USER.user_id

    # KPI commitments stored as JSON when schedule is committed
    # Example: {"efficiency": 85.0, "quality": 98.5, "otd": 95.0}
    kpi_commitments_json = Column(JSON, nullable=True)

    # Notes/metadata
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationship to details
    details = relationship(
        "CapacityScheduleDetail", back_populates="schedule", cascade="all, delete-orphan", lazy="dynamic"
    )

    def is_editable(self) -> bool:
        """Check if schedule can be edited."""
        return self.status == ScheduleStatus.DRAFT

    def total_scheduled_quantity(self) -> int:
        """Calculate total scheduled quantity across all details."""
        return sum(d.scheduled_quantity or 0 for d in self.details)

    def total_completed_quantity(self) -> int:
        """Calculate total completed quantity across all details."""
        return sum(d.completed_quantity or 0 for d in self.details)

    def __repr__(self):
        return f"<CapacitySchedule(name={self.schedule_name}, period={self.period_start}-{self.period_end}, status={self.status})>"


class CapacityScheduleDetail(Base):
    """
    CAPACITY_SCHEDULE_DETAIL table - Production schedule line items

    Purpose:
    - Define what to produce on which line on which date
    - Track scheduled vs completed quantities
    - Support sequence/priority within day

    Multi-tenant: All records isolated by client_id
    """

    __tablename__ = "capacity_schedule_detail"
    __table_args__ = (
        Index("ix_capacity_schedule_detail_schedule", "schedule_id"),
        Index("ix_capacity_schedule_detail_date", "client_id", "scheduled_date"),
        Index("ix_capacity_schedule_detail_line", "client_id", "line_id", "scheduled_date"),
        Index("ix_capacity_schedule_detail_order", "client_id", "order_id"),
        {"extend_existing": True},
    )

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Parent schedule reference (indexed via composite index in __table_args__)
    schedule_id = Column(Integer, ForeignKey("capacity_schedule.id"), nullable=False)

    # Multi-tenant isolation - CRITICAL
    client_id = Column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # What to produce (indexed via composite index in __table_args__)
    order_id = Column(Integer, ForeignKey("capacity_orders.id"), nullable=True)
    order_number = Column(String(50), nullable=True)  # Denormalized for reporting
    style_code = Column(String(50), nullable=True)  # Denormalized for reporting

    # Where and when (indexed via composite indexes in __table_args__)
    line_id = Column(Integer, ForeignKey("capacity_production_lines.id"), nullable=True)
    line_code = Column(String(50), nullable=True)  # Denormalized for reporting
    scheduled_date = Column(Date, nullable=False)

    # Quantities
    scheduled_quantity = Column(Integer, default=0)
    completed_quantity = Column(Integer, default=0)

    # Sequence within day (for prioritization)
    sequence = Column(Integer, default=1)

    # Notes/metadata
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationship back to header
    schedule = relationship("CapacitySchedule", back_populates="details")

    def remaining_quantity(self) -> int:
        """Calculate remaining quantity to produce."""
        return max(0, (self.scheduled_quantity or 0) - (self.completed_quantity or 0))

    def completion_percent(self) -> float:
        """Calculate completion percentage."""
        if not self.scheduled_quantity or self.scheduled_quantity == 0:
            return 0.0
        return min(100.0, (self.completed_quantity or 0) / self.scheduled_quantity * 100)

    def __repr__(self):
        return f"<CapacityScheduleDetail(schedule_id={self.schedule_id}, date={self.scheduled_date}, order={self.order_number})>"
