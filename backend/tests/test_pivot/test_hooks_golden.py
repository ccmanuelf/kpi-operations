"""Cross-source goldens (spec §8): for the same window/scope the pivot labor
dataset MUST equal summarize_labor_hours, and the pivot delivery dataset MUST
equal calculate_true_otd. These pin engine-vs-KPI consistency structurally.

NOTE: unlike the task brief's draft (which assumed a demo-seeded template
DB), the pivot test-template DB is Alembic-schema-only -- there is no seed
data. The `seeded` fixture below inserts a client, mixed-labor-class
employees, attendance entries (OT-split + unsplit, allocated + unallocated),
production entries (with/without an inferable ideal_cycle_time), and work
orders (on-time, late-unjustified, late-justified, and one with no
inferable planned date to exercise calculate_true_otd's skip rule) directly,
so the goldens compare pivot totals against summarize_labor_hours /
calculate_true_otd over the exact same rows in the same session -- a
stronger guarantee than the brief's template-seeded version.

Field-name note: calculate_true_otd's `true_otd` sub-dict uses `total` and
`on_time` (not `total_orders`/`on_time_count` as the brief's draft assumed --
see backend/calculations/otd.py:477-488 for the actual keys)."""

from datetime import date, datetime, time
from decimal import Decimal

import pytest

from backend.calculations.labor_hours import earned_hours, summarize_labor_hours
from backend.calculations.otd import calculate_true_otd
from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.attendance_hour_allocation import AttendanceHourAllocation
from backend.orm.client import Client
from backend.orm.employee import Employee
from backend.orm.product import Product
from backend.orm.production_entry import ProductionEntry
from backend.orm.shift import Shift
from backend.orm.user import User
from backend.orm.work_order import WorkOrder, WorkOrderStatus
from backend.pivot.engine import run_pivot

WINDOW = (date(2025, 1, 1), date(2026, 12, 31))
CID = "PVTH-CLI"


@pytest.fixture
def seeded(db_session):
    """Seed FK targets + labor/delivery fixture rows and return the client id.

    The pivot test-template DB is schema-only (see module docstring), so
    every FK target the rows below reference is inserted here, not assumed
    demo-seeded.
    """
    db_session.add_all(
        [
            Client(client_id=CID, client_name="Pivot Hooks Client"),
            Product(
                product_id=1,
                client_id=CID,
                product_code="PVTH-PROD",
                product_name="Pivot Hooks Product",
                # ideal_cycle_time left NULL: PE-2 below has none of its own
                # either, so it lands in excluded_entries (never guessed).
            ),
            Shift(
                shift_id=1,
                client_id=CID,
                shift_name="Pivot Hooks Shift",
                start_time=time(6, 0),
                end_time=time(14, 0),
            ),
            User(
                user_id="USR-PVTH-001",
                username="pivot_hooks_admin",
                email="pivot_hooks_admin@test.com",
                role="admin",
            ),
        ]
    )
    db_session.commit()

    db_session.add_all(
        [
            Employee(
                employee_id=1,
                employee_code="PVTH-E1",
                employee_name="Direct Employee",
                client_id_assigned=CID,
                labor_class="direct",
            ),
            Employee(
                employee_id=2,
                employee_code="PVTH-E2",
                employee_name="Indirect Employee",
                client_id_assigned=CID,
                labor_class="indirect",
            ),
            Employee(
                employee_id=3,
                employee_code="PVTH-E3",
                employee_name="Unclassified Employee",
                client_id_assigned=CID,
                labor_class=None,
            ),
        ]
    )
    db_session.commit()

    # AttendanceEntry rows: OT-split (e1), unsplit (e2, e4), mixed
    # allocations (e1 billed+nonbillable, e3 fully billed, e4 nonproductive
    # only, e2 none at all), and a per-entry labor_class_override (e4,
    # employee 1's *default* is direct but this entry overrides to indirect).
    db_session.add_all(
        [
            AttendanceEntry(
                attendance_entry_id="PVTH-ATT-1",
                client_id=CID,
                employee_id=1,
                shift_id=1,
                shift_date=datetime(2026, 3, 2, 6),
                scheduled_hours=Decimal("8"),
                actual_hours=Decimal("8"),
                normal_hours=Decimal("6"),
                double_hours=Decimal("2"),
                triple_hours=Decimal("0"),
                entered_by="USR-PVTH-001",
            ),
            AttendanceEntry(
                attendance_entry_id="PVTH-ATT-2",
                client_id=CID,
                employee_id=2,
                shift_id=1,
                shift_date=datetime(2026, 3, 3, 6),
                scheduled_hours=Decimal("8"),
                actual_hours=Decimal("7.5"),
                entered_by="USR-PVTH-001",
            ),
            AttendanceEntry(
                attendance_entry_id="PVTH-ATT-3",
                client_id=CID,
                employee_id=3,
                shift_id=1,
                shift_date=datetime(2026, 3, 4, 6),
                scheduled_hours=Decimal("8"),
                actual_hours=Decimal("8"),
                normal_hours=Decimal("8"),
                double_hours=Decimal("0"),
                triple_hours=Decimal("0"),
                entered_by="USR-PVTH-001",
            ),
            AttendanceEntry(
                attendance_entry_id="PVTH-ATT-4",
                client_id=CID,
                employee_id=1,
                shift_id=1,
                shift_date=datetime(2026, 3, 5, 6),
                scheduled_hours=Decimal("8"),
                actual_hours=Decimal("8"),
                labor_class_override="indirect",
                entered_by="USR-PVTH-001",
            ),
        ]
    )
    db_session.commit()

    db_session.add_all(
        [
            AttendanceHourAllocation(
                attendance_entry_id="PVTH-ATT-1", category="billed_production", hours=Decimal("5")
            ),
            AttendanceHourAllocation(attendance_entry_id="PVTH-ATT-1", category="training", hours=Decimal("1")),
            AttendanceHourAllocation(
                attendance_entry_id="PVTH-ATT-3", category="billed_production", hours=Decimal("8")
            ),
            AttendanceHourAllocation(attendance_entry_id="PVTH-ATT-4", category="idle_wait", hours=Decimal("2")),
        ]
    )
    db_session.commit()

    # ProductionEntry rows: PE-1 has its own ideal_cycle_time (counted into
    # earned_hours); PE-2 has neither its own nor the product's (excluded).
    db_session.add_all(
        [
            ProductionEntry(
                production_entry_id="PVTH-PE-1",
                client_id=CID,
                product_id=1,
                shift_id=1,
                production_date=datetime(2026, 3, 2, 6),
                shift_date=datetime(2026, 3, 2, 6),
                units_produced=100,
                run_time_hours=Decimal("10"),
                employees_assigned=5,
                employees_present=5,
                ideal_cycle_time=Decimal("0.05"),
                entered_by="USR-PVTH-001",
            ),
            ProductionEntry(
                production_entry_id="PVTH-PE-2",
                client_id=CID,
                product_id=1,
                shift_id=1,
                production_date=datetime(2026, 3, 3, 6),
                shift_date=datetime(2026, 3, 3, 6),
                units_produced=50,
                run_time_hours=Decimal("5"),
                employees_assigned=5,
                employees_present=5,
                ideal_cycle_time=None,
                entered_by="USR-PVTH-001",
            ),
        ]
    )
    db_session.commit()

    # WorkOrders: on-time (WO-1), late-unjustified (WO-2), late-justified
    # (WO-3), and no-inferable-planned-date (WO-4 -- exercises the skip
    # rule: no planned_ship_date/required_date/planned_start_date at all).
    db_session.add_all(
        [
            WorkOrder(
                work_order_id="PVTH-WO-1",
                client_id=CID,
                style_model="PVTH-STYLE-A",
                planned_quantity=10,
                status=WorkOrderStatus.COMPLETED,
                planned_ship_date=datetime(2026, 3, 5),
                actual_delivery_date=datetime(2026, 3, 4),
            ),
            WorkOrder(
                work_order_id="PVTH-WO-2",
                client_id=CID,
                style_model="PVTH-STYLE-A",
                planned_quantity=10,
                status=WorkOrderStatus.COMPLETED,
                planned_ship_date=datetime(2026, 3, 5),
                actual_delivery_date=datetime(2026, 3, 10),
            ),
            WorkOrder(
                work_order_id="PVTH-WO-3",
                client_id=CID,
                style_model="PVTH-STYLE-B",
                planned_quantity=10,
                status=WorkOrderStatus.COMPLETED,
                planned_ship_date=datetime(2026, 3, 5),
                actual_delivery_date=datetime(2026, 3, 9),
                delay_classification="justified",
                justified_delay_reason="material_supplier_delay",
            ),
            WorkOrder(
                work_order_id="PVTH-WO-4",
                client_id=CID,
                style_model="PVTH-STYLE-B",
                planned_quantity=10,
                status=WorkOrderStatus.COMPLETED,
                actual_delivery_date=datetime(2026, 3, 6),
            ),
        ]
    )
    db_session.commit()

    return CID


def test_labor_totals_equal_summarize_labor_hours(db_session, seeded):
    cid = seeded
    golden = summarize_labor_hours(db_session, [cid], *WINDOW)
    out = run_pivot(db_session, "labor", "year", None, *WINDOW, [cid])
    t = out["totals"]
    g = golden["totals"]
    for key in (
        "scheduled",
        "actual",
        "normal",
        "double",
        "triple",
        "unsplit_actual",
        "billed",
        "available_for_efficiency",
    ):
        assert t[key] == pytest.approx(float(g[key])), key


def test_labor_by_class_equals_golden(db_session, seeded):
    cid = seeded
    golden = summarize_labor_hours(db_session, [cid], *WINDOW)
    out = run_pivot(db_session, "labor", "year", "labor_class", *WINDOW, [cid])
    by_key = {r["group_key"]: r for r in out["rows"]}
    for cls in ("direct", "indirect"):
        if float(golden["by_labor_class"][cls]["actual"]) > 0:
            assert by_key[cls]["actual"] == pytest.approx(float(golden["by_labor_class"][cls]["actual"]))
    # Omit-when-never-produced rule: earned_hours is never produced by
    # fetch_labor when group_by == "labor_class" (production rows carry no
    # labor class), so efficiency_available_basis must be absent -- not
    # 0/None-spammed -- from every row and from totals.
    assert "efficiency_available_basis" not in out["totals"]
    for row in out["rows"]:
        assert "efficiency_available_basis" not in row


def test_labor_efficiency_available_basis_matches_ratio_of_sums(db_session, seeded):
    cid = seeded
    earned, _excluded = earned_hours(db_session, [cid], *WINDOW)
    golden = summarize_labor_hours(db_session, [cid], *WINDOW)
    out = run_pivot(db_session, "labor", "year", None, *WINDOW, [cid])
    avail = float(golden["totals"]["available_for_efficiency"])
    assert avail > 0
    assert out["totals"]["efficiency_available_basis"] == pytest.approx(round(float(earned) / avail * 100, 2))


def test_delivery_totals_equal_calculate_true_otd(db_session, seeded):
    cid = seeded
    golden = calculate_true_otd(db_session, cid, *WINDOW)
    out = run_pivot(db_session, "delivery", "year", None, *WINDOW, [cid])
    t = out["totals"]
    # calculate_true_otd's true_otd sub-dict keys are `total`/`on_time`
    # (backend/calculations/otd.py:477-488) -- not total_orders/on_time_count.
    assert t["delivered"] == golden["true_otd"]["total"]
    assert t["on_time"] == golden["true_otd"]["on_time"]
    assert t["delivered"] > 0
    assert t["otd_gross_pct"] == pytest.approx(float(golden["true_otd"]["percentage"]), abs=0.01)
    assert t["otd_net_pct"] == pytest.approx(float(golden["true_otd"]["net_percentage"]), abs=0.01)


def test_delivery_zero_on_time_reports_percentages_as_zero_not_omitted(db_session):
    """Regression: the omit-when-never-produced rule must be structural (a
    Component the hook never touches for THIS group_by, e.g. earned_hours
    under group_by='labor_class'), not data-dependent (a Component no row
    happened to increment this run). A window whose only COMPLETED delivery
    is late and unjustified must report 0% OTD -- not silently drop the
    otd_gross_pct/otd_net_pct keys from rows and totals."""
    cid = "PVTH-ZERO-OTD"
    db_session.add(Client(client_id=cid, client_name="Zero OTD Client"))
    db_session.commit()
    db_session.add(
        WorkOrder(
            work_order_id="PVTH-ZERO-WO-1",
            client_id=cid,
            style_model="PVTH-STYLE-ZERO",
            planned_quantity=1,
            status=WorkOrderStatus.COMPLETED,
            planned_ship_date=datetime(2026, 3, 5),
            actual_delivery_date=datetime(2026, 3, 10),  # late; delay_classification unset -> unjustified
        )
    )
    db_session.commit()

    out = run_pivot(db_session, "delivery", "year", None, *WINDOW, [cid])
    assert out["totals"]["delivered"] == 1.0
    assert out["totals"]["on_time"] == 0.0
    assert out["totals"]["otd_gross_pct"] == 0.0
    assert out["totals"]["otd_net_pct"] == 0.0
    [row] = out["rows"]
    assert row["otd_gross_pct"] == 0.0
    assert row["otd_net_pct"] == 0.0


def test_labor_all_excluded_production_reports_efficiency_available_basis_as_zero(db_session):
    """Regression companion to the delivery test above: a window whose
    production rows all lack an inferable ideal_cycle_time must still report
    efficiency_available_basis == 0.0 (earned_hours produced, just zero) --
    not omit the ratio outright. Distinct from group_by='labor_class', where
    earned_hours is genuinely never applicable (production rows carry no
    labor class) and omission there is still correct (see
    test_labor_by_class_equals_golden)."""
    cid = "PVTH-ALL-EXCLUDED"
    db_session.add_all(
        [
            Client(client_id=cid, client_name="All Excluded Client"),
            Product(product_id=1, client_id=cid, product_code="PVTH-AE-PROD", product_name="AE Product"),
            Shift(shift_id=1, client_id=cid, shift_name="AE Shift", start_time=time(6, 0), end_time=time(14, 0)),
            User(user_id="USR-PVTH-AE-001", username="pvth_ae_admin", email="pvth_ae_admin@test.com", role="admin"),
            Employee(
                employee_id=1,
                employee_code="PVTH-AE-E1",
                employee_name="AE Employee",
                client_id_assigned=cid,
                labor_class="direct",
            ),
        ]
    )
    db_session.commit()
    db_session.add(
        AttendanceEntry(
            attendance_entry_id="PVTH-AE-ATT-1",
            client_id=cid,
            employee_id=1,
            shift_id=1,
            shift_date=datetime(2026, 3, 2, 6),
            scheduled_hours=Decimal("8"),
            actual_hours=Decimal("8"),
            entered_by="USR-PVTH-AE-001",
        )
    )
    db_session.add(
        ProductionEntry(
            production_entry_id="PVTH-AE-PE-1",
            client_id=cid,
            product_id=1,
            shift_id=1,
            production_date=datetime(2026, 3, 2, 6),
            shift_date=datetime(2026, 3, 2, 6),
            units_produced=10,
            run_time_hours=Decimal("1"),
            employees_assigned=1,
            employees_present=1,
            ideal_cycle_time=None,  # and Product above also has none -> excluded
            entered_by="USR-PVTH-AE-001",
        )
    )
    db_session.commit()

    out = run_pivot(db_session, "labor", "year", None, *WINDOW, [cid])
    assert out["totals"]["excluded_entries"] == 1.0
    assert out["totals"]["efficiency_available_basis"] == 0.0
