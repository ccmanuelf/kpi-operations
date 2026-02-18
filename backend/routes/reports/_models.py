"""
Reports - Shared Pydantic Models

Request/response models shared across reports sub-modules.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class EmailReportConfig(BaseModel):
    """Email report configuration schema"""

    enabled: bool = False
    frequency: str = "daily"  # daily, weekly, monthly
    report_time: str = "06:00"
    recipients: List[str] = []
    client_id: Optional[str] = None
    include_executive_summary: bool = True
    include_efficiency: bool = True
    include_quality: bool = True
    include_availability: bool = True
    include_attendance: bool = True
    include_predictions: bool = True


class EmailReportConfigResponse(EmailReportConfig):
    """Response model with additional fields"""

    config_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TestEmailRequest(BaseModel):
    """Request model for test email"""

    email: str


class ManualReportRequest(BaseModel):
    """Request model for manual report generation"""

    client_id: str
    start_date: str
    end_date: str
    recipient_emails: List[str]
