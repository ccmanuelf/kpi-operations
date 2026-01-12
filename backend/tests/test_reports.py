"""
Test Report Generation Endpoints
Run with: pytest backend/tests/test_reports.py -v

Uses shared auth_headers fixture from conftest.py
"""
import pytest
from datetime import date, timedelta


# auth_headers and test_client fixtures are provided by conftest.py


class TestReportEndpoints:
    """Test report generation endpoints"""

    def test_get_available_reports(self, test_client, auth_headers):
        """Test /api/reports/available endpoint"""
        response = test_client.get("/api/reports/available", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "reports" in data
        assert len(data["reports"]) == 4  # production, quality, attendance, comprehensive
        assert "query_parameters" in data
        assert "features" in data

        # Verify report types
        report_types = [r["type"] for r in data["reports"]]
        assert "production" in report_types
        assert "quality" in report_types
        assert "attendance" in report_types
        assert "comprehensive" in report_types

    def test_generate_production_pdf(self, test_client, auth_headers):
        """Test production PDF report generation"""
        start_date = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = date.today().strftime("%Y-%m-%d")

        response = test_client.get(
            f"/api/reports/production/pdf?start_date={start_date}&end_date={end_date}",
            headers=auth_headers
        )

        if response.status_code != 200:
            print(f"ERROR RESPONSE: {response.text}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "Content-Disposition" in response.headers
        assert "production_report" in response.headers["Content-Disposition"]
        assert "X-Report-Type" in response.headers
        assert response.headers["X-Report-Type"] == "production"

    def test_generate_production_excel(self, test_client, auth_headers):
        """Test production Excel report generation"""
        start_date = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = date.today().strftime("%Y-%m-%d")

        response = test_client.get(
            f"/api/reports/production/excel?start_date={start_date}&end_date={end_date}",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "spreadsheetml.sheet" in response.headers["content-type"]
        assert "Content-Disposition" in response.headers
        assert ".xlsx" in response.headers["Content-Disposition"]
        assert "X-Report-Type" in response.headers

    def test_generate_quality_pdf(self, test_client, auth_headers):
        """Test quality PDF report generation"""
        response = test_client.get(
            "/api/reports/quality/pdf",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["X-Report-Type"] == "quality"

    def test_generate_quality_excel(self, test_client, auth_headers):
        """Test quality Excel report generation"""
        response = test_client.get(
            "/api/reports/quality/excel",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "spreadsheetml.sheet" in response.headers["content-type"]

    def test_generate_attendance_pdf(self, test_client, auth_headers):
        """Test attendance PDF report generation"""
        response = test_client.get(
            "/api/reports/attendance/pdf",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["X-Report-Type"] == "attendance"

    def test_generate_attendance_excel(self, test_client, auth_headers):
        """Test attendance Excel report generation"""
        response = test_client.get(
            "/api/reports/attendance/excel",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "spreadsheetml.sheet" in response.headers["content-type"]

    def test_generate_comprehensive_pdf(self, test_client, auth_headers):
        """Test comprehensive PDF report generation"""
        response = test_client.get(
            "/api/reports/comprehensive/pdf",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["X-Report-Type"] == "comprehensive"
        assert "X-Generated-By" in response.headers
        assert "X-Generated-At" in response.headers

    def test_generate_comprehensive_excel(self, test_client, auth_headers):
        """Test comprehensive Excel report generation"""
        response = test_client.get(
            "/api/reports/comprehensive/excel",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "spreadsheetml.sheet" in response.headers["content-type"]
        assert response.headers["X-Report-Type"] == "comprehensive"

    def test_invalid_date_format(self, test_client, auth_headers):
        """Test error handling for invalid date format"""
        response = test_client.get(
            "/api/reports/production/pdf?start_date=invalid-date",
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]

    def test_start_date_after_end_date(self, test_client, auth_headers):
        """Test validation for start_date > end_date"""
        start_date = date.today().strftime("%Y-%m-%d")
        end_date = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")

        response = test_client.get(
            f"/api/reports/production/pdf?start_date={start_date}&end_date={end_date}",
            headers=auth_headers
        )

        assert response.status_code == 400
        assert "before end date" in response.json()["detail"].lower()

    def test_client_filtering(self, test_client, auth_headers):
        """Test client_id filtering in reports"""
        response = test_client.get(
            "/api/reports/production/pdf?client_id=TEST_CLIENT",
            headers=auth_headers
        )

        # Debug: print error if not 200
        if response.status_code != 200:
            print(f"ERROR RESPONSE: {response.json()}")

        # Should succeed even if client doesn't have data
        assert response.status_code == 200
        assert "client_TEST_CLIENT" in response.headers["Content-Disposition"]

    def test_authentication_required(self, test_client):
        """Test that authentication is required"""
        response = test_client.get("/api/reports/production/pdf")

        assert response.status_code == 401


class TestReportGenerators:
    """Test report generator classes directly"""

    def test_pdf_generator_import(self):
        """Test PDFReportGenerator can be imported"""
        from reports.pdf_generator import PDFReportGenerator
        assert PDFReportGenerator is not None

    def test_excel_generator_import(self):
        """Test ExcelReportGenerator can be imported"""
        from reports.excel_generator import ExcelReportGenerator
        assert ExcelReportGenerator is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
