"""Reports must not aggregate one tenant's data into another tenant's document.

`PDFReportGenerator` takes a `client_id` and applies it to its production and
quality queries -- but both of its attendance queries were unfiltered, so a
client-scoped PDF computed absenteeism over EVERY tenant's attendance. The
number was wrong, and it was not the reader's to see.

`/api/reports/attendance/pdf` is the sharpest case: absenteeism is its ONLY
section, so that whole document was cross-tenant.

This is the class #144 swept out of the route layer via a uniform
`resolve_client_scope` dependency. The report generators sit below the routes
and query the ORM directly, so that sweep never reached them -- which is why
these assert on the generator itself rather than on an endpoint.
"""

from datetime import date
from decimal import Decimal

from backend.db.factories import TestDataFactory
from backend.reports.pdf_generator import PDFReportGenerator

DAY = date(2026, 6, 11)


def _tenant_with_absence(db, *, absent_hours: Decimal, scheduled_hours: Decimal = Decimal("8.0")):
    """One client whose single attendance row carries a known absence."""
    client = TestDataFactory.create_client(db)
    shift = TestDataFactory.create_shift(db, client_id=client.client_id)
    employee = TestDataFactory.create_employee(db, client_id=client.client_id)
    TestDataFactory.create_attendance_entry(
        db,
        employee_id=employee.employee_id,
        client_id=client.client_id,
        shift_id=shift.shift_id,
        shift_date=DAY,
        scheduled_hours=scheduled_hours,
        absence_hours=absent_hours,
        is_absent=absent_hours > 0,
    )
    db.commit()
    return client


def _absenteeism_from_summary(db, client_id):
    rows = PDFReportGenerator(db)._fetch_kpi_summary(client_id, DAY, DAY)
    return next((r["value"] for r in rows if r["name"] == "Absenteeism"), None)


class TestAbsenteeismIsClientScoped:
    def test_the_summary_counts_only_the_requested_client(self, transactional_db):
        db = transactional_db
        # Tenant A: fully absent. Tenant B: fully present. Unscoped, the two
        # average to 50%; scoped to A it must be 100%.
        a = _tenant_with_absence(db, absent_hours=Decimal("8.0"))
        _tenant_with_absence(db, absent_hours=Decimal("0.0"))

        assert _absenteeism_from_summary(db, a.client_id) == 100.0

    def test_the_other_tenant_reads_its_own_figure(self, transactional_db):
        # Two-sided: scoping must not be achieved by returning a constant.
        db = transactional_db
        _tenant_with_absence(db, absent_hours=Decimal("8.0"))
        b = _tenant_with_absence(db, absent_hours=Decimal("0.0"))

        assert _absenteeism_from_summary(db, b.client_id) == 0.0

    def test_the_detail_section_counts_only_the_requested_client(self, transactional_db):
        # /api/reports/attendance/pdf renders this section and nothing else.
        db = transactional_db
        a = _tenant_with_absence(db, absent_hours=Decimal("8.0"))
        _tenant_with_absence(db, absent_hours=Decimal("0.0"))

        details = PDFReportGenerator(db)._fetch_kpi_details("absenteeism", a.client_id, DAY, DAY)

        assert "Status" not in details, f"absenteeism fell through to the placeholder: {details}"
        assert "100.0" in str(details.values()), details

    def test_an_unscoped_request_still_sees_everything(self, transactional_db):
        # client_id=None means "all clients" for an internal/global report, and
        # must keep doing so -- the fix is a filter, not a hard requirement.
        db = transactional_db
        _tenant_with_absence(db, absent_hours=Decimal("8.0"))
        _tenant_with_absence(db, absent_hours=Decimal("0.0"))

        assert _absenteeism_from_summary(db, None) == 50.0
