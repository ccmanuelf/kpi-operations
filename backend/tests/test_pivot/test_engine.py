"""Engine behavior over the SQL-path datasets, on the standard SQLite test DB.

Seeds minimal ORM rows spanning a week boundary so bucket rollup, grouping,
ratio-of-sums, zero-denominator None, scoping, and coercion are all pinned.
"""

from datetime import date, datetime, time
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
