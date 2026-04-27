"""
JOB table ORM schema (SQLAlchemy)
Line items within work orders for detailed tracking
Source: 01-Core_DataEntities_Inventory.csv lines 34-51
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class Job(Base):
    """JOB table - Work order line items with part-level detail"""

    __tablename__ = "JOB"
    __table_args__ = {"extend_existing": True}

    # Primary key
    job_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)

    # Parent work order
    work_order_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("WORK_ORDER.work_order_id"), nullable=False, index=True
    )

    # Multi-tenant isolation (CRITICAL SECURITY FIX)
    client_id_fk: Mapped[str] = mapped_column(String(50), ForeignKey("CLIENT.client_id"), nullable=False, index=True)

    # Operation details
    operation_name: Mapped[str] = mapped_column(String(255), nullable=False)
    operation_code: Mapped[Optional[str]] = mapped_column(String(50))
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)  # Order within work order

    # Part details (for quality DPMO calculation)
    part_number: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    part_description: Mapped[Optional[str]] = mapped_column(String(255))

    # Quantity tracking
    planned_quantity: Mapped[Optional[int]] = mapped_column(Integer)
    completed_quantity: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    quantity_scrapped: Mapped[Optional[int]] = mapped_column(Integer, default=0)  # Scrap tracking

    # Time tracking
    planned_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    actual_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))

    # Status
    is_completed: Mapped[Optional[int]] = mapped_column(Integer, default=0)  # Boolean
    completed_date: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Assigned resources
    assigned_employee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("EMPLOYEE.employee_id"))
    assigned_shift_id: Mapped[Optional[int]] = mapped_column(Integer)

    # Metadata
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
