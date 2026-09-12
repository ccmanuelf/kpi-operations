"""A measurement nobody recorded must not be reported as a measured zero.

Both generators averaged `float(e.efficiency_percentage or 0)`, which counts a
NULL as a contributing zero. For `efficiency_percentage` and
`performance_percentage` that is every row in every deployment -- nothing in the
application writes those columns, only test fixtures -- so the comprehensive
report printed "0.0% / At Risk / Variance -85.0%" for two headline KPIs. A reader
sees a catastrophe where the truth is an absent measurement.

The generators already draw this distinction elsewhere: the Excel OTD block omits
itself when no orders were delivered, and the labour-hours block when no
attendance rows exist. This extends the same rule to a column that exists but was
never populated, rather than inventing a new convention.

These are PR-B's prerequisite. PR-B implements four more sections from services
with the same shape, so without the rule it would replicate the defect.
"""

from datetime import date
from decimal import Decimal

import pytest

from backend.db.factories import TestDataFactory
from backend.reports.excel_generator import ExcelReportGenerator
from backend.reports.measurements import absence_note, recorded
from backend.reports.pdf_generator import PDFReportGenerator

DAY = date(2026, 6, 11)


class TestRecorded:
    def test_nulls_are_dropped_rather_than_counted_as_zero(self):
        from types import SimpleNamespace

        entries = [SimpleNamespace(x=None), SimpleNamespace(x=Decimal("80")), SimpleNamespace(x=None)]

        assert recorded(entries, "x") == [80.0]

    def test_a_real_zero_is_kept(self):
        # The whole point is telling these apart: a recorded 0 is a measurement.
        from types import SimpleNamespace

        entries = [SimpleNamespace(x=Decimal("0")), SimpleNamespace(x=None)]

        assert recorded(entries, "x") == [0.0]

    def test_an_all_null_column_yields_nothing(self):
        from types import SimpleNamespace

        assert recorded([SimpleNamespace(x=None), SimpleNamespace(x=None)], "x") == []

    def test_a_missing_attribute_is_treated_as_absent(self):
        from types import SimpleNamespace

        assert recorded([SimpleNamespace()], "x") == []

    def test_the_average_is_over_what_was_recorded(self):
        # Partly-populated is the case where `or 0` is most misleading: two
        # entries at 90 with three NULLs averages to 90, not 36.
        from types import SimpleNamespace

        entries = [SimpleNamespace(x=90), SimpleNamespace(x=None), SimpleNamespace(x=90), SimpleNamespace(x=None)]
        values = recorded(entries, "x")

        assert sum(values) / len(values) == 90.0


class TestAbsenceNote:
    def test_it_does_not_blame_the_reader_for_missing_data(self):
        note = absence_note([1, 2, 3], "efficiency_percentage", "Efficiency")

        assert "not recorded" in note["Status"].lower()
        assert "3 production entries" in note["Note"]
        # The generators' generic message is false here and actionable in the
        # wrong direction: the entries WERE entered, and entering more would
        # change nothing.
        assert "ensure data has been entered" not in note["Note"]


@pytest.fixture
def client_with_unmeasured_production(transactional_db):
    """Production entries that exist but carry no efficiency measurement.

    Exactly the live shape: `TestDataFactory.create_production_entry` does not set
    those columns, and neither does anything in the application.
    """
    db = transactional_db
    client = TestDataFactory.create_client(db)
    user = TestDataFactory.create_user(db, client_id=client.client_id)
    shift = TestDataFactory.create_shift(db, client_id=client.client_id)
    product = TestDataFactory.create_product(db, client_id=client.client_id)
    for _ in range(3):
        TestDataFactory.create_production_entry(
            db,
            client_id=client.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            entered_by=user.user_id,
            production_date=DAY,
        )
    db.commit()
    return db, client


class TestTheSummaryOmitsAnUnmeasuredRow:
    def test_the_pdf_omits_efficiency_rather_than_reporting_zero(self, client_with_unmeasured_production):
        db, client = client_with_unmeasured_production

        names = [r["name"] for r in PDFReportGenerator(db)._fetch_kpi_summary(client.client_id, DAY, DAY)]

        assert "Efficiency" not in names, "an unrecorded measurement was reported as a value"
        assert "Performance" not in names

    def test_the_excel_omits_them_too(self, client_with_unmeasured_production):
        db, client = client_with_unmeasured_production

        names = [r["name"] for r in ExcelReportGenerator(db)._fetch_kpi_summary_data(client.client_id, DAY, DAY)]

        assert "Efficiency" not in names
        assert "Performance" not in names

    def test_a_recorded_value_is_still_reported(self, client_with_unmeasured_production):
        # The guard must not suppress real data.
        db, client = client_with_unmeasured_production
        from backend.orm.production_entry import ProductionEntry

        row = db.query(ProductionEntry).filter(ProductionEntry.client_id == client.client_id).first()
        row.efficiency_percentage = Decimal("82.5")
        db.commit()

        rows = PDFReportGenerator(db)._fetch_kpi_summary(client.client_id, DAY, DAY)
        efficiency = next((r for r in rows if r["name"] == "Efficiency"), None)

        assert efficiency is not None, "a recorded measurement must still be reported"
        assert efficiency["value"] == 82.5, "and averaged over what was recorded, not over every entry"

    def test_a_recorded_zero_is_reported_not_suppressed(self, client_with_unmeasured_production):
        # A genuine 0% is a finding, not an absence. The guard must not hide it.
        db, client = client_with_unmeasured_production
        from backend.orm.production_entry import ProductionEntry

        row = db.query(ProductionEntry).filter(ProductionEntry.client_id == client.client_id).first()
        row.efficiency_percentage = Decimal("0")
        db.commit()

        rows = PDFReportGenerator(db)._fetch_kpi_summary(client.client_id, DAY, DAY)
        efficiency = next((r for r in rows if r["name"] == "Efficiency"), None)

        assert efficiency is not None, "a recorded zero must be reported"
        assert efficiency["value"] == 0.0


class TestTheDetailBlockSaysWhatIsActuallyWrong:
    def test_it_does_not_claim_no_data_was_entered(self, client_with_unmeasured_production):
        db, client = client_with_unmeasured_production

        details = PDFReportGenerator(db)._fetch_kpi_details("efficiency", client.client_id, DAY, DAY)

        assert "not recorded" in details["Status"].lower(), details
        assert "3 production entries" in details["Note"], details
        assert "ensure data has been entered" not in str(details), details

    def test_it_no_longer_reports_a_zero_average(self, client_with_unmeasured_production):
        db, client = client_with_unmeasured_production

        details = PDFReportGenerator(db)._fetch_kpi_details("efficiency", client.client_id, DAY, DAY)

        assert "Current Value" not in details, details
        assert "Variance" not in details, details

    def test_availability_is_unaffected(self, client_with_unmeasured_production):
        # Availability is COMPUTED from run_time/downtime rather than read from a
        # stored column, so it must keep rendering.
        db, client = client_with_unmeasured_production

        details = PDFReportGenerator(db)._fetch_kpi_details("availability", client.client_id, DAY, DAY)

        assert "Current Value" in details, details

    def test_a_window_with_no_entries_at_all_still_says_so(self, client_with_unmeasured_production):
        # The pre-existing message is correct for a genuinely empty range, and
        # must not be replaced by the new one.
        db, client = client_with_unmeasured_production

        details = PDFReportGenerator(db)._fetch_kpi_details(
            "efficiency", client.client_id, date(2020, 1, 1), date(2020, 1, 2)
        )

        assert "No data available" in str(details.get("Status", "")), details
