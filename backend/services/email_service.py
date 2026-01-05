"""
Email Service for KPI Platform
Handles email delivery using SendGrid or SMTP
"""
import os
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
    SENDGRID_AVAILABLE = True
except ImportError:
    SENDGRID_AVAILABLE = False

from backend.config import settings


class EmailService:
    """Service for sending emails with attachments"""

    def __init__(self):
        self.use_sendgrid = SENDGRID_AVAILABLE and hasattr(settings, 'SENDGRID_API_KEY') and settings.SENDGRID_API_KEY

        if not self.use_sendgrid:
            # SMTP configuration
            self.smtp_host = getattr(settings, 'SMTP_HOST', 'smtp.gmail.com')
            self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
            self.smtp_user = getattr(settings, 'SMTP_USER', '')
            self.smtp_password = getattr(settings, 'SMTP_PASSWORD', '')

    def send_kpi_report(
        self,
        to_emails: List[str],
        client_name: str,
        report_date: datetime,
        pdf_content: bytes,
        subject: Optional[str] = None,
        additional_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send KPI report email with PDF attachment

        Args:
            to_emails: List of recipient email addresses
            client_name: Name of the client
            report_date: Date of the report
            pdf_content: PDF file content as bytes
            subject: Optional custom subject line
            additional_message: Optional additional message to include

        Returns:
            Dict with status and message
        """
        if not subject:
            subject = f"Daily KPI Report - {client_name} - {report_date.strftime('%B %d, %Y')}"

        html_content = self._generate_email_template(
            client_name=client_name,
            report_date=report_date,
            additional_message=additional_message
        )

        if self.use_sendgrid:
            return self._send_via_sendgrid(
                to_emails=to_emails,
                subject=subject,
                html_content=html_content,
                pdf_content=pdf_content,
                pdf_filename=f"KPI_Report_{client_name}_{report_date.strftime('%Y%m%d')}.pdf"
            )
        else:
            return self._send_via_smtp(
                to_emails=to_emails,
                subject=subject,
                html_content=html_content,
                pdf_content=pdf_content,
                pdf_filename=f"KPI_Report_{client_name}_{report_date.strftime('%Y%m%d')}.pdf"
            )

    def _send_via_sendgrid(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str,
        pdf_content: bytes,
        pdf_filename: str
    ) -> Dict[str, Any]:
        """Send email via SendGrid API"""
        try:
            from_email = getattr(settings, 'REPORT_FROM_EMAIL', 'reports@kpi-platform.com')

            message = Mail(
                from_email=from_email,
                to_emails=to_emails,
                subject=subject,
                html_content=html_content
            )

            # Attach PDF
            import base64
            encoded_pdf = base64.b64encode(pdf_content).decode()

            attachment = Attachment(
                FileContent(encoded_pdf),
                FileName(pdf_filename),
                FileType('application/pdf'),
                Disposition('attachment')
            )
            message.attachment = attachment

            # Send email
            sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
            response = sg.send(message)

            return {
                'success': True,
                'status_code': response.status_code,
                'message': 'Email sent successfully via SendGrid'
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to send email via SendGrid: {str(e)}'
            }

    def _send_via_smtp(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str,
        pdf_content: bytes,
        pdf_filename: str
    ) -> Dict[str, Any]:
        """Send email via SMTP"""
        try:
            from_email = getattr(settings, 'REPORT_FROM_EMAIL', self.smtp_user)

            # Create message
            msg = MIMEMultipart('mixed')
            msg['Subject'] = subject
            msg['From'] = from_email
            msg['To'] = ', '.join(to_emails)

            # Attach HTML body
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)

            # Attach PDF
            pdf_attachment = MIMEApplication(pdf_content, _subtype='pdf')
            pdf_attachment.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
            msg.attach(pdf_attachment)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            return {
                'success': True,
                'message': 'Email sent successfully via SMTP'
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to send email via SMTP: {str(e)}'
            }

    def _generate_email_template(
        self,
        client_name: str,
        report_date: datetime,
        additional_message: Optional[str] = None
    ) -> str:
        """Generate HTML email template"""

        template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KPI Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #1976d2;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .content {{
            background-color: #f5f5f5;
            padding: 30px;
            border-radius: 0 0 5px 5px;
        }}
        .info-box {{
            background-color: white;
            padding: 15px;
            margin: 15px 0;
            border-left: 4px solid #1976d2;
            border-radius: 3px;
        }}
        .footer {{
            text-align: center;
            margin-top: 20px;
            font-size: 12px;
            color: #666;
        }}
        .button {{
            display: inline-block;
            background-color: #1976d2;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 3px;
            margin: 10px 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Daily KPI Report</h1>
        <p>{client_name}</p>
    </div>

    <div class="content">
        <p>Dear Team,</p>

        <p>Please find attached your daily KPI performance report for <strong>{report_date.strftime('%B %d, %Y')}</strong>.</p>

        {f'<div class="info-box"><p>{additional_message}</p></div>' if additional_message else ''}

        <div class="info-box">
            <h3>Report Contents:</h3>
            <ul>
                <li>Executive Summary with all KPI metrics</li>
                <li>Production efficiency and performance data</li>
                <li>Quality metrics (FPY, PPM, DPMO)</li>
                <li>Equipment availability and downtime analysis</li>
                <li>Attendance and absenteeism rates</li>
                <li>On-time delivery performance</li>
            </ul>
        </div>

        <p>The detailed PDF report is attached to this email. If you have any questions or need additional information, please don't hesitate to reach out.</p>

        <p><strong>Key Highlights:</strong></p>
        <ul>
            <li>Review the Executive Summary for overall performance</li>
            <li>Check trend indicators for areas requiring attention</li>
            <li>Focus on metrics marked as "At Risk" or "Critical"</li>
        </ul>

        <p>Best regards,<br>
        <strong>KPI Operations Platform</strong></p>
    </div>

    <div class="footer">
        <p>This is an automated report generated by the KPI Operations Platform.</p>
        <p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
</body>
</html>
"""

        return template

    def send_test_email(self, to_email: str) -> Dict[str, Any]:
        """Send a test email to verify configuration"""
        subject = "Test Email - KPI Platform"
        html_content = """
        <html>
            <body>
                <h2>Test Email</h2>
                <p>This is a test email from the KPI Operations Platform.</p>
                <p>If you received this email, your email configuration is working correctly.</p>
            </body>
        </html>
        """

        if self.use_sendgrid:
            try:
                from_email = getattr(settings, 'REPORT_FROM_EMAIL', 'reports@kpi-platform.com')
                message = Mail(
                    from_email=from_email,
                    to_emails=[to_email],
                    subject=subject,
                    html_content=html_content
                )
                sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
                response = sg.send(message)
                return {'success': True, 'status_code': response.status_code}
            except Exception as e:
                return {'success': False, 'error': str(e)}
        else:
            try:
                from_email = getattr(settings, 'REPORT_FROM_EMAIL', self.smtp_user)
                msg = MIMEMultipart()
                msg['Subject'] = subject
                msg['From'] = from_email
                msg['To'] = to_email
                msg.attach(MIMEText(html_content, 'html'))

                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls()
                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)
                    server.send_message(msg)
                return {'success': True}
            except Exception as e:
                return {'success': False, 'error': str(e)}
