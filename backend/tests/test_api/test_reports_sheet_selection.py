"""Characterization tests: Excel report sheets per report type (honest-surface PR)."""

from io import BytesIO

from openpyxl import load_workbook


def _sheets(test_client, auth_headers, report_type: str) -> list[str]:
    response = test_client.get(f"/api/reports/{report_type}/excel", headers=auth_headers)
    assert response.status_code == 200
    return list(load_workbook(BytesIO(response.content)).sheetnames)


class TestComprehensiveSheets:
    def test_comprehensive_has_all_data_sheets_and_no_charts(self, test_client, auth_headers):
        assert _sheets(test_client, auth_headers, "comprehensive") == [
            "Executive Summary",
            "Production Metrics",
            "Quality Metrics",
            "Downtime Analysis",
            "Attendance",
        ]
