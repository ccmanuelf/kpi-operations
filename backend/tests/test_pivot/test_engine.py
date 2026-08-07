"""Engine behavior over the SQL-path datasets, on the standard SQLite test DB.

Seeds minimal ORM rows spanning a week boundary so bucket rollup, grouping,
ratio-of-sums, zero-denominator None, scoping, and coercion are all pinned.
"""

from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest

from backend.orm.client import Client
from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.product import Product
from backend.orm.production_entry import ProductionEntry
from backend.orm.shift import Shift
from backend.orm.user import User
from backend.pivot.engine import run_pivot


# Fixture note (per task-3-brief.md): the db_session template DB is
# Alembic-schema-only (no demo seed data), so the FK targets the entries
# below reference — product_id=1, shift_id=1, entered_by="USR-ADMIN-001",
# plus the CLIENT rows the enforced client_id FK needs — don't pre-exist and
# must be inserted here. Autouse so every test starts with them in place;
# harmless (and unused) for the one test that never touches the DB.
@pytest.fixture(autouse=True)
def _seed_fks(db_session):
    db_session.add_all(
        [
            Client(client_id="PIVOT-CLI", client_name="Pivot Test Client"),
            Client(client_id="PIVOT-OTHER", client_name="Pivot Other Client"),
            Product(
                product_id=1,
                client_id="PIVOT-CLI",
                product_code="PVT-PROD",
                product_name="Pivot Product",
                # ideal_cycle_time left NULL: test_zero_denominator_ratio_is_none
                # relies on the product-level fallback also being absent.
            ),
            Shift(
                shift_id=1,
                client_id="PIVOT-CLI",
                shift_name="Pivot Shift",
                start_time=time(6, 0),
                end_time=time(14, 0),
            ),
            User(
                user_id="USR-ADMIN-001",
                username="pivot_admin",
                email="pivot_admin@test.com",
                role="admin",
            ),
        ]
    )
    db_session.commit()


def _pe(db, entry_id, client, day, units, run_h, ict, present=5):
    db.add(
        ProductionEntry(
            production_entry_id=entry_id,
            client_id=client,
            product_id=1,
            shift_id=1,
            production_date=datetime(day.year, day.month, day.day, 6),
            shift_date=datetime(day.year, day.month, day.day, 6),
            units_produced=units,
            run_time_hours=Decimal(str(run_h)),
            employees_assigned=present,
            employees_present=present,
            ideal_cycle_time=Decimal(str(ict)) if ict is not None else None,
            entered_by="USR-ADMIN-001",
        )
    )


def test_month_bucket_groups_and_ratio_of_sums(db_session):
    # Two entries same month, different ict presence, one excluded from earned
    _pe(db_session, "PVT-1", "PIVOT-CLI", date(2026, 3, 2), 100, 10, 0.05)
    _pe(db_session, "PVT-2", "PIVOT-CLI", date(2026, 3, 9), 200, 10, 0.10)
    db_session.commit()

    out = run_pivot(
        db_session,
        "production",
        "month",
        None,
        date(2026, 3, 1),
        date(2026, 3, 31),
        ["PIVOT-CLI"],
    )
    assert out["bucket"] == "month"
    [row] = out["rows"]
    assert row["bucket_start"] == "2026-03-01"
    assert row["units"] == 300
    assert row["run_hours"] == 20.0
    # earned = 100*0.05 + 200*0.10 = 25.0 ; efficiency = 25/20*100 (ratio of SUMS)
    assert row["earned_hours"] == 25.0
    assert row["efficiency_pct"] == pytest.approx(125.0)
    assert out["totals"]["efficiency_pct"] == pytest.approx(125.0)
    # JSON-safe: floats/ints/None/str only
    for v in row.values():
        assert v is None or isinstance(v, (int, float, str))


def test_week_bucket_splits_on_iso_monday(db_session):
    _pe(db_session, "PVT-3", "PIVOT-CLI", date(2026, 8, 2), 10, 1, 0.1)  # Sunday -> wk 7/27
    _pe(db_session, "PVT-4", "PIVOT-CLI", date(2026, 8, 3), 10, 1, 0.1)  # Monday -> wk 8/03
    db_session.commit()
    out = run_pivot(
        db_session,
        "production",
        "week",
        None,
        date(2026, 8, 1),
        date(2026, 8, 9),
        ["PIVOT-CLI"],
    )
    assert [r["bucket_start"] for r in out["rows"]] == ["2026-07-27", "2026-08-03"]


def test_zero_denominator_ratio_is_none(db_session):
    _pe(db_session, "PVT-5", "PIVOT-CLI", date(2026, 3, 2), 50, 0, None)
    db_session.commit()
    out = run_pivot(
        db_session,
        "production",
        "month",
        None,
        date(2026, 3, 1),
        date(2026, 3, 31),
        ["PIVOT-CLI"],
    )
    [row] = out["rows"]
    assert row["efficiency_pct"] is None
    assert row["excluded_entries"] == 1


def test_group_by_and_share(db_session):
    # NOTE: brief draft used "MECHANICAL_FAILURE", which is not a valid
    # DowntimeReasonEnum member (backend/orm/downtime_taxonomy.py) and trips
    # the ORM's @validates("downtime_reason") on add(). Substituted the
    # equivalent valid reason "EQUIPMENT_FAILURE" — root_cause_category is
    # set explicitly per-row below, so this substitution does not touch any
    # assertion (category/share math is unchanged).
    for i, (reason, cat, minutes) in enumerate(
        [("EQUIPMENT_FAILURE", "machine", 90), ("MATERIAL_SHORTAGE", "materials", 30)]
    ):
        db_session.add(
            DowntimeEntry(
                downtime_entry_id=f"PVT-DT-{i}",
                client_id="PIVOT-CLI",
                shift_date=datetime(2026, 3, 2, 6),
                downtime_reason=reason,
                root_cause_category=cat,
                downtime_duration_minutes=minutes,
            )
        )
    db_session.commit()
    out = run_pivot(
        db_session,
        "downtime",
        "month",
        "category",
        date(2026, 3, 1),
        date(2026, 3, 31),
        ["PIVOT-CLI"],
    )
    by_key = {r["group_key"]: r for r in out["rows"]}
    assert by_key["machine"]["downtime_hours"] == 1.5
    assert by_key["machine"]["events"] == 1
    assert by_key["machine"]["share_of_window_pct"] == pytest.approx(75.0)
    assert by_key["materials"]["share_of_window_pct"] == pytest.approx(25.0)
    assert out["totals"]["downtime_hours"] == 2.0


def test_group_by_line_joins(db_session):
    """Exercises GroupBy.joins (the `ds.joins + gb.joins` concatenation in
    _sql_day_rows) -- no other test grouped production by `line`, which is
    the only production group_by that adds its own join beyond the dataset's
    Product join."""
    from backend.orm.production_line import ProductionLine

    db_session.add(
        ProductionLine(
            client_id="PIVOT-CLI",
            line_code="PVT-LINE-1",
            line_name="Pivot Sewing Line",
        )
    )
    db_session.commit()
    line = db_session.query(ProductionLine).filter_by(line_code="PVT-LINE-1").one()

    db_session.add(
        ProductionEntry(
            production_entry_id="PVT-LINE-PE-1",
            client_id="PIVOT-CLI",
            product_id=1,
            shift_id=1,
            line_id=line.line_id,
            production_date=datetime(2026, 3, 2, 6),
            shift_date=datetime(2026, 3, 2, 6),
            units_produced=40,
            run_time_hours=Decimal("4"),
            employees_assigned=2,
            employees_present=2,
            ideal_cycle_time=Decimal("0.1"),
            entered_by="USR-ADMIN-001",
        )
    )
    db_session.commit()

    out = run_pivot(
        db_session,
        "production",
        "month",
        "line",
        date(2026, 3, 1),
        date(2026, 3, 31),
        ["PIVOT-CLI"],
    )
    [row] = out["rows"]
    assert row["group_key"] == "Pivot Sewing Line"
    assert row["units"] == 40


def test_client_scope_filters(db_session):
    _pe(db_session, "PVT-6", "PIVOT-CLI", date(2026, 3, 2), 10, 1, 0.1)
    _pe(db_session, "PVT-7", "PIVOT-OTHER", date(2026, 3, 2), 999, 1, 0.1)
    db_session.commit()
    out = run_pivot(
        db_session,
        "production",
        "month",
        None,
        date(2026, 3, 1),
        date(2026, 3, 31),
        ["PIVOT-CLI"],
    )
    assert out["totals"]["units"] == 10


def test_unknown_group_by_raises_value_error(db_session):
    with pytest.raises(ValueError):
        run_pivot(
            db_session,
            "production",
            "month",
            "nope",
            date(2026, 3, 1),
            date(2026, 3, 31),
            None,
        )


def test_quality_fpy_ratio_of_sums(db_session):
    from backend.orm.quality_entry import QualityEntry
    from backend.orm.work_order import WorkOrder

    # Create WorkOrder for QualityEntry FK (work_order_id is NOT NULL)
    db_session.add(
        WorkOrder(
            work_order_id="PVT-WO-QE",
            client_id="PIVOT-CLI",
            style_model="PVT",
            planned_quantity=1,
        )
    )
    db_session.commit()

    for i, (insp, passed, defects) in enumerate([(100, 90, 12), (50, 25, 30)]):
        db_session.add(
            QualityEntry(
                quality_entry_id=f"PVT-QE-{i}",
                client_id="PIVOT-CLI",
                work_order_id="PVT-WO-QE",
                shift_date=datetime(2026, 3, 2, 6),
                units_inspected=insp,
                units_passed=passed,
                units_defective=insp - passed,
                total_defects_count=defects,
            )
        )
    db_session.commit()
    out = run_pivot(
        db_session,
        "quality",
        "month",
        None,
        date(2026, 3, 1),
        date(2026, 3, 31),
        ["PIVOT-CLI"],
    )
    [row] = out["rows"]
    assert row["inspected"] == 150
    assert row["defects"] == 42
    # FPY ratio-of-sums: (90+25)/150*100 = 76.67 — NOT avg(90%, 50%) = 70
    assert row["fpy_pct"] == pytest.approx(76.67, abs=0.01)


def test_holds_measures(db_session):
    from backend.orm.hold_entry import HoldEntry
    from backend.orm.work_order import WorkOrder

    # Create WorkOrder for HoldEntry FK (work_order_id is NOT NULL)
    db_session.add(
        WorkOrder(
            work_order_id="PVT-WO-HOLD",
            client_id="PIVOT-CLI",
            style_model="PVT",
            planned_quantity=1,
        )
    )
    db_session.commit()

    for i, (cat, hours) in enumerate([("Material", 48), ("Material", 24), ("Quality", 12)]):
        db_session.add(
            HoldEntry(
                hold_entry_id=f"PVT-H-{i}",
                client_id="PIVOT-CLI",
                work_order_id="PVT-WO-HOLD",
                hold_status="ON_HOLD",
                hold_date=datetime(2026, 3, 2, 6),
                hold_reason_category=cat,
                hold_reason="MATERIAL_SHORTAGE",
                total_hold_duration_hours=Decimal(str(hours)),
            )
        )
    db_session.commit()
    out = run_pivot(
        db_session,
        "holds",
        "month",
        "reason_category",
        date(2026, 3, 1),
        date(2026, 3, 31),
        ["PIVOT-CLI"],
    )
    by_key = {r["group_key"]: r for r in out["rows"]}
    assert by_key["Material"]["holds"] == 2
    assert by_key["Material"]["hold_days"] == 3.0  # 72h / 24
    assert by_key["Material"]["avg_days_per_hold"] == pytest.approx(1.5)


def test_holds_resolved_hold_uses_recorded_duration(db_session):
    """Validation finding F3 (b): a resolved hold (total_hold_duration_hours
    set) uses its recorded hours/24 -- unchanged from the pre-fix SQL path's
    math, now produced by the fetch_holds hook instead."""
    from backend.orm.hold_entry import HoldEntry
    from backend.orm.work_order import WorkOrder

    db_session.add(
        WorkOrder(
            work_order_id="PVT-WO-RESOLVED",
            client_id="PIVOT-CLI",
            style_model="PVT",
            planned_quantity=1,
        )
    )
    db_session.commit()
    db_session.add(
        HoldEntry(
            hold_entry_id="PVT-H-RESOLVED",
            client_id="PIVOT-CLI",
            work_order_id="PVT-WO-RESOLVED",
            hold_status="RESUMED",
            hold_date=datetime(2026, 3, 2, 6),
            hold_reason_category="Material",
            hold_reason="MATERIAL_SHORTAGE",
            total_hold_duration_hours=Decimal("48"),
        )
    )
    db_session.commit()
    out = run_pivot(db_session, "holds", "month", "reason_category", date(2026, 3, 1), date(2026, 3, 31), ["PIVOT-CLI"])
    by_key = {r["group_key"]: r for r in out["rows"]}
    assert by_key["Material"]["holds"] == 1
    assert by_key["Material"]["hold_days"] == 2.0  # 48h / 24
    assert by_key["Material"]["avg_days_per_hold"] == pytest.approx(2.0)


def test_holds_active_hold_uses_age_to_date(db_session):
    """Validation finding F3 (a): an active hold (NULL duration -- the VM's
    chronic seeded holds are still ON_HOLD) contributes age-to-date, not 0.
    Previously the SQL path's SUM(COALESCE(total_hold_duration_hours, 0))
    silently zeroed every open hold; the fetch_holds hook now falls back to
    (today - hold_date).days for rows with no recorded duration.

    HoldEntry.total_hold_duration_hours declares an ORM-level `default=0`
    (backend/orm/hold_entry.py) that SQLAlchemy applies at flush whenever the
    attribute is None -- whether explicitly passed or simply omitted -- so a
    plain `HoldEntry(...)` insert can never land a genuine NULL through the
    ORM. The column itself is nullable at the DB layer (no server_default,
    per the Alembic baseline), so real NULLs do exist (imported/legacy rows);
    force one here via a Core UPDATE, which bypasses that ORM-instance
    default path, to exercise the branch this fix targets.
    """
    from sqlalchemy import update

    from backend.orm.hold_entry import HoldEntry
    from backend.orm.work_order import WorkOrder

    db_session.add(
        WorkOrder(
            work_order_id="PVT-WO-ACTIVE",
            client_id="PIVOT-CLI",
            style_model="PVT",
            planned_quantity=1,
        )
    )
    db_session.commit()
    hold_day = date.today() - timedelta(days=10)
    db_session.add(
        HoldEntry(
            hold_entry_id="PVT-H-ACTIVE",
            client_id="PIVOT-CLI",
            work_order_id="PVT-WO-ACTIVE",
            hold_status="ON_HOLD",
            hold_date=datetime.combine(hold_day, time(6, 0)),
            hold_reason_category="Material",
            hold_reason="MATERIAL_SHORTAGE",
        )
    )
    db_session.commit()
    db_session.execute(
        update(HoldEntry).where(HoldEntry.hold_entry_id == "PVT-H-ACTIVE").values(total_hold_duration_hours=None)
    )
    db_session.commit()
    out = run_pivot(
        db_session,
        "holds",
        "year",
        "reason_category",
        date.today() - timedelta(days=400),
        date.today(),
        ["PIVOT-CLI"],
    )
    by_key = {r["group_key"]: r for r in out["rows"]}
    assert by_key["Material"]["holds"] == 1
    assert by_key["Material"]["hold_days"] == pytest.approx(10, abs=0.01)
    assert by_key["Material"]["avg_days_per_hold"] == pytest.approx(10, abs=0.01)
