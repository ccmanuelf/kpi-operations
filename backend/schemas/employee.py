"""
EMPLOYEE table ORM schema (SQLAlchemy)
Source: 01-Core_DataEntities_Inventory.csv lines 43-53
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class Employee(Base):
    """EMPLOYEE table - Staff directory with floating pool flag"""
    __tablename__ = "EMPLOYEE"
    __table_args__ = {"extend_existing": True}

    # Primary key
    employee_id = Column(Integer, primary_key=True, autoincrement=True)

    # Employee identification
    employee_code = Column(String(50), unique=True, nullable=False, index=True)
    employee_name = Column(String(255), nullable=False)

    # Multi-client assignment (comma-separated client IDs for leaders/supervisors)
    client_id_assigned = Column(Text)  # NULL for floating pool, comma-separated for multi-client

    # Floating pool flag
    is_floating_pool = Column(Integer, nullable=False, default=0, index=True)  # Boolean: 0=regular, 1=floating

    # Status and department
    is_active = Column(Integer, nullable=False, default=1, index=True)  # Soft delete: 1=active, 0=inactive
    department = Column(String(50))  # Department classification

    # Additional info
    contact_phone = Column(String(50))
    contact_email = Column(String(255))
    position = Column(String(100))
    hire_date = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
