"""
Scheduled Daily Reports Task
Uses APScheduler for scheduling (Celery alternative for simplicity)
"""

from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, List
import logging

from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.database import get_db
from backend.reports.pdf_generator import PDFReportGenerator
from backend.services.email_service import EmailService
from backend.orm.client import Client
from backend.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DailyReportScheduler:
    """Schedule and execute daily KPI reports"""

    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler()
        self.email_service = EmailService()
        self.enabled = getattr(settings, "REPORT_EMAIL_ENABLED", True)
        self.report_time = getattr(settings, "REPORT_EMAIL_TIME", "06:00")

    def start(self) -> None:
        """Start the scheduler"""
        if not self.enabled:
            logger.info("Daily reports are disabled in configuration")
            return

        # Parse report time (HH:MM format)
        hour, minute = map(int, self.report_time.split(":"))

        # Schedule daily reports
        self.scheduler.add_job(
            func=self.send_daily_reports,
            trigger=CronTrigger(hour=hour, minute=minute),
            id="daily_kpi_reports",
            name="Send Daily KPI Reports",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(f"Daily report scheduler started. Reports will be sent at {self.report_time}")

    def stop(self) -> None:
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Daily report scheduler stopped")

    def send_daily_reports(self) -> None:
        """Generate and send reports for all active clients"""
        logger.info("Starting daily report generation")

        db = next(get_db())

        try:
            # Get all active clients
            clients = db.query(Client).filter(Client.is_active.is_(True)).all()

            logger.info(f"Found {len(clients)} active clients")

            report_date = datetime.now(tz=timezone.utc)
            start_date = date.today() - timedelta(days=1)  # Yesterday
            end_date = date.today()

            success_count = 0
            failure_count = 0

            for client in clients:
                try:
                    result = self.generate_and_send_report(
                        db=db, client=client, start_date=start_date, end_date=end_date, report_date=report_date
                    )

                    if result["success"]:
                        success_count += 1
                        logger.info(f"Successfully sent report for client: {client.client_name}")
                    else:
                        failure_count += 1
                        logger.error(f"Failed to send report for client {client.client_name}: {result.get('error')}")

                except Exception as e:
                    failure_count += 1
                    logger.error(f"Error processing report for client {client.client_name}: {str(e)}")

            logger.info(f"Daily report generation completed. Success: {success_count}, Failures: {failure_count}")

        except Exception as e:
            logger.error(f"Error in daily report generation: {str(e)}")
        finally:
            db.close()

    def generate_and_send_report(
        self, db: Session, client: Client, start_date: date, end_date: date, report_date: datetime
    ) -> Dict[str, Any]:
        """Generate and send report for a single client"""

        # Get client admin emails
        recipient_emails = self._get_client_admin_emails(db, client.client_id)

        if not recipient_emails:
            logger.warning(f"No admin emails found for client: {client.client_name}")
            return {"success": False, "error": "No recipient emails configured"}

        try:
            # Generate PDF report
            pdf_generator = PDFReportGenerator(db)
            pdf_buffer = pdf_generator.generate_report(
                client_id=client.client_id, start_date=start_date, end_date=end_date
            )

            # Send email. send_kpi_report is annotated Dict[str, Any] but
            # passes through Any for at least the SendGrid path (the
            # sendgrid client is import-shielded by try/except), so cast
            # explicitly to keep the no-any-return rule honest.
            result: Dict[str, Any] = self.email_service.send_kpi_report(
                to_emails=recipient_emails,
                client_name=client.client_name,
                report_date=report_date,
                pdf_content=pdf_buffer.getvalue(),
            )

            return result

        except Exception as e:
            logger.error(f"Error generating/sending report for {client.client_name}: {e}")
            return {"success": False, "error": "Report generation failed"}

    def _get_client_admin_emails(self, db: Session, client_id: str) -> List[str]:
        """Get list of admin email addresses for a client.

        The User table stores client assignment as a comma-separated
        string in `client_id_assigned` (e.g. "ACME-MFG,TEXTILE-PRO" for
        multi-client leaders) or NULL for global admin/poweruser. To
        match a specific client we LIKE-match the substring; admins
        with NULL assignment are global so they always qualify.
        """
        from backend.orm.user import User
        from sqlalchemy import or_

        admins = (
            db.query(User)
            .filter(
                or_(
                    User.client_id_assigned.is_(None),  # global admin/poweruser
                    User.client_id_assigned.like(f"%{client_id}%"),
                ),
                User.role.in_(["admin", "ADMIN"]),
                User.is_active.is_(True),
                User.email.isnot(None),
            )
            .all()
        )

        return [admin.email for admin in admins if admin.email]

    def send_manual_report(
        self, client_id: str, start_date: date, end_date: date, recipient_emails: List[str]
    ) -> Dict[str, Any]:
        """Manually trigger a report for specific client and date range"""

        db = next(get_db())

        try:
            client = db.query(Client).filter(Client.client_id == client_id).first()

            if not client:
                return {"success": False, "error": "Client not found"}

            # Generate PDF
            pdf_generator = PDFReportGenerator(db)
            pdf_buffer = pdf_generator.generate_report(client_id=client_id, start_date=start_date, end_date=end_date)

            # Send email — see generate_and_send_report for the type cast
            # rationale (sendgrid Any-leak via import-shielded fallback).
            result: Dict[str, Any] = self.email_service.send_kpi_report(
                to_emails=recipient_emails,
                client_name=client.client_name,
                report_date=datetime.now(tz=timezone.utc),
                pdf_content=pdf_buffer.getvalue(),
                additional_message="This is a manually requested report.",
            )

            return result

        except Exception as e:
            logger.error(f"Error in manual report generation: {e}")
            return {"success": False, "error": "Report generation failed"}
        finally:
            db.close()


# Global scheduler instance
scheduler = DailyReportScheduler()
