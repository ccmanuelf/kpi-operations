"""Guards that the report generators use real availability, not placeholders."""

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import pytest

from backend.reports.excel_generator import ExcelReportGenerator
from backend.reports.pdf_generator import PDFReportGenerator
from backend.tests.fixtures.factories import TestDataFactory

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"


class TestNoPlaceholderAvailability:
    def test_excel_generator_has_no_hardcoded_availability(self):
        src = (REPORTS_DIR / "excel_generator.py").read_text()
        assert '"availability": 90.0' not in src
        assert "calculate_availability_pure" in src

    def test_pdf_generator_has_no_hardcoded_availability(self):
        src = (REPORTS_DIR / "pdf_generator.py").read_text()
        assert "[85.0] * len" not in src
        assert "calculate_availability_pure" in src


def _seed_production_entry(
    db, *, run_time_hours: Decimal, downtime_hours: Decimal, entry_date: date, entry_time: time = time(18, 0)
):
    """Insert one ProductionEntry with known run/downtime hours through real FKs,
    timestamped late in the day (18:00 by default) on entry_date rather than
    midnight. Combined with querying start_date == end_date == entry_date, this
    exercises the DateTime-vs-date upper-bound boundary case (#145 pattern)."""
    client = TestDataFactory.create_client(db)
    user = TestDataFactory.create_user(db, role="admin", client_id=client.client_id)
    product = TestDataFactory.create_product(db, client_id=client.client_id)
    shift = TestDataFactory.create_shift(db, client_id=client.client_id)
    entry = TestDataFactory.create_production_entry(
        db,
        client_id=client.client_id,
        product_id=product.product_id,
        shift_id=shift.shift_id,
        entered_by=user.user_id,
        production_date=entry_date,
        run_time_hours=run_time_hours,
        downtime_hours=downtime_hours,
    )
    entry.production_date = datetime.combine(entry_date, entry_time)
    db.flush()
    return client


class TestAvailabilityValueEquality:
    """Spec §7: feed known run/downtime hours through the REAL fetch path and
    assert the emitted availability figure exactly. run=7h + downtime=1h ->
    scheduled=8h -> availability == 87.5, per calculate_availability_pure's
    (scheduled - downtime) / scheduled * 100 formula.

    The fixture entry is timestamped 18:00 on entry_date and queried with
    start_date == end_date == entry_date — the DateTime-vs-date upper-bound
    boundary case fixed in this change (the #145 `datetime.combine(start_date,
    datetime.min.time())` / `datetime.combine(end_date, datetime.max.time())`
    pattern, applied to every `_fetch_*` method in both generators). An entry
    timestamped anywhere on end_date, not just midnight, must be included.
    """

    def test_excel_fetch_production_data_availability_is_exact(self, transactional_db):
        entry_date = date(2026, 1, 15)
        client = _seed_production_entry(
            transactional_db,
            run_time_hours=Decimal("7.0"),
            downtime_hours=Decimal("1.0"),
            entry_date=entry_date,
        )

        rows = ExcelReportGenerator(transactional_db)._fetch_production_data(client.client_id, entry_date, entry_date)

        assert len(rows) == 1
        assert rows[0]["availability"] == 87.5

    def test_pdf_fetch_kpi_details_availability_is_exact(self, transactional_db):
        entry_date = date(2026, 1, 15)
        client = _seed_production_entry(
            transactional_db,
            run_time_hours=Decimal("7.0"),
            downtime_hours=Decimal("1.0"),
            entry_date=entry_date,
        )

        details = PDFReportGenerator(transactional_db)._fetch_kpi_details(
            "availability", client.client_id, entry_date, entry_date
        )

        assert details["Current Value"] == "87.5%"
        assert details["Average (Period)"] == "87.5%"
        assert details["Best Day"] == "87.5%"
        assert details["Worst Day"] == "87.5%"


class TestExcelGeneratorEmptySheetSelectionGuard:
    """M-4: an empty (or all-unknown-key) sheet selection must fail loudly,
    not silently produce a zero-sheet workbook that crashes openpyxl on save.
    """

    def test_empty_sheet_selection_raises_value_error(self, transactional_db):
        generator = ExcelReportGenerator(transactional_db)

        with pytest.raises(ValueError, match="sheets selected no valid sheet keys"):
            generator.generate_report(
                client_id=None,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
                sheets=["not-a-real-sheet-key"],
            )
