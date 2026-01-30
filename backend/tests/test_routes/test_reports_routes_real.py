"""
Reports Routes Tests with Real Database Integration
Target: Increase routes/reports.py coverage to 75%+
"""
import pytest
from io import BytesIO
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.schemas import ClientType
from backend.routes.reports import router as reports_router
from backend.tests.fixtures.factories import TestDataFactory


def create_test_app(db_session):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(reports_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="function")
def reports_db():
    """Create a fresh database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    TestDataFactory.reset_counters()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def reports_setup(reports_db):
    """Create standard test data for reports tests."""
    db = reports_db

    # Create client
    client = TestDataFactory.create_client(
        db,
        client_id="REPORT-TEST-CLIENT",
        client_name="Reports Test Client",
        client_type=ClientType.HOURLY_RATE
    )

    # Create users
    admin = TestDataFactory.create_user(
        db,
        user_id="rpt-admin-001",
        username="rpt_admin",
        role="admin",
        client_id=None
    )

    supervisor = TestDataFactory.create_user(
        db,
        user_id="rpt-super-001",
        username="rpt_supervisor",
        role="supervisor",
        client_id=client.client_id
    )

    # Create product
    product = TestDataFactory.create_product(
        db,
        product_code="RPT-PROD-001",
        product_name="Reports Test Product",
        ideal_cycle_time=Decimal("0.10")
    )

    # Create shift
    shift = TestDataFactory.create_shift(
        db,
        shift_name="Reports Test Shift",
        start_time="06:00:00",
        end_time="14:00:00"
    )

    db.commit()

    return {
        "db": db,
        "client": client,
        "admin": admin,
        "supervisor": supervisor,
        "product": product,
        "shift": shift,
    }


@pytest.fixture
def admin_client(reports_setup):
    """Create an admin test client."""
    db = reports_setup["db"]
    user = reports_setup["admin"]
    app = create_test_app(db)

    from backend.auth.jwt import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user

    return TestClient(app), reports_setup


@pytest.fixture
def supervisor_client(reports_setup):
    """Create a supervisor test client."""
    db = reports_setup["db"]
    user = reports_setup["supervisor"]
    app = create_test_app(db)

    from backend.auth.jwt import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user

    return TestClient(app), reports_setup


class TestAvailableReports:
    """Tests for available reports endpoint."""

    def test_get_available_reports(self, supervisor_client):
        """Test getting available report types."""
        client, setup = supervisor_client

        response = client.get("/api/reports/available")

        assert response.status_code == 200
        data = response.json()
        assert "reports" in data
        assert len(data["reports"]) > 0
        # Check structure of first report type
        first_type = data["reports"][0]
        assert "type" in first_type
        assert "name" in first_type
        assert "description" in first_type
        assert "formats" in first_type
        # Check query parameters info
        assert "query_parameters" in data
        # Check features list
        assert "features" in data


class TestEmailConfiguration:
    """Tests for email configuration routes."""

    def test_get_email_config_default(self, supervisor_client):
        """Test getting default email configuration."""
        client, setup = supervisor_client

        response = client.get("/api/reports/email-config")

        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert "frequency" in data
        assert "recipients" in data
        assert data["enabled"] is False  # Default

    def test_get_email_config_with_client_id(self, admin_client):
        """Test getting email config for specific client."""
        client, setup = admin_client
        client_id = setup["client"].client_id

        response = client.get(f"/api/reports/email-config?client_id={client_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["client_id"] == client_id

    def test_save_email_config_success(self, supervisor_client):
        """Test saving email configuration."""
        client, setup = supervisor_client
        client_id = setup["client"].client_id

        response = client.post(
            "/api/reports/email-config",
            json={
                "enabled": True,
                "frequency": "daily",
                "report_time": "06:00",
                "recipients": ["test@example.com"],
                "client_id": client_id,
                "include_executive_summary": True,
                "include_efficiency": True,
                "include_quality": True,
                "include_availability": True,
                "include_attendance": True,
                "include_predictions": True
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["frequency"] == "daily"
        assert len(data["recipients"]) == 1

    def test_save_email_config_no_recipients_when_enabled(self, supervisor_client):
        """Test error when enabling without recipients."""
        client, setup = supervisor_client

        response = client.post(
            "/api/reports/email-config",
            json={
                "enabled": True,
                "frequency": "daily",
                "recipients": [],  # Empty but enabled
            }
        )

        assert response.status_code == 400
        assert "recipient" in response.json()["detail"].lower()

    def test_save_email_config_invalid_frequency(self, supervisor_client):
        """Test error with invalid frequency."""
        client, setup = supervisor_client

        response = client.post(
            "/api/reports/email-config",
            json={
                "enabled": False,
                "frequency": "invalid_frequency",
                "recipients": []
            }
        )

        assert response.status_code == 400
        assert "frequency" in response.json()["detail"].lower()

    def test_save_email_config_weekly(self, supervisor_client):
        """Test saving weekly email configuration."""
        client, setup = supervisor_client
        client_id = setup["client"].client_id

        response = client.post(
            "/api/reports/email-config",
            json={
                "enabled": True,
                "frequency": "weekly",
                "report_time": "08:00",
                "recipients": ["weekly@example.com"],
                "client_id": client_id,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["frequency"] == "weekly"

    def test_update_email_config_not_found(self, supervisor_client):
        """Test updating non-existent config."""
        client, setup = supervisor_client

        # Try to PUT without creating first
        response = client.put(
            "/api/reports/email-config",
            json={
                "enabled": False,
                "frequency": "daily",
                "recipients": [],
                "client_id": "non-existent-client"
            }
        )

        assert response.status_code == 404

    def test_update_email_config_success(self, supervisor_client):
        """Test updating existing email configuration."""
        client, setup = supervisor_client
        client_id = setup["client"].client_id

        # First create
        client.post(
            "/api/reports/email-config",
            json={
                "enabled": True,
                "frequency": "daily",
                "recipients": ["test@example.com"],
                "client_id": client_id,
            }
        )

        # Then update
        response = client.put(
            "/api/reports/email-config",
            json={
                "enabled": True,
                "frequency": "monthly",
                "recipients": ["updated@example.com"],
                "client_id": client_id,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["frequency"] == "monthly"


class TestTestEmail:
    """Tests for test email endpoint."""

    @pytest.mark.skip(reason="Test email endpoint throws 500 in test environment (EmailService not available)")
    def test_send_test_email(self, supervisor_client):
        """Test sending a test email."""
        client, setup = supervisor_client

        response = client.post(
            "/api/reports/email-config/test",
            json={"email": "test@example.com"}
        )

        # Accept 200 or 500 (email service may not be configured)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is True
            assert "test@example.com" in data["message"]


class TestPDFReportGeneration:
    """Tests for PDF report generation."""

    def test_production_pdf_invalid_date_format(self, supervisor_client):
        """Test error with invalid date format."""
        client, setup = supervisor_client

        response = client.get(
            "/api/reports/production/pdf?start_date=invalid-date"
        )

        assert response.status_code == 400
        assert "date" in response.json()["detail"].lower()

    def test_production_pdf_start_after_end(self, supervisor_client):
        """Test error when start date is after end date."""
        client, setup = supervisor_client
        end = date.today() - timedelta(days=30)
        start = date.today()

        response = client.get(
            f"/api/reports/production/pdf?start_date={start}&end_date={end}"
        )

        assert response.status_code == 400
        assert "before" in response.json()["detail"].lower()


class TestExcelReportGeneration:
    """Tests for Excel report generation."""

    def test_production_excel_invalid_date(self, supervisor_client):
        """Test error with invalid date format."""
        client, setup = supervisor_client

        response = client.get(
            "/api/reports/production/excel?start_date=not-a-date"
        )

        assert response.status_code == 400


class TestQualityReports:
    """Tests for quality report generation."""

    def test_quality_pdf_invalid_date(self, supervisor_client):
        """Test quality PDF with invalid date."""
        client, setup = supervisor_client

        response = client.get(
            "/api/reports/quality/pdf?start_date=wrong"
        )

        assert response.status_code == 400


class TestAttendanceReports:
    """Tests for attendance report generation."""

    def test_attendance_pdf_invalid_date(self, supervisor_client):
        """Test attendance PDF with invalid date."""
        client, setup = supervisor_client

        response = client.get(
            "/api/reports/attendance/pdf?start_date=2024-13-01"  # Invalid month
        )

        assert response.status_code == 400


class TestManualReport:
    """Tests for manual report sending."""

    def test_send_manual_report_invalid_date(self, supervisor_client):
        """Test manual report with invalid date."""
        client, setup = supervisor_client
        client_id = setup["client"].client_id

        response = client.post(
            "/api/reports/send-manual",
            json={
                "client_id": client_id,
                "start_date": "invalid-date",
                "end_date": "2024-01-31",
                "recipient_emails": ["test@example.com"]
            }
        )

        assert response.status_code == 400

    def test_send_manual_report_start_after_end(self, supervisor_client):
        """Test manual report with start date after end date."""
        client, setup = supervisor_client
        client_id = setup["client"].client_id

        response = client.post(
            "/api/reports/send-manual",
            json={
                "client_id": client_id,
                "start_date": "2024-12-31",
                "end_date": "2024-01-01",
                "recipient_emails": ["test@example.com"]
            }
        )

        assert response.status_code == 400
        assert "before" in response.json()["detail"].lower()


# =============================================================================
# Mocked PDF/Excel Generation Tests
# =============================================================================

class TestProductionPDFWithMock:
    """Tests for production PDF generation with mocked generator."""

    @patch("backend.routes.reports.PDFReportGenerator")
    def test_production_pdf_success(self, mock_pdf_class, supervisor_client):
        """Test successful production PDF generation."""
        client, setup = supervisor_client
        client_id = setup["client"].client_id

        # Setup mock
        mock_generator = MagicMock()
        mock_generator.generate_report.return_value = BytesIO(b"%PDF-1.4 mock content")
        mock_pdf_class.return_value = mock_generator

        start = (date.today() - timedelta(days=7)).isoformat()
        end = date.today().isoformat()

        response = client.get(
            f"/api/reports/production/pdf?client_id={client_id}&start_date={start}&end_date={end}"
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert "production_report" in response.headers["content-disposition"]

    @patch("backend.routes.reports.PDFReportGenerator")
    def test_production_pdf_all_clients(self, mock_pdf_class, supervisor_client):
        """Test production PDF for all clients (admin)."""
        client, setup = supervisor_client

        mock_generator = MagicMock()
        mock_generator.generate_report.return_value = BytesIO(b"%PDF-1.4 content")
        mock_pdf_class.return_value = mock_generator

        response = client.get("/api/reports/production/pdf")

        assert response.status_code == 200
        assert "all_clients" in response.headers["content-disposition"]

    @patch("backend.routes.reports.PDFReportGenerator")
    def test_production_pdf_generator_error(self, mock_pdf_class, supervisor_client):
        """Test PDF generation error handling."""
        client, setup = supervisor_client

        mock_generator = MagicMock()
        mock_generator.generate_report.side_effect = Exception("PDF generation failed")
        mock_pdf_class.return_value = mock_generator

        response = client.get("/api/reports/production/pdf")

        assert response.status_code == 500
        assert "error" in response.json()["detail"].lower()


class TestProductionExcelWithMock:
    """Tests for production Excel generation with mocked generator."""

    @patch("backend.routes.reports.ExcelReportGenerator")
    def test_production_excel_success(self, mock_excel_class, supervisor_client):
        """Test successful production Excel generation."""
        client, setup = supervisor_client
        client_id = setup["client"].client_id

        mock_generator = MagicMock()
        mock_generator.generate_report.return_value = BytesIO(b"PK mock xlsx content")
        mock_excel_class.return_value = mock_generator

        start = (date.today() - timedelta(days=7)).isoformat()
        end = date.today().isoformat()

        response = client.get(
            f"/api/reports/production/excel?client_id={client_id}&start_date={start}&end_date={end}"
        )

        assert response.status_code == 200
        assert "spreadsheetml" in response.headers["content-type"]
        assert ".xlsx" in response.headers["content-disposition"]

    @patch("backend.routes.reports.ExcelReportGenerator")
    def test_production_excel_generator_error(self, mock_excel_class, supervisor_client):
        """Test Excel generation error handling."""
        client, setup = supervisor_client

        mock_generator = MagicMock()
        mock_generator.generate_report.side_effect = Exception("Excel generation failed")
        mock_excel_class.return_value = mock_generator

        response = client.get("/api/reports/production/excel")

        assert response.status_code == 500
        assert "error" in response.json()["detail"].lower()


class TestQualityPDFWithMock:
    """Tests for quality PDF generation with mocked generator."""

    @patch("backend.routes.reports.PDFReportGenerator")
    def test_quality_pdf_success(self, mock_pdf_class, supervisor_client):
        """Test successful quality PDF generation."""
        client, setup = supervisor_client

        mock_generator = MagicMock()
        mock_generator.generate_report.return_value = BytesIO(b"%PDF-1.4 quality report")
        mock_pdf_class.return_value = mock_generator

        response = client.get("/api/reports/quality/pdf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "quality_report" in response.headers["content-disposition"]

    @patch("backend.routes.reports.PDFReportGenerator")
    def test_quality_pdf_with_client(self, mock_pdf_class, supervisor_client):
        """Test quality PDF for specific client."""
        client, setup = supervisor_client
        client_id = setup["client"].client_id

        mock_generator = MagicMock()
        mock_generator.generate_report.return_value = BytesIO(b"%PDF-1.4 content")
        mock_pdf_class.return_value = mock_generator

        response = client.get(f"/api/reports/quality/pdf?client_id={client_id}")

        assert response.status_code == 200
        assert client_id in response.headers["content-disposition"]


class TestQualityExcelWithMock:
    """Tests for quality Excel generation with mocked generator."""

    @patch("backend.routes.reports.ExcelReportGenerator")
    def test_quality_excel_success(self, mock_excel_class, supervisor_client):
        """Test successful quality Excel generation."""
        client, setup = supervisor_client

        mock_generator = MagicMock()
        mock_generator.generate_report.return_value = BytesIO(b"PK xlsx content")
        mock_excel_class.return_value = mock_generator

        response = client.get("/api/reports/quality/excel")

        assert response.status_code == 200
        assert "spreadsheetml" in response.headers["content-type"]
        assert "quality_report" in response.headers["content-disposition"]


class TestAttendancePDFWithMock:
    """Tests for attendance PDF generation with mocked generator."""

    @patch("backend.routes.reports.PDFReportGenerator")
    def test_attendance_pdf_success(self, mock_pdf_class, supervisor_client):
        """Test successful attendance PDF generation."""
        client, setup = supervisor_client

        mock_generator = MagicMock()
        mock_generator.generate_report.return_value = BytesIO(b"%PDF-1.4 attendance report")
        mock_pdf_class.return_value = mock_generator

        response = client.get("/api/reports/attendance/pdf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attendance_report" in response.headers["content-disposition"]

    @patch("backend.routes.reports.PDFReportGenerator")
    def test_attendance_pdf_date_range(self, mock_pdf_class, supervisor_client):
        """Test attendance PDF with date range."""
        client, setup = supervisor_client

        mock_generator = MagicMock()
        mock_generator.generate_report.return_value = BytesIO(b"%PDF content")
        mock_pdf_class.return_value = mock_generator

        start = (date.today() - timedelta(days=30)).isoformat()
        end = date.today().isoformat()

        response = client.get(f"/api/reports/attendance/pdf?start_date={start}&end_date={end}")

        assert response.status_code == 200
        # Verify the generator was called with correct parameters
        mock_generator.generate_report.assert_called_once()


class TestAttendanceExcelWithMock:
    """Tests for attendance Excel generation with mocked generator."""

    @patch("backend.routes.reports.ExcelReportGenerator")
    def test_attendance_excel_success(self, mock_excel_class, supervisor_client):
        """Test successful attendance Excel generation."""
        client, setup = supervisor_client

        mock_generator = MagicMock()
        mock_generator.generate_report.return_value = BytesIO(b"PK xlsx content")
        mock_excel_class.return_value = mock_generator

        response = client.get("/api/reports/attendance/excel")

        assert response.status_code == 200
        assert "spreadsheetml" in response.headers["content-type"]
        assert "attendance_report" in response.headers["content-disposition"]

    @patch("backend.routes.reports.ExcelReportGenerator")
    def test_attendance_excel_start_after_end(self, mock_excel_class, supervisor_client):
        """Test attendance Excel with invalid date range."""
        client, setup = supervisor_client
        end = date.today() - timedelta(days=30)
        start = date.today()

        response = client.get(
            f"/api/reports/attendance/excel?start_date={start}&end_date={end}"
        )

        assert response.status_code == 400
        assert "before" in response.json()["detail"].lower()


class TestMonthlyFrequencyConfig:
    """Tests for monthly email configuration."""

    def test_save_email_config_monthly(self, supervisor_client):
        """Test saving monthly email configuration."""
        client, setup = supervisor_client
        client_id = setup["client"].client_id

        response = client.post(
            "/api/reports/email-config",
            json={
                "enabled": True,
                "frequency": "monthly",
                "report_time": "09:00",
                "recipients": ["monthly@example.com"],
                "client_id": client_id,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["frequency"] == "monthly"

    def test_email_config_disabled_no_recipients_ok(self, supervisor_client):
        """Test that disabled config can have empty recipients."""
        client, setup = supervisor_client

        response = client.post(
            "/api/reports/email-config",
            json={
                "enabled": False,
                "frequency": "daily",
                "recipients": []  # Empty is OK when disabled
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["recipients"] == []


class TestComprehensivePDFWithMock:
    """Tests for comprehensive PDF generation with mocked generator."""

    @patch("backend.routes.reports.PDFReportGenerator")
    def test_comprehensive_pdf_success(self, mock_pdf_class, supervisor_client):
        """Test successful comprehensive PDF generation."""
        client, setup = supervisor_client

        mock_generator = MagicMock()
        mock_generator.generate_report.return_value = BytesIO(b"%PDF-1.4 comprehensive")
        mock_pdf_class.return_value = mock_generator

        response = client.get("/api/reports/comprehensive/pdf")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "comprehensive_report" in response.headers["content-disposition"]

    @patch("backend.routes.reports.PDFReportGenerator")
    def test_comprehensive_pdf_with_client(self, mock_pdf_class, supervisor_client):
        """Test comprehensive PDF for specific client."""
        client, setup = supervisor_client
        client_id = setup["client"].client_id

        mock_generator = MagicMock()
        mock_generator.generate_report.return_value = BytesIO(b"%PDF content")
        mock_pdf_class.return_value = mock_generator

        response = client.get(f"/api/reports/comprehensive/pdf?client_id={client_id}")

        assert response.status_code == 200
        assert client_id in response.headers["content-disposition"]


class TestComprehensiveExcelWithMock:
    """Tests for comprehensive Excel generation with mocked generator."""

    @patch("backend.routes.reports.ExcelReportGenerator")
    def test_comprehensive_excel_success(self, mock_excel_class, supervisor_client):
        """Test successful comprehensive Excel generation."""
        client, setup = supervisor_client

        mock_generator = MagicMock()
        mock_generator.generate_report.return_value = BytesIO(b"PK xlsx")
        mock_excel_class.return_value = mock_generator

        response = client.get("/api/reports/comprehensive/excel")

        assert response.status_code == 200
        assert "spreadsheetml" in response.headers["content-type"]
        assert "comprehensive_report" in response.headers["content-disposition"]

    @patch("backend.routes.reports.ExcelReportGenerator")
    def test_comprehensive_excel_invalid_date_range(self, mock_excel_class, supervisor_client):
        """Test comprehensive Excel with invalid date range."""
        client, setup = supervisor_client

        end = date.today() - timedelta(days=30)
        start = date.today()

        response = client.get(
            f"/api/reports/comprehensive/excel?start_date={start}&end_date={end}"
        )

        assert response.status_code == 400
        assert "before" in response.json()["detail"].lower()


class TestQualityExcelValidation:
    """Tests for quality Excel validation."""

    def test_quality_excel_invalid_date(self, supervisor_client):
        """Test quality Excel with invalid date."""
        client, setup = supervisor_client

        response = client.get("/api/reports/quality/excel?start_date=bad-date")

        assert response.status_code == 400

    def test_quality_excel_start_after_end(self, supervisor_client):
        """Test quality Excel with start after end."""
        client, setup = supervisor_client
        end = date.today() - timedelta(days=30)
        start = date.today()

        response = client.get(
            f"/api/reports/quality/excel?start_date={start}&end_date={end}"
        )

        assert response.status_code == 400

    @patch("backend.routes.reports.ExcelReportGenerator")
    def test_quality_excel_error_handling(self, mock_excel_class, supervisor_client):
        """Test quality Excel error handling."""
        client, setup = supervisor_client

        mock_generator = MagicMock()
        mock_generator.generate_report.side_effect = Exception("Excel error")
        mock_excel_class.return_value = mock_generator

        response = client.get("/api/reports/quality/excel")

        assert response.status_code == 500


class TestAttendanceErrorHandling:
    """Tests for attendance report error handling."""

    @patch("backend.routes.reports.PDFReportGenerator")
    def test_attendance_pdf_error_handling(self, mock_pdf_class, supervisor_client):
        """Test attendance PDF error handling."""
        client, setup = supervisor_client

        mock_generator = MagicMock()
        mock_generator.generate_report.side_effect = Exception("PDF error")
        mock_pdf_class.return_value = mock_generator

        response = client.get("/api/reports/attendance/pdf")

        assert response.status_code == 500

    @patch("backend.routes.reports.ExcelReportGenerator")
    def test_attendance_excel_error_handling(self, mock_excel_class, supervisor_client):
        """Test attendance Excel error handling."""
        client, setup = supervisor_client

        mock_generator = MagicMock()
        mock_generator.generate_report.side_effect = Exception("Excel error")
        mock_excel_class.return_value = mock_generator

        response = client.get("/api/reports/attendance/excel")

        assert response.status_code == 500
