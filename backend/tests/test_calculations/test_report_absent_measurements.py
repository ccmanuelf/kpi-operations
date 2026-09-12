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
        # Caught on the live demo: "a efficiency measurement". Every metric this
        # is used for is vowel-initial, and the string is customer-facing.
        assert " a efficiency" not in note["Note"], note["Note"]
        assert " a availability" not in absence_note([1], "x", "Availability")["Note"]
        # The generators' generic message is false here and actionable in the
        # wrong direction: the entries WERE entered, and entering more would
        # change nothing.
        assert "ensure data has been entered" not in note["Note"]

    def test_the_sentence_reads_correctly_for_every_metric_it_is_used_for(self):
        for label in ("Efficiency", "Performance", "Availability", "OEE"):
            note = absence_note([1, 2], "col", label)
            assert f" a {label.lower()}" not in note["Note"], note["Note"]
            assert label.lower() in note["Note"], note["Note"]


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


class TestTheSummaryDoesNotReportAnUnmeasuredZero:
    """The original defect: 0.0% presented as a measured result.

    These assert the substance -- no zero, no verdict against one -- rather than
    the mechanism. An earlier version asserted the row was OMITTED; the
    cross-model review pointed out that a vanished row is indistinguishable from a
    KPI the report never covered, so the row is now kept with a "Not Recorded"
    status instead. `TestTheAbsenceIsVISIBLEnotOmitted` pins that shape.
    """

    def test_the_pdf_reports_no_value_for_an_unrecorded_measurement(self, client_with_unmeasured_production):
        db, client = client_with_unmeasured_production

        rows = {r["name"]: r for r in PDFReportGenerator(db)._fetch_kpi_summary(client.client_id, DAY, DAY)}

        for name in ("Efficiency", "Performance"):
            assert rows[name]["value"] is None, f"{name} reported an unrecorded measurement as a value"
            assert rows[name]["status"] not in (
                "At Risk",
                "Warning",
                "Critical",
                "Urgent",
            ), f"{name} was judged against a number nobody measured"

    def test_the_excel_does_the_same(self, client_with_unmeasured_production):
        db, client = client_with_unmeasured_production

        rows = {r["name"]: r for r in ExcelReportGenerator(db)._fetch_kpi_summary_data(client.client_id, DAY, DAY)}

        for name in ("Efficiency", "Performance"):
            assert rows[name]["current"] is None, f"{name} reported an unrecorded measurement as a value"

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


class TestTheAbsenceIsVISIBLEnotOmitted:
    """A vanished row is indistinguishable from a KPI the report never covered.

    Raised by the cross-model review, and it contradicts a precedent PR-A set: an
    unconfigured TARGET renders a visible "—" with a "No Target" status rather
    than disappearing. An unrecorded MEASUREMENT gets the same treatment, so a
    reader comparing two periods sees a row change rather than a row vanish.
    """

    def test_the_pdf_keeps_the_row_and_says_not_recorded(self, client_with_unmeasured_production):
        db, client = client_with_unmeasured_production

        rows = PDFReportGenerator(db)._fetch_kpi_summary(client.client_id, DAY, DAY)
        efficiency = next((r for r in rows if r["name"] == "Efficiency"), None)

        assert efficiency is not None, "the row must not vanish"
        assert efficiency["value"] is None
        assert efficiency["status"] == "Not Recorded"

    def test_the_pdf_renders_the_value_as_an_em_dash(self, client_with_unmeasured_production):
        db, client = client_with_unmeasured_production

        elements = PDFReportGenerator(db)._build_executive_summary(client.client_id, DAY, DAY)
        tables = [e for e in elements if hasattr(e, "_cellvalues")]
        flat = [[str(c) for c in row] for row in tables[0]._cellvalues]
        efficiency = next(r for r in flat if r[0] == "Efficiency")

        assert efficiency[1] == "—", efficiency
        assert efficiency[3] == "Not Recorded", efficiency

    def test_excel_keeps_the_row_too_and_is_not_painted_as_an_alarm(self, client_with_unmeasured_production):
        from backend.reports.targets import UNEVALUATED_STATUSES

        db, client = client_with_unmeasured_production
        rows = ExcelReportGenerator(db)._fetch_kpi_summary_data(client.client_id, DAY, DAY)
        efficiency = next((r for r in rows if r["name"] == "Efficiency"), None)

        assert efficiency is not None
        assert efficiency["current"] is None
        assert efficiency["status"] in UNEVALUATED_STATUSES, "an absent measurement must not render as critical"

    def test_excel_writes_no_variance_formula_for_an_unmeasured_row(self, client_with_unmeasured_production):
        # Excel reads a blank cell as 0, so `=B-C` would subtract nothing from
        # nothing and print a confident 0.0 for a row that measured neither side.
        from openpyxl import load_workbook

        db, client = client_with_unmeasured_production
        buf = ExcelReportGenerator(db).generate_report(client_id=client.client_id, start_date=DAY, end_date=DAY)
        ws = load_workbook(buf)["Executive Summary"]

        for row in range(8, ws.max_row + 1):
            if ws[f"A{row}"].value == "Efficiency":
                assert ws[f"B{row}"].value is None, "the value cell must be blank"
                assert ws[f"D{row}"].value is None, f"variance holds {ws[f'D{row}'].value!r}"
                break
        else:
            raise AssertionError("no Efficiency row in the summary sheet")


class TestTheDenominatorIsExposed:
    """A partly-populated column averages over a subset, and it must say so.

    Otherwise a figure drawn from 2 entries looks identical to one drawn from 200,
    and neither is comparable with a period that measured everything. The pivot
    engine exposes exactly this as `excluded_entries`.
    """

    def test_a_partly_measured_period_reports_how_many_contributed(self, client_with_unmeasured_production):
        from backend.orm.production_entry import ProductionEntry

        db, client = client_with_unmeasured_production
        row = db.query(ProductionEntry).filter(ProductionEntry.client_id == client.client_id).first()
        row.efficiency_percentage = Decimal("90.0")
        db.commit()

        details = PDFReportGenerator(db)._fetch_kpi_details("efficiency", client.client_id, DAY, DAY)

        assert details["Entries Measured"] == "1 of 3", details
        assert details["Current Value"] == "90.0%", "averaged over what was recorded, not over all three"

    def test_a_fully_measured_period_says_so_too(self, client_with_unmeasured_production):
        from backend.orm.production_entry import ProductionEntry

        db, client = client_with_unmeasured_production
        for row in db.query(ProductionEntry).filter(ProductionEntry.client_id == client.client_id).all():
            row.efficiency_percentage = Decimal("80.0")
        db.commit()

        details = PDFReportGenerator(db)._fetch_kpi_details("efficiency", client.client_id, DAY, DAY)

        assert details["Entries Measured"] == "3 of 3", details


class TestTwoDifferentAbsencesGetTwoDifferentAnswers:
    """No entries at all is not the same as entries without a measurement.

    Caught by `test_report_availability.py`, whose cell-position tests state
    outright that with no production data seeded "OTD is the only KPI in the
    table". An earlier version of this change emitted the Efficiency and
    Performance rows unconditionally and shifted every row below them.

      no entries at all       -> omit, as the OTD block does for a window with no
                                 deliveries and the labour-hours block for one with
                                 no attendance.
      entries, no measurement -> emit, "Not Recorded".
    """

    def test_a_window_with_no_production_omits_the_rows_entirely(self, transactional_db):
        db = transactional_db
        client = TestDataFactory.create_client(db)
        db.commit()

        pdf = [r["name"] for r in PDFReportGenerator(db)._fetch_kpi_summary(client.client_id, DAY, DAY)]
        excel = [r["name"] for r in ExcelReportGenerator(db)._fetch_kpi_summary_data(client.client_id, DAY, DAY)]

        for names in (pdf, excel):
            assert "Efficiency" not in names, names
            assert "Performance" not in names, names

    def test_entries_without_a_measurement_still_emit_the_row(self, client_with_unmeasured_production):
        db, client = client_with_unmeasured_production

        names = [r["name"] for r in PDFReportGenerator(db)._fetch_kpi_summary(client.client_id, DAY, DAY)]

        assert "Efficiency" in names, "the rows exist, so the row must too"
