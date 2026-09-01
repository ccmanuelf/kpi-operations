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
            proposed_at=stamp,
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
    operations = [
        {
            "product": styles[i % len(styles)],
            "step": i + 1,
            "operation": op_name,
            "machine_tool": machine,
            "sam_min": sam,
            "operators": operators,
        }
        for i, (op_name, machine, sam, operators) in enumerate(
            (
                ("Cut and bundle", "Cutter", 2.5, 2),
                ("Assemble", "Sewing line", 8.75, 8),
                ("Press, inspect and pack", "Finishing table", 2.25, 3),
            )
        )
    ]
    demands = [{"product": style, "daily_demand": 180.0, "bundle_size": 20} for style in styles]
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
                "Two hours of weekday overtime added, to see whether the demand horizon "
                "closes without a second shift.",
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
            last_run_summary=(
                {"horizon_days": SIM_HORIZON_DAYS, "fulfilled_pct": 92.4, "bottleneck": "Assemble"} if ran else None
            ),
            last_run_at=datetime.combine(as_of - timedelta(days=3), time(9, 15)) if ran else None,
        )
