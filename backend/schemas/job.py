"""
JOB table ORM schema (SQLAlchemy)
Line items within work orders for detailed tracking
Source: 01-Core_DataEntities_Inventory.csv lines 34-51
"""
from sqlalchemy import Column, Integer, String, Numeric, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class Job(Base):
    """JOB table - Work order line items with part-level detail"""
    __tablename__ = "JOB"
    __table_args__ = {"extend_existing": True}

    # Primary key
    job_id = Column(String(50), primary_key=True, index=True)

    # Parent work order
    work_order_id = Column(String(50), ForeignKey('WORK_ORDER.work_order_id'), nullable=False, index=True)

    # Multi-tenant isolation (CRITICAL SECURITY FIX)
    client_id_fk = Column(String(50), ForeignKey('CLIENT.client_id'), nullable=False, index=True)

    # Operation details
    operation_name = Column(String(255), nullable=False)
    operation_code = Column(String(50))
    sequence_number = Column(Integer, nullable=False)  # Order within work order

    # Part details (for quality DPMO calculation)
    part_number = Column(String(100), index=True)
    part_description = Column(String(255))

    # Quantity tracking
    planned_quantity = Column(Integer)
    completed_quantity = Column(Integer, default=0)
    quantity_scrapped = Column(Integer, default=0)  # Scrap tracking for quality metrics

    # Time tracking
    planned_hours = Column(Numeric(10, 2))
    actual_hours = Column(Numeric(10, 2))

    # Status
    is_completed = Column(Integer, default=0)  # Boolean
    completed_date = Column(DateTime)

    # Assigned resources
    assigned_employee_id = Column(Integer, ForeignKey('EMPLOYEE.employee_id'))
    assigned_shift_id = Column(Integer)

    # Metadata
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
