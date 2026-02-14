"""
Import Log models for tracking CSV and batch imports
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class BatchImportRequest(BaseModel):
    """Request body for batch import"""

    entries: List[dict]


class BatchImportResponse(BaseModel):
    """Batch import result with logging"""

    total_rows: int
    successful: int
    failed: int
    errors: List[dict]
    created_entries: List[int]
    import_log_id: Optional[int] = None
    import_timestamp: datetime


class ImportLogResponse(BaseModel):
    """Import log entry response"""

    log_id: int
    user_id: int
    import_timestamp: datetime
    file_name: Optional[str]
    rows_attempted: int
    rows_succeeded: int
    rows_failed: int
    error_details: Optional[str]
    import_type: str  # 'csv_upload' or 'batch_import'

    class Config:
        from_attributes = True
