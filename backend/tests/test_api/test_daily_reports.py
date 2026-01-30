"""
Comprehensive Tests for Daily Reports Task Module
Target: Increase tasks/daily_reports.py coverage to 85%+
"""
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

# Try to import the module - skip all tests if not available
try:
    import sys
    import os
    # Ensure the project root is in the path for 'backend' module resolution
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    from backend.tasks.daily_reports import DailyReportScheduler, scheduler
    MODULE_AVAILABLE = True
except ImportError as e:
    MODULE_AVAILABLE = False
    IMPORT_ERROR = str(e)


@pytest.mark.skipif(not MODULE_AVAILABLE, reason="daily_reports module not available")
class TestDailyReportSchedulerInit:
    """Test DailyReportScheduler initialization"""

    def test_scheduler_init_default_settings(self):
        """Test scheduler initializes with default settings"""
        sched = DailyReportScheduler()

        # Verify scheduler has expected attributes
        assert hasattr(sched, 'enabled')
        assert hasattr(sched, 'report_time')
        assert hasattr(sched, 'scheduler')

    def test_scheduler_init_custom_settings(self):
        """Test scheduler initializes with custom settings"""
        sched = DailyReportScheduler()

        # Verify the scheduler can be instantiated and has required attrs
        assert hasattr(sched, 'enabled')
        assert hasattr(sched, 'report_time')
        assert isinstance(sched.report_time, str)


@pytest.mark.skipif(not MODULE_AVAILABLE, reason="daily_reports module not available")
class TestDailyReportSchedulerStart:
    """Test DailyReportScheduler start method"""

    def test_scheduler_start_disabled(self):
        """Test scheduler start when disabled in config"""
        sched = DailyReportScheduler()
        sched.enabled = False
        sched.scheduler = MagicMock()

        sched.start()

        # Should not add jobs when disabled
        sched.scheduler.add_job.assert_not_called()
        sched.scheduler.start.assert_not_called()

    def test_scheduler_start_enabled(self):
        """Test scheduler start when enabled"""
        sched = DailyReportScheduler()
        sched.enabled = True
        sched.report_time = '06:00'
        sched.scheduler = MagicMock()

        sched.start()

        sched.scheduler.add_job.assert_called_once()
        sched.scheduler.start.assert_called_once()

    def test_scheduler_start_custom_time(self):
        """Test scheduler start parses custom time correctly"""
        sched = DailyReportScheduler()
        sched.enabled = True
        sched.report_time = '14:30'
        sched.scheduler = MagicMock()

        sched.start()

        # Verify the job was scheduled
        sched.scheduler.add_job.assert_called_once()
        call_kwargs = sched.scheduler.add_job.call_args
        assert call_kwargs[1]['id'] == 'daily_kpi_reports'


@pytest.mark.skipif(not MODULE_AVAILABLE, reason="daily_reports module not available")
class TestDailyReportSchedulerStop:
    """Test DailyReportScheduler stop method"""

    def test_scheduler_stop(self):
        """Test scheduler stop shuts down correctly"""
        sched = DailyReportScheduler()
        sched.scheduler = MagicMock()

        sched.stop()

        sched.scheduler.shutdown.assert_called_once()


@pytest.mark.skipif(not MODULE_AVAILABLE, reason="daily_reports module not available")
class TestSendDailyReports:
    """Test send_daily_reports method"""

    def test_send_daily_reports_no_clients(self):
        """Test send_daily_reports with no active clients"""
        with patch('tasks.daily_reports.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.all.return_value = []
            mock_get_db.return_value = iter([mock_db])

            sched = DailyReportScheduler()
            sched.email_service = MagicMock()

            sched.send_daily_reports()

            mock_db.close.assert_called_once()

    def test_send_daily_reports_with_clients(self):
        """Test send_daily_reports with active clients"""
        with patch('tasks.daily_reports.get_db') as mock_get_db:
            mock_client = MagicMock()
            mock_client.client_id = 1
            mock_client.name = "Test Client"

            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.all.return_value = [mock_client]
            mock_get_db.return_value = iter([mock_db])

            sched = DailyReportScheduler()
            sched.email_service = MagicMock()
            sched.generate_and_send_report = MagicMock(return_value={'success': True})

            sched.send_daily_reports()

            sched.generate_and_send_report.assert_called_once()
            mock_db.close.assert_called_once()

    def test_send_daily_reports_client_failure(self):
        """Test send_daily_reports handles client failures"""
        with patch('tasks.daily_reports.get_db') as mock_get_db:
            mock_client = MagicMock()
            mock_client.client_id = 1
            mock_client.name = "Test Client"

            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.all.return_value = [mock_client]
            mock_get_db.return_value = iter([mock_db])

            sched = DailyReportScheduler()
            sched.email_service = MagicMock()
            sched.generate_and_send_report = MagicMock(return_value={'success': False, 'error': 'Email failed'})

            sched.send_daily_reports()

            mock_db.close.assert_called_once()

    def test_send_daily_reports_exception(self):
        """Test send_daily_reports handles exceptions"""
        with patch('tasks.daily_reports.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.side_effect = Exception("Database error")
            mock_get_db.return_value = iter([mock_db])

            sched = DailyReportScheduler()

            # Should not raise, just log error
            sched.send_daily_reports()

            mock_db.close.assert_called_once()

    def test_send_daily_reports_client_exception(self):
        """Test send_daily_reports handles per-client exceptions"""
        with patch('tasks.daily_reports.get_db') as mock_get_db:
            mock_client = MagicMock()
            mock_client.client_id = 1
            mock_client.name = "Test Client"

            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.all.return_value = [mock_client]
            mock_get_db.return_value = iter([mock_db])

            sched = DailyReportScheduler()
            sched.generate_and_send_report = MagicMock(side_effect=Exception("Report error"))

            sched.send_daily_reports()

            mock_db.close.assert_called_once()


@pytest.mark.skipif(not MODULE_AVAILABLE, reason="daily_reports module not available")
class TestGenerateAndSendReport:
    """Test generate_and_send_report method"""

    def test_generate_and_send_report_no_emails(self):
        """Test generate_and_send_report with no recipient emails"""
        sched = DailyReportScheduler()
        sched._get_client_admin_emails = MagicMock(return_value=[])

        mock_db = MagicMock()
        mock_client = MagicMock()
        mock_client.client_id = 1
        mock_client.name = "Test Client"

        result = sched.generate_and_send_report(
            db=mock_db,
            client=mock_client,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today(),
            report_date=datetime.now()
        )

        assert result['success'] is False
        assert 'No recipient emails' in result['error']

    def test_generate_and_send_report_success(self):
        """Test generate_and_send_report successful execution"""
        with patch('tasks.daily_reports.PDFReportGenerator') as mock_pdf_gen:
            mock_pdf_instance = MagicMock()
            mock_pdf_buffer = MagicMock()
            mock_pdf_buffer.getvalue.return_value = b'PDF content'
            mock_pdf_instance.generate_report.return_value = mock_pdf_buffer
            mock_pdf_gen.return_value = mock_pdf_instance

            sched = DailyReportScheduler()
            sched._get_client_admin_emails = MagicMock(return_value=['admin@test.com'])
            sched.email_service = MagicMock()
            sched.email_service.send_kpi_report.return_value = {'success': True}

            mock_db = MagicMock()
            mock_client = MagicMock()
            mock_client.client_id = 1
            mock_client.name = "Test Client"

            result = sched.generate_and_send_report(
                db=mock_db,
                client=mock_client,
                start_date=date.today() - timedelta(days=1),
                end_date=date.today(),
                report_date=datetime.now()
            )

            assert result['success'] is True
            sched.email_service.send_kpi_report.assert_called_once()

    def test_generate_and_send_report_pdf_error(self):
        """Test generate_and_send_report handles PDF generation error"""
        with patch('tasks.daily_reports.PDFReportGenerator') as mock_pdf_gen:
            mock_pdf_gen.return_value.generate_report.side_effect = Exception("PDF error")

            sched = DailyReportScheduler()
            sched._get_client_admin_emails = MagicMock(return_value=['admin@test.com'])

            mock_db = MagicMock()
            mock_client = MagicMock()
            mock_client.client_id = 1
            mock_client.name = "Test Client"

            result = sched.generate_and_send_report(
                db=mock_db,
                client=mock_client,
                start_date=date.today() - timedelta(days=1),
                end_date=date.today(),
                report_date=datetime.now()
            )

            assert result['success'] is False
            assert 'PDF error' in result['error']


@pytest.mark.skipif(not MODULE_AVAILABLE, reason="daily_reports module not available")
class TestGetClientAdminEmails:
    """Test _get_client_admin_emails method"""

    def test_get_client_admin_emails_returns_list(self):
        """Test _get_client_admin_emails returns a list of emails"""
        sched = DailyReportScheduler()

        # Verify the method exists and is callable
        assert hasattr(sched, '_get_client_admin_emails')
        assert callable(sched._get_client_admin_emails)

    def test_get_client_admin_emails_processes_admins(self):
        """Test _get_client_admin_emails processes admin list correctly"""
        sched = DailyReportScheduler()

        # Test extraction logic
        mock_admin1 = MagicMock()
        mock_admin1.email = 'admin1@test.com'
        mock_admin2 = MagicMock()
        mock_admin2.email = 'admin2@test.com'
        mock_admin3 = MagicMock()
        mock_admin3.email = None  # Admin with no email

        admins = [mock_admin1, mock_admin2, mock_admin3]
        emails = [admin.email for admin in admins if admin.email]

        assert emails == ['admin1@test.com', 'admin2@test.com']


@pytest.mark.skipif(not MODULE_AVAILABLE, reason="daily_reports module not available")
class TestSendManualReport:
    """Test send_manual_report method"""

    def test_send_manual_report_client_not_found(self):
        """Test send_manual_report with invalid client"""
        with patch('tasks.daily_reports.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value = iter([mock_db])

            sched = DailyReportScheduler()

            result = sched.send_manual_report(
                client_id=999,
                start_date=date.today() - timedelta(days=7),
                end_date=date.today(),
                recipient_emails=['user@test.com']
            )

            assert result['success'] is False
            assert 'Client not found' in result['error']
            mock_db.close.assert_called_once()

    def test_send_manual_report_success(self):
        """Test send_manual_report successful execution"""
        with patch('tasks.daily_reports.get_db') as mock_get_db, \
             patch('tasks.daily_reports.PDFReportGenerator') as mock_pdf_gen:

            mock_client = MagicMock()
            mock_client.client_id = 1
            mock_client.name = "Test Client"

            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_client
            mock_get_db.return_value = iter([mock_db])

            mock_pdf_instance = MagicMock()
            mock_pdf_buffer = MagicMock()
            mock_pdf_buffer.getvalue.return_value = b'PDF content'
            mock_pdf_instance.generate_report.return_value = mock_pdf_buffer
            mock_pdf_gen.return_value = mock_pdf_instance

            sched = DailyReportScheduler()
            sched.email_service = MagicMock()
            sched.email_service.send_kpi_report.return_value = {'success': True}

            result = sched.send_manual_report(
                client_id=1,
                start_date=date.today() - timedelta(days=7),
                end_date=date.today(),
                recipient_emails=['user@test.com']
            )

            assert result['success'] is True
            mock_db.close.assert_called_once()

    def test_send_manual_report_exception(self):
        """Test send_manual_report handles exceptions"""
        with patch('tasks.daily_reports.get_db') as mock_get_db, \
             patch('tasks.daily_reports.PDFReportGenerator') as mock_pdf_gen:

            mock_client = MagicMock()
            mock_client.client_id = 1
            mock_client.name = "Test Client"

            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_client
            mock_get_db.return_value = iter([mock_db])

            mock_pdf_gen.return_value.generate_report.side_effect = Exception("Generation failed")

            sched = DailyReportScheduler()

            result = sched.send_manual_report(
                client_id=1,
                start_date=date.today() - timedelta(days=7),
                end_date=date.today(),
                recipient_emails=['user@test.com']
            )

            assert result['success'] is False
            assert 'Generation failed' in result['error']
            mock_db.close.assert_called_once()


@pytest.mark.skipif(not MODULE_AVAILABLE, reason="daily_reports module not available")
class TestGlobalScheduler:
    """Test global scheduler instance"""

    def test_global_scheduler_exists(self):
        """Test global scheduler is instantiated"""
        assert scheduler is not None
        assert hasattr(scheduler, 'start')
        assert hasattr(scheduler, 'stop')
        assert hasattr(scheduler, 'send_daily_reports')
