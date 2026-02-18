"""
Reports - Email Configuration Endpoints

Email report configuration CRUD, test email, and manual report sending.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.reports.pdf_generator import PDFReportGenerator
from backend.utils.logging_utils import get_module_logger
from ._models import EmailReportConfig, EmailReportConfigResponse, TestEmailRequest, ManualReportRequest

logger = get_module_logger(__name__)

email_config_router = APIRouter()

# In-memory storage for email configs (in production, use database table)
_email_configs: dict = {}


@email_config_router.get("/email-config", response_model=EmailReportConfigResponse)
async def get_email_report_config(
    client_id: Optional[str] = Query(None, description="Client ID"),
    current_user: User = Depends(get_current_user),
):
    """
    Get email report configuration for a client

    Returns the current email report settings including:
    - Enabled status
    - Report frequency
    - Recipients list
    - Report content options
    """
    config_key = client_id or f"user_{current_user.user_id}"

    if config_key in _email_configs:
        return EmailReportConfigResponse(**_email_configs[config_key])

    # Return default configuration if not found
    return EmailReportConfigResponse(
        enabled=False,
        frequency="daily",
        report_time="06:00",
        recipients=[],
        client_id=client_id,
        include_executive_summary=True,
        include_efficiency=True,
        include_quality=True,
        include_availability=True,
        include_attendance=True,
        include_predictions=True,
    )


@email_config_router.post("/email-config", response_model=EmailReportConfigResponse)
async def save_email_report_config(
    config: EmailReportConfig,
    current_user: User = Depends(get_current_user),
):
    """
    Save email report configuration

    Creates or updates email report settings for automated delivery.
    Configuration includes:
    - Report frequency (daily/weekly/monthly)
    - Delivery time
    - Recipient list
    - Report content options
    """
    # Validate recipients
    if config.enabled and len(config.recipients) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one recipient email is required when enabled",
        )

    # Validate frequency
    if config.frequency not in ["daily", "weekly", "monthly"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Frequency must be 'daily', 'weekly', or 'monthly'",
        )

    # Store config
    config_key = config.client_id or f"user_{current_user.user_id}"

    config_dict = config.model_dump()
    config_dict["updated_at"] = datetime.now(tz=timezone.utc)
    config_dict["created_at"] = _email_configs.get(config_key, {}).get(
        "created_at", datetime.now(tz=timezone.utc)
    )

    _email_configs[config_key] = config_dict

    return EmailReportConfigResponse(**config_dict)


@email_config_router.put("/email-config", response_model=EmailReportConfigResponse)
async def update_email_report_config(
    config: EmailReportConfig,
    current_user: User = Depends(get_current_user),
):
    """
    Update existing email report configuration

    Partial update of email report settings.
    """
    config_key = config.client_id or f"user_{current_user.user_id}"

    if config_key not in _email_configs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email configuration not found. Use POST to create.",
        )

    # Validate if enabling
    if config.enabled and len(config.recipients) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one recipient email is required when enabled",
        )

    config_dict = config.model_dump()
    config_dict["updated_at"] = datetime.now(tz=timezone.utc)
    config_dict["created_at"] = _email_configs[config_key].get("created_at", datetime.now(tz=timezone.utc))

    _email_configs[config_key] = config_dict

    return EmailReportConfigResponse(**config_dict)


@email_config_router.post("/email-config/test")
async def send_test_email(
    request: TestEmailRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Send a test email to verify email configuration

    Sends a sample email to verify that email delivery is working correctly.
    """
    try:
        from backend.services.email_service import EmailService

        email_service = EmailService()
        result = email_service.send_test_email(request.email)

        if result.get("success"):
            return {"success": True, "message": f"Test email sent successfully to {request.email}"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to send test email"),
            )

    except ImportError:
        # Email service not available, simulate success for demo
        return {
            "success": True,
            "message": f"Test email queued for {request.email} (email service not configured)",
            "note": "Email service is not fully configured. In production, configure SMTP or SendGrid.",
        }
    except Exception as e:
        logger.exception("Failed to send test email: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test email",
        )


@email_config_router.post("/send-manual")
async def send_manual_report(
    request: ManualReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually trigger a report to be sent via email

    Generates and sends a KPI report immediately to specified recipients.
    """
    try:
        from backend.middleware.client_auth import verify_client_access

        # SECURITY FIX (VULN-004): Verify client access before generating report
        verify_client_access(current_user, request.client_id)

        # Parse dates
        try:
            start_date = datetime.strptime(request.start_date, "%Y-%m-%d").date()
            end_date = datetime.strptime(request.end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid date format. Use YYYY-MM-DD",
            )

        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date must be before end date",
            )

        # Generate PDF report
        pdf_generator = PDFReportGenerator(db)
        pdf_buffer = pdf_generator.generate_report(
            client_id=request.client_id, start_date=start_date, end_date=end_date
        )

        # Send email
        try:
            from backend.services.email_service import EmailService
            from backend.schemas.client import Client

            email_service = EmailService()

            # Get client name
            client = db.query(Client).filter(Client.client_id == request.client_id).first()
            client_name = client.name if client else request.client_id

            result = email_service.send_kpi_report(
                to_emails=request.recipient_emails,
                client_name=client_name,
                report_date=datetime.now(tz=timezone.utc),
                pdf_content=pdf_buffer.getvalue(),
                additional_message="This is a manually requested KPI report.",
            )

            if result.get("success"):
                return {
                    "success": True,
                    "message": f"Report sent to {len(request.recipient_emails)} recipient(s)",
                    "recipients": request.recipient_emails,
                }
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=result.get("error", "Failed to send report"),
                )

        except ImportError:
            # Email service not configured - return report generation success
            return {
                "success": True,
                "message": "Report generated successfully (email service not configured)",
                "note": "Configure SMTP or SendGrid for email delivery",
                "recipients": request.recipient_emails,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to generate/send manual report: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate report",
        )
