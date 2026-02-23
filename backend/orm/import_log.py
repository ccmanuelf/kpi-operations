"""
Import Log ORM schema (SQLAlchemy)
Tracks CSV and batch import operations for auditing
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base


class ImportLog(Base):
    """Import Log table for tracking all import operations"""

    __tablename__ = "import_log"
    __table_args__ = {"extend_existing": True}

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("USER.user_id"), nullable=False, index=True)
    import_timestamp = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    file_name = Column(String(255))
    rows_attempted = Column(Integer, nullable=False, default=0)
    rows_succeeded = Column(Integer, nullable=False, default=0)
    rows_failed = Column(Integer, nullable=False, default=0)
    error_details = Column(Text)  # JSON string of error details
    import_type = Column(String(50), nullable=False)  # 'csv_upload' or 'batch_import'
