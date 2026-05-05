"""
Real-data aggregators for the dual-view inspector (F.1).

Verifies that aggregate_*_inputs() pulls correct values from
ProductionEntry / QualityEntry / WorkOrder rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from backend.orm.production_entry import ProductionEntry
from backend.orm.quality_entry import QualityEntry
from backend.orm.work_order import WorkOrder, WorkOrderStatus
from backend.services.dual_view.aggregators import (
    aggregate_fpy_inputs,
    aggregate_oee_inputs,
    aggregate_otd_inputs,
)
from backend.tests.fixtures.factories import TestDataFactory


PERIOD_START = datetime(2026, 4, 1, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 4, 30, 23, 59, 59, tzinfo=timezone.utc)


def _client_user(db, client_id: str = "AGG-CLIENT"):
    client = TestDataFactory.create_client(db, client_id=client_id)
    user = TestDataFactory.create_user(db, role="admin", client_id=client.client_id)
    db.commit()
    return client, user


def _make_production_entry(db, *, client_id, **overrides):
    """Create a ProductionEntry with sensible defaults."""

    product = TestDataFactory.create_product(db, client_id=client_id)
    shift = TestDataFactory.create_shift(db, client_id=client_id)
    user = TestDataFactory.create_user(db, role="operator", client_id=client_id)
    db.flush()

    defaults = dict(
        production_entry_id=f"PE-{TestDataFactory._next_int('pe')}",
        client_id=client_id,
        product_id=product.product_id,
        shift_id=shift.shift_id,
        production_date=datetime(2026, 4, 15, tzinfo=timezone.utc),
        shift_date=datetime(2026, 4, 15, tzinfo=timezone.utc),
        units_produced=100,
        run_time_hours=Decimal("7.0"),
        employees_assigned=5,
        defect_count=2,
        scrap_count=1,
        setup_time_hours=Decimal("0.5"),
        downtime_hours=Decimal("0.5"),
        maintenance_hours=Decimal("0.0"),
        ideal_cycle_time=Decimal("0.07"),
        entered_by=int("".join(c for c in user.user_id if c.isdigit()) or "1"),
    )
    defaults.update(overrides)
    entry = ProductionEntry(**defaults)
    db.add(entry)
    db.commit()
    return entry


def _make_quality_entry(db, *, client_id, work_order_id=None, **overrides):
    if work_order_id is None:
        wo = WorkOrder(
            work_order_id=f"WO-Q-{TestDataFactory._next_int('woq')}",
            client_id=client_id,
            style_model="STYLE-Q",
            planned_quantity=100,
            received_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
        )
        db.add(wo)
        db.flush()
        work_order_id = wo.work_order_id

    defaults = dict(
        quality_entry_id=f"QE-{TestDataFactory._next_int('qe')}",
        client_id=client_id,
        work_order_id=work_order_id,
        shift_date=datetime(2026, 4, 15, tzinfo=timezone.utc),
        units_inspected=100,
        units_passed=85,
        units_defective=15,
        total_defects_count=15,
        units_reworked=10,
    )
    defaults.update(overrides)
    qe = QualityEntry(**defaults)
    db.add(qe)
    db.commit()
    return qe


class TestAggregateOEE:
    def test_empty_period_yields_zero_aggregates(self, transactional_db):
        client, _ = _client_user(transactional_db)
        result = aggregate_oee_inputs(transactional_db, client.client_id, PERIOD_START, PERIOD_END)
        assert result.units_produced == 0
        assert result.run_time_hours == Decimal("0")
        assert result.scheduled_hours == Decimal("0")
        # Cycle time falls back to default
        assert result.ideal_cycle_time_hours == Decimal("0.25")

    def test_two_entries_summed(self, transactional_db):
        client, _ = _client_user(transactional_db)
        _make_production_entry(
            transactional_db,
            client_id=client.client_id,
            units_produced=100,
            run_time_hours=Decimal("7.0"),
            downtime_hours=Decimal("0.5"),
            setup_time_hours=Decimal("0.5"),
            maintenance_hours=Decimal("0.0"),
            defect_count=2,
            scrap_count=1,
        )
        _make_production_entry(
            transactional_db,
            client_id=client.client_id,
            units_produced=80,
            run_time_hours=Decimal("6.0"),
            downtime_hours=Decimal("1.0"),
            setup_time_hours=Decimal("0.5"),
            maintenance_hours=Decimal("0.5"),
            defect_count=3,
            scrap_count=2,
        )

        result = aggregate_oee_inputs(transactional_db, client.client_id, PERIOD_START, PERIOD_END)
        assert result.units_produced == 180
        assert result.run_time_hours == Decimal("13.0")
        assert result.downtime_hours == Decimal("1.5")
        # scheduled = run + downtime + setup + maintenance = 13 + 1.5 + 1 + 0.5
        assert result.scheduled_hours == Decimal("16.0")
        # setup_minutes = 1h × 60
        assert result.setup_minutes == Decimal("60.0")
        assert result.scheduled_maintenance_hours == Decimal("0.5")
        assert result.defect_count == 5
        assert result.scrap_count == 3

    def test_other_clients_excluded(self, transactional_db):
        client_a, _ = _client_user(transactional_db, client_id="AGG-A")
        client_b, _ = _client_user(transactional_db, client_id="AGG-B")
        _make_production_entry(transactional_db, client_id=client_a.client_id, units_produced=999)

        result = aggregate_oee_inputs(transactional_db, client_b.client_id, PERIOD_START, PERIOD_END)
        assert result.units_produced == 0

    def test_rework_pulled_from_quality_entries(self, transactional_db):
        client, _ = _client_user(transactional_db)
        _make_production_entry(transactional_db, client_id=client.client_id)
        _make_quality_entry(transactional_db, client_id=client.client_id, units_reworked=12)

        result = aggregate_oee_inputs(transactional_db, client.client_id, PERIOD_START, PERIOD_END)
        assert result.units_reworked == 12

    def test_heterogeneous_products_use_units_weighted_cycle_time(self, transactional_db):
        # Regression: with simple func.avg, heterogeneous products (cheap fast
        # cycle + slow expensive cycle in the same period) made the aggregate
        # cycle time too high, and Performance came back > 100% even when each
        # individual entry was bounded. Units-weighted average is the correct
        # aggregation: sum(cycle × units) / sum(units).
        client, _ = _client_user(transactional_db)
        # 49 fast units at 0.15 h/unit + 14 slow units at 0.50 h/unit, both
        # produced in 8h. Per-entry Performance is exactly the target_perf
        # the seeder picks (90% and 87.5% respectively).
        _make_production_entry(
            transactional_db,
            client_id=client.client_id,
            units_produced=48,
            run_time_hours=Decimal("8.0"),
            ideal_cycle_time=Decimal("0.15"),
        )
        _make_production_entry(
            transactional_db,
            client_id=client.client_id,
            units_produced=14,
            run_time_hours=Decimal("8.0"),
            ideal_cycle_time=Decimal("0.50"),
        )
        result = aggregate_oee_inputs(transactional_db, client.client_id, PERIOD_START, PERIOD_END)
        # Weighted cycle = (0.15*48 + 0.50*14) / 62 = 14.20 / 62 ≈ 0.229
        weighted = (Decimal("0.15") * 48 + Decimal("0.50") * 14) / Decimal(62)
        assert abs(result.ideal_cycle_time_hours - weighted) < Decimal("0.001")
        # Sanity: with this weighted cycle, Performance ≤ 100% on the aggregate
        # (0.229 * 62 / 16) * 100 ≈ 88.7% — physical and below the 150% cap.
        perf_pct = (
            result.ideal_cycle_time_hours * Decimal(result.units_produced) / result.run_time_hours * Decimal("100")
        )
        assert perf_pct <= Decimal("100")

    def test_missing_master_cycle_time_falls_back_to_observed_rate(self, transactional_db):
        # Regression: with the old hardcoded 0.25h fallback, demo data without
        # a master ideal_cycle_time produced Performance > 100% (and OEE > 100%).
        # The aggregator now derives the standard from the observed rate
        # (run_time / units), which makes Performance == 100% — the conservative
        # interpretation when no published standard exists.
        client, _ = _client_user(transactional_db)
        _make_production_entry(
            transactional_db,
            client_id=client.client_id,
            units_produced=200,
            run_time_hours=Decimal("8.0"),
            ideal_cycle_time=None,
        )
        result = aggregate_oee_inputs(transactional_db, client.client_id, PERIOD_START, PERIOD_END)
        # 8h / 200 units = 0.04 h/unit observed
        assert result.ideal_cycle_time_hours == Decimal("0.04")


class TestAggregateOTD:
    def test_empty_period_yields_zero_orders(self, transactional_db):
        client, _ = _client_user(transactional_db)
        result = aggregate_otd_inputs(transactional_db, client.client_id, PERIOD_START, PERIOD_END)
        assert result.orders == []

    def test_orders_with_delays_aggregated(self, transactional_db):
        client, _ = _client_user(transactional_db)
        # Lead time = 30 days. On-time order, late by 3 days, late by 6 days.
        for delay_days, delivery in ((0, 15), (3, 18), (6, 21)):
            wo = WorkOrder(
                work_order_id=f"WO-OTD-{delay_days}",
                client_id=client.client_id,
                style_model="X",
                planned_quantity=100,
                planned_start_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
                planned_ship_date=datetime(2026, 4, 15, tzinfo=timezone.utc),
                actual_delivery_date=datetime(2026, 4, delivery, tzinfo=timezone.utc),
                status=WorkOrderStatus.COMPLETED,
            )
            transactional_db.add(wo)
        transactional_db.commit()

        result = aggregate_otd_inputs(transactional_db, client.client_id, PERIOD_START, PERIOD_END)
        # 3 work orders → 3 delay entries
        assert len(result.orders) == 3
        # Lead time = 14 days; delays are 0/14, 3/14, 6/14
        delay_pcts = sorted(float(o.delay_pct) for o in result.orders)
        assert delay_pcts[0] == 0.0
        assert abs(delay_pcts[1] - 3 / 14) < 0.001
        assert abs(delay_pcts[2] - 6 / 14) < 0.001

    def test_orders_missing_required_dates_skipped(self, transactional_db):
        client, _ = _client_user(transactional_db)
        # No actual_delivery_date → excluded
        wo = WorkOrder(
            work_order_id="WO-NO-DELIVERY",
            client_id=client.client_id,
            style_model="X",
            planned_quantity=100,
            planned_start_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
            planned_ship_date=datetime(2026, 4, 15, tzinfo=timezone.utc),
            actual_delivery_date=None,
            status=WorkOrderStatus.IN_PROGRESS,
        )
        transactional_db.add(wo)
        transactional_db.commit()

        result = aggregate_otd_inputs(transactional_db, client.client_id, PERIOD_START, PERIOD_END)
        assert result.orders == []


class TestAggregateOEEFilters:
    def test_work_order_id_filter_applied(self, transactional_db):
        from backend.orm.work_order import WorkOrder

        client, _ = _client_user(transactional_db)
        wo1 = WorkOrder(work_order_id="WO-F-1", client_id=client.client_id, style_model="X", planned_quantity=100)
        wo2 = WorkOrder(work_order_id="WO-F-2", client_id=client.client_id, style_model="X", planned_quantity=100)
        transactional_db.add(wo1)
        transactional_db.add(wo2)
        transactional_db.flush()

        _make_production_entry(
            transactional_db,
            client_id=client.client_id,
            work_order_id="WO-F-1",
            units_produced=50,
        )
        _make_production_entry(
            transactional_db,
            client_id=client.client_id,
            work_order_id="WO-F-2",
            units_produced=120,
        )

        result = aggregate_oee_inputs(
            transactional_db,
            client.client_id,
            PERIOD_START,
            PERIOD_END,
            work_order_id="WO-F-1",
        )
        assert result.units_produced == 50

    def test_no_filter_includes_all_rows(self, transactional_db):
        from backend.orm.work_order import WorkOrder

        client, _ = _client_user(transactional_db)
        wo1 = WorkOrder(work_order_id="WO-F-3", client_id=client.client_id, style_model="X", planned_quantity=100)
        wo2 = WorkOrder(work_order_id="WO-F-4", client_id=client.client_id, style_model="X", planned_quantity=100)
        transactional_db.add(wo1)
        transactional_db.add(wo2)
        transactional_db.flush()

        _make_production_entry(
            transactional_db,
            client_id=client.client_id,
            work_order_id="WO-F-3",
            units_produced=50,
        )
        _make_production_entry(
            transactional_db,
            client_id=client.client_id,
            work_order_id="WO-F-4",
            units_produced=120,
        )

        result = aggregate_oee_inputs(
            transactional_db,
            client.client_id,
            PERIOD_START,
            PERIOD_END,
        )
        assert result.units_produced == 170


class TestAggregateFPYFilters:
    def test_work_order_id_filter(self, transactional_db):
        client, _ = _client_user(transactional_db)
        _make_quality_entry(
            transactional_db,
            client_id=client.client_id,
            work_order_id="WO-Q-A",
            units_inspected=50,
            units_passed=45,
        )
        _make_quality_entry(
            transactional_db,
            client_id=client.client_id,
            work_order_id="WO-Q-B",
            units_inspected=100,
            units_passed=80,
        )

        result = aggregate_fpy_inputs(
            transactional_db,
            client.client_id,
            PERIOD_START,
            PERIOD_END,
            work_order_id="WO-Q-A",
        )
        assert result.total_inspected == 50
        assert result.units_passed_first_time == 45

    def test_inapplicable_filters_silently_ignored(self, transactional_db):
        client, _ = _client_user(transactional_db)
        _make_quality_entry(
            transactional_db,
            client_id=client.client_id,
            units_inspected=100,
            units_passed=80,
        )
        # Passing line_id/shift_id/product_id is accepted but has no effect
        result = aggregate_fpy_inputs(
            transactional_db,
            client.client_id,
            PERIOD_START,
            PERIOD_END,
            line_id=999,
            shift_id=999,
            product_id=999,
        )
        assert result.total_inspected == 100


class TestAggregateFPY:
    def test_empty_period_yields_zero(self, transactional_db):
        client, _ = _client_user(transactional_db)
        result = aggregate_fpy_inputs(transactional_db, client.client_id, PERIOD_START, PERIOD_END)
        assert result.total_inspected == 0
        assert result.units_passed_first_time == 0
        assert result.units_reworked == 0

    def test_summed_across_quality_entries(self, transactional_db):
        client, _ = _client_user(transactional_db)
        _make_quality_entry(
            transactional_db,
            client_id=client.client_id,
            units_inspected=100,
            units_passed=80,
            units_reworked=10,
        )
        _make_quality_entry(
            transactional_db,
            client_id=client.client_id,
            units_inspected=50,
            units_passed=45,
            units_reworked=3,
        )

        result = aggregate_fpy_inputs(transactional_db, client.client_id, PERIOD_START, PERIOD_END)
        assert result.total_inspected == 150
        assert result.units_passed_first_time == 125
        assert result.units_reworked == 13
