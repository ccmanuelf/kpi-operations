"""Calculation assumptions, their history, and saved simulations.

Three tables behind the dual-view feature and the simulation screen. The other
two in this cluster are deliberately NOT here and are declared in
`coverage.NOT_SEEDED` with reasons: METRIC_ASSUMPTION_DEPENDENCY is seeded by
the BOOT path from the authoritative catalog, and METRIC_CALCULATION_RESULT is
output the nightly dual-view scheduler recomputes.

WHY THE VALUES DEVIATE. Dual-view exists to show a standard number beside a
site-adjusted one. If every assumption matched the catalog's `default_value`,
both views would be identical and the delta column would read zero on every
row -- a screen demonstrating its own layout and nothing else. Two of the six
deviate, and each carries the rationale a reviewer would ask for.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Type

from backend.seed.emitters_master import ClientSetup
from backend.seed.events import (
    AssumptionChanged,
    AssumptionRegistered,
    Event,
    SimulationScenarioSaved,
)
from backend.seed.profiles import Profile
from backend.seed.scenarios import CALCULATION_ASSUMPTIONS, USERS, ClientScenario

#: Who proposes and who approves. Both columns are ForeignKeys to USER.user_id,
#: and the split mirrors the lifecycle the status enum describes: a poweruser
#: submits, an admin approves.
PROPOSED_BY = next(u.user_id for u in USERS if u.role == "poweruser")
APPROVED_BY = next(u.user_id for u in USERS if u.role == "admin")

#: A simulation the operator can open and run. Sized from the same styles the
#: rest of the seed builds, so the scenario plans real products.
# The engine caps this at MAX_HORIZON_DAYS = 7 (simulation_v2/constants.py).
# Not imported: `backend.simulation_v2.constants` lives behind a package
# __init__ that pulls the whole simpy engine (237 modules) into what is
# meant to be a pure emitter. test_assumption_dataset.py validates every
# seeded config against the real schema instead, which catches drift in
# any field rather than just this one.
SIM_HORIZON_DAYS = 7

#: The route every saved simulation plans, mirroring the three-operation route
#: the capacity workbook is built from (emitters_capacity.OPERATIONS). Not
#: imported from there: that tuple carries capacity-side columns (setup
#: minutes, the machine/manual split) the simulation schema has no field for.
SIM_ROUTE = (
    ("Cut and bundle", "Cutter", 2.5, 2),
    ("Assemble", "Sewing line", 8.75, 8),
    ("Press, inspect and pack", "Finishing table", 2.25, 3),
)

#: When the site last reviewed the assumptions it adjusted, and how long the
#: ones left at the textbook default have gone unrevisited. The report calls a
#: row stale past 365 days, so these straddle it deliberately: a staleness
#: column where every row is the same colour demonstrates nothing.
#:
#: Both are measured from `as_of`, NOT from the activity window. Anchoring the
#: unreviewed ones to `activity_start` made the split a property of the
#: profile: FULL opens its window 365 days before as_of and SMOKE only 14, so
#: the same arithmetic left SMOKE's "stale" rows 145 days old (not stale at
#: all) and its recent review dated BEFORE the proposal it approves.
RECENT_REVIEW_DAYS = 45
STALE_REVIEW_DAYS = 400

#: Daily demand per product in the saved scenarios.
DAILY_DEMAND_PER_PRODUCT = 180.0

#: How much of demand the baseline run met. Below 1.0 on purpose: a scenario
#: that met demand exactly gives the planner nothing to act on.
BASELINE_COVERAGE = 0.941


def last_run_summary(product_count: int) -> dict:
    """The summary a REAL run leaves behind, key for key.

    POST /api/v2/simulation/scenarios/{id}/run persists exactly these six keys
    (routes/simulation_scenarios.py), and the scenario list renders
    `last_run_summary.daily_throughput_pcs` and `.daily_coverage_pct`. A
    summary with any other keys renders a run date beside two em-dashes --
    which reads as a run that failed to record its results, and is worse than
    the unrun row it is meant to contrast with. The previous shape
    ({horizon_days, fulfilled_pct, bottleneck}) shared no key with it; nothing
    in the repo wrote or read `fulfilled_pct` at all.

    Derived rather than typed, so coverage cannot contradict the throughput
    and demand printed beside it.
    """
    demand = DAILY_DEMAND_PER_PRODUCT * product_count
    throughput = round(demand * BASELINE_COVERAGE, 1)
    total_sam = sum(op[2] for op in SIM_ROUTE)
    return {
        "daily_throughput_pcs": throughput,
        "daily_demand_pcs": demand,
        "daily_coverage_pct": round(throughput / demand * 100, 1),
        "avg_cycle_time_min": total_sam,
        "avg_wip_pcs": round(throughput / len(SIM_ROUTE), 1),
        "duration_seconds": 2.4,
    }


def emit_assumptions(
    emit: Callable[..., None],
    scenario: ClientScenario,
    profile: Profile,
    setup: ClientSetup,
    as_of: date,
) -> None:
    cid = scenario.client_id
    stamp = datetime.combine(setup.activity_start - timedelta(days=1), time(20, 0))
    minute = 0

    def declare(cls: Type[Event], **kw: Any) -> None:
        nonlocal minute
        emit(cls, stamp + timedelta(seconds=minute), cid, **kw)
        minute += 1

    for name, value, default_value, deviates, rationale in CALCULATION_ASSUMPTIONS:
        key = f"{cid}-ASSUMP-{name}"
        value_json = json.dumps(value)
        # `days_since_review` counts from approved_at, and the variance report
        # calls a row stale past STALE_AFTER_DAYS. Approving all six on one day
        # put every row at the same age, so the staleness column showed one
        # state -- and, sitting exactly ON the boundary, all of them would flip
        # together the day after the seed was taken.
        #
        # The two the site adjusted were reviewed when it adjusted them; the
        # four left at the textbook default have not been revisited since
        # before this window opened. effective_date is unchanged either way:
        # all six have been in force the whole time, and approved_at is the
        # REVIEW date, which is what the report measures.
        review_days = RECENT_REVIEW_DAYS if deviates else STALE_REVIEW_DAYS
        approved_at = datetime.combine(as_of - timedelta(days=review_days), time(11, 0))
        # A proposal cannot postdate its own approval. `stamp` sits one day
        # before the activity window, which is earlier than any review date in
        # FULL but LATER than the recent one in SMOKE -- so the earlier of the
        # two is the only choice that holds for both profiles.
        proposed_at = min(stamp, approved_at - timedelta(hours=2))
        declare(
            AssumptionRegistered,
            assumption_key=key,
            assumption_name=name,
            value_json=value_json,
            rationale=rationale,
            effective_date=datetime.combine(setup.activity_start, time(0, 0)),
            status="active",
            # The lifecycle the status enum describes: a poweruser proposes,
            # an admin approves. Both are ForeignKeys to USER.user_id.
            proposed_by=PROPOSED_BY,
            proposed_at=proposed_at,
            # status is "active", and approve() is the only way a row reaches
            # it. The admin who approves is already named for the change row
            # below; recording it only there left every assumption ACTIVE with
            # no approver.
            approved_by=APPROVED_BY,
            approved_at=approved_at,
        )
        # Only the deviating ones carry a change row. An assumption left at the
        # catalog default was never edited, and inventing an approval for it
        # would put a decision in the audit trail that nobody made.
        if deviates:
            declare(
                AssumptionChanged,
                assumption_key=key,
                changed_by=APPROVED_BY,
                # A value change on an already-active assumption, NOT an
                # initial proposal. previous_value_json=None is the model's
                # documented shape for a proposal (orm/calculation_assumption
                # .py) -- using it here would have left the history view
                # unable to say what the site moved away from, which is the
                # only thing that view exists to show.
                previous_value_json=json.dumps(default_value),
                new_value_json=value_json,
                previous_status="active",
                new_status="active",
                change_reason=rationale,
            )

    # --- saved simulations -------------------------------------------------
    styles = [p.style for p in scenario.products]
    # Every product gets the WHOLE route. Indexing the product by the operation
    # (`styles[i % len(styles)]` across the three steps) handed each product a
    # different SINGLE step -- one product was cut and never sewn, another's
    # route began at step 2 -- and the step numbers only looked sequential
    # because they were counting operations rather than each product's route.
    operations = [
        {
            "product": style,
            "step": step,
            "operation": op_name,
            "machine_tool": machine,
            "sam_min": sam,
            "operators": operators,
        }
        for style in styles
        for step, (op_name, machine, sam, operators) in enumerate(SIM_ROUTE, start=1)
    ]
    demands = [{"product": style, "daily_demand": DAILY_DEMAND_PER_PRODUCT, "bundle_size": 20} for style in styles]
    schedule = {
        "shifts_enabled": 2,
        "shift1_hours": 8.0,
        "shift2_hours": 4.0,
        "work_days": 5,
        "ot_enabled": True,
        "weekday_ot_hours": 2.0,
        "weekend_ot_days": 0,
    }

    for idx, (sim_name, description, ot_enabled, ran) in enumerate(
        (
            (
                "Baseline: current staffing",
                "The line as it runs today, with no overtime. The reference every other " "scenario is judged against.",
                False,
                True,
            ),
            (
                "With weekday overtime",
                "Two hours of weekday overtime on top of the two shifts already running, "
                "to see whether the demand horizon closes without adding a third.",
                True,
                False,
            ),
        )
    ):
        config = {
            "operations": operations,
            "schedule": {**schedule, "ot_enabled": ot_enabled},
            "demands": demands,
            "horizon_days": SIM_HORIZON_DAYS,
        }
        declare(
            SimulationScenarioSaved,
            scenario_key=f"{cid}-SIM-{idx + 1:02d}",
            name=sim_name,
            description=description,
            config=config,
            # Only the baseline has been run. A list where every scenario
            # carries results shows no difference between saved and executed,
            # which is the distinction the run button exists for.
            last_run_summary=dict(last_run_summary(len(styles))) if ran else None,
            last_run_at=datetime.combine(as_of - timedelta(days=3), time(9, 15)) if ran else None,
        )
