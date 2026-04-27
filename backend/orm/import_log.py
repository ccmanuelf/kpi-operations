"""
Import Log ORM schema (SQLAlchemy)
Tracks CSV and batch import operations for auditing
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.database import Base


class ImportLog(Base):
    """Import Log table for tracking all import operations"""

    __tablename__ = "import_log"
    __table_args__ = {"extend_existing": True}

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("USER.user_id"), nullable=False, index=True)
    import_timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), index=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255))
    rows_attempted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_succeeded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rows_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_details: Mapped[Optional[str]] = mapped_column(Text)  # JSON string of error details
    import_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'csv_upload' or 'batch_import'
