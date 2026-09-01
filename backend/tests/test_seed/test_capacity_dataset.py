"""The capacity workbook, asserted against a FULL seeded database.

Three invariants that a reader would otherwise have to take on trust, and
that were each broken at some point while this data was being written:

  * every scheduled day has a calendar day behind it -- otherwise the day
    contributes demand while contributing no capacity, and utilisation reads
    high for a reason nothing in the data explains;
  * a schedule row's denormalised `order_number` names the order its
    `order_id` points at -- they are derived in two places and agreed only
    by coincidence until they were paired;
  * all three ComponentStatus values occur -- `SHORTAGE` was unreachable
    because the available quantity had a floor of 300, so the shortage
    workflow's worst state could never be demonstrated.

Also pins the headline the whole module exists for: the plant runs hot with a
bottleneck, and the overtime scenario clears it. A capacity module where
every scenario reports zero is what this data replaced.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import text

from backend.seed.generator import generate
from backend.seed.materialize import materialize
from backend.seed.profiles import FULL, SMOKE
from backend.seed.scenarios import SCENARIOS

AS_OF = date(2026, 8, 21)


@pytest.fixture(scope="module")
def full_db(seed_engine_module):
    events = generate(SCENARIOS, FULL, seed=1234, as_of=AS_OF)
    with seed_engine_module.begin() as conn:
        materialize(conn, events, FULL)
    return seed_engine_module


def test_every_scheduled_day_has_a_calendar_day_behind_it(full_db):
    with full_db.begin() as conn:
        orphans = conn.execute(
            text(
                "SELECT COUNT(*) FROM capacity_schedule_detail d "
                "WHERE NOT EXISTS (SELECT 1 FROM capacity_calendar c "
                "                  WHERE c.client_id = d.client_id "
                "                    AND c.calendar_date = d.scheduled_date)"
            )
        ).scalar_one()
    assert orphans == 0, (
        f"{orphans} scheduled days have no calendar row -- they contribute demand "
        "with no working day behind them, so utilisation is overstated"
    )


def test_the_calendar_covers_the_schedule_on_a_SHORT_profile_too(seed_engine):
    """The FULL case above cannot fail this, which is why this one exists.

    FULL runs 365 days, so `activity_start` is already far earlier than the
    schedule's 30-day lookback and anchoring the calendar to it happens to
    work. SMOKE runs 14 -- `activity_start` lands AFTER `as_of - 30d`, and
    anchoring the calendar there leaves the first two weeks of the schedule
    with no calendar row: those days contribute demand while contributing no
    working day, so capacity is undercounted against demand that is fully
    counted. Reverting the `min(activity_start, schedule_lookback_start)`
    anchor fails here and nowhere else.
    """
    events = generate(SCENARIOS, SMOKE, seed=1234, as_of=AS_OF)
    with seed_engine.begin() as conn:
        materialize(conn, events, SMOKE)
        orphans = conn.execute(
            text(
                "SELECT COUNT(*) FROM capacity_schedule_detail d "
                "WHERE NOT EXISTS (SELECT 1 FROM capacity_calendar c "
                "                  WHERE c.client_id = d.client_id "
                "                    AND c.calendar_date = d.scheduled_date)"
            )
        ).scalar_one()
    assert orphans == 0, f"{orphans} scheduled days have no calendar row on the SMOKE profile"


def test_a_schedule_rows_order_number_names_the_order_it_points_at(full_db):
    with full_db.begin() as conn:
        mismatches = conn.execute(
            text(
                "SELECT COUNT(*) FROM capacity_schedule_detail d "
                "JOIN capacity_orders o ON o.id = d.order_id "
                "WHERE o.order_number <> d.order_number"
            )
        ).scalar_one()
    assert mismatches == 0, f"{mismatches} rows display one order's number while referencing another"


def test_the_component_check_exercises_all_three_statuses(full_db):
    with full_db.begin() as conn:
        seen = {row[0] for row in conn.execute(text("SELECT DISTINCT status FROM capacity_component_check"))}
    assert seen == {"OK", "PARTIAL", "SHORTAGE"}, (
        f"component check only produced {sorted(seen)} -- a shortage workflow whose worst "
        "state never occurs demonstrates a screen, not the workflow"
    )


def test_the_plant_runs_hot_with_a_bottleneck_an_overtime_plan_can_clear(full_db):
    """The headline this module's data exists to produce.

    Before it, every scenario compared 0 capacity hours against 0 and resolved
    0 bottlenecks -- structurally, because demand comes only from schedule
    detail under a COMMITTED/ACTIVE schedule and there was none.
    """
    from sqlalchemy.orm import Session

    from backend.orm.capacity.scenario import CapacityScenario
    from backend.services.capacity.analysis_service import CapacityAnalysisService
    from backend.services.capacity.scenario_service import ScenarioService

    with Session(full_db) as session:
        client_id = session.query(CapacityScenario.client_id).first()[0]
        scenario_ids = [
            row[0] for row in session.query(CapacityScenario.id).filter(CapacityScenario.client_id == client_id).all()
        ]
        start = AS_OF
        end = AS_OF + timedelta(days=30)

        analysis = CapacityAnalysisService(session).analyze_capacity(
            client_id=client_id, period_start=start, period_end=end
        )
        assert analysis.total_capacity_hours > 0
        assert analysis.total_demand_hours > 0
        assert analysis.bottleneck_count >= 1, "no bottleneck: nothing for a scenario to resolve"

        comparisons = ScenarioService(session).compare_scenarios(client_id, scenario_ids, start, end)
        assert len(comparisons) == len(scenario_ids)

        by_type = {c.scenario_type: c for c in comparisons}
        overtime = by_type["OVERTIME"]
        assert overtime.capacity_increase_percent > 0
        assert overtime.modified_utilization < overtime.original_utilization
        assert overtime.bottlenecks_resolved >= 1, "the overtime plan clears no bottleneck"

        # The two plans must differ, or the comparison screen shows one answer
        # twice and there is nothing to choose between.
        setup_reduction = by_type["SETUP_REDUCTION"]
        assert overtime.capacity_increase_percent != setup_reduction.capacity_increase_percent
