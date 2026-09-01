"""The capacity workbook's master data.

Separate from `emitters_master` for two reasons. The capacity module is its
own subsystem with its own line table, its own calendar and its own order
book -- and its rows are declarations a planner makes, not things that happen
on the shop floor, so they do not belong in the operations stream either.

WHAT TIES IT TO THE REST OF THE SEED. Every style planned here is a style the
operations side already builds (`ClientSetup.products_by_id`), and the line
codes mirror the operational ones. A demo where the workbook plans products
nobody manufactures reads as two unrelated datasets; this one shows the same
factory from the planning side.

TIMESTAMPS. All of it is stamped inside the SETUP band -- late on the last
setup day, after `emit_setup`'s cursor and before the first activity event.
That matters most for the calendar: a calendar day is a DECLARATION, not an
event occurring on that date, and `generate()` drops any event whose `at` is
past `as_of`. Stamping a forward-looking calendar day at its own date would
delete exactly the future the planner needs.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Type

from backend.seed.emitters_master import ClientSetup
from backend.seed.events import (
    CapacityBomDefined,
    CapacityBomLineDefined,
    CapacityCalendarDayDeclared,
    CapacityLineDefined,
    CapacityOrderPlaced,
    CapacityStandardDefined,
    CapacityStockCounted,
    Event,
)
from backend.seed.profiles import Profile
from backend.seed.scenarios import ClientScenario

#: The departments a garment order passes through, in route order. Cycled
#: across lines so every department owns at least one, which is what makes an
#: OVERTIME scenario's `affected_departments` filter select a real subset.
DEPARTMENTS = ("CUTTING", "SEWING", "FINISHING")

#: Operations per style, one per department, with the standard minutes a
#: planner would quote. SAM totals ~13.5 min/unit, in the range the seeded
#: piece-rate clients already imply.
OPERATIONS = (
    ("OP-CUT", "Cut and bundle", "CUTTING", "2.5000", "15.0000", "1.8000", "0.7000"),
    ("OP-SEW", "Assemble", "SEWING", "8.7500", "22.5000", "5.2500", "3.5000"),
    ("OP-FIN", "Press, inspect and pack", "FINISHING", "2.2500", "8.0000", "0.9000", "1.3500"),
)

#: Components every style consumes. `quantity_per` and waste are per finished
#: unit, so a BOM explosion against an order quantity gives a usable number.
COMPONENTS = (
    ("FAB-MAIN", "Main body fabric", "2.400000", "M", "6.00", "FABRIC"),
    ("FAB-LINE", "Lining fabric", "0.850000", "M", "4.50", "FABRIC"),
    ("TRM-THREAD", "Thread cone", "0.120000", "EA", "2.00", "TRIM"),
    ("TRM-LABEL", "Care label set", "1.000000", "EA", "0.50", "TRIM"),
)

#: A forward window so the workbook has something to PLAN, not only history.
#: The seeded universe ends at `as_of`; a planner looking at a calendar that
#: stops today has no horizon to schedule into.
FORWARD_HORIZON_DAYS = 45


def emit_capacity(
    emit: Callable[..., None],
    scenario: ClientScenario,
    profile: Profile,
    setup: ClientSetup,
    as_of: date,
) -> None:
    cid = scenario.client_id

    # A LOCAL generator, deliberately not the stream's shared `rng`. Drawing
    # from that one here would shift every subsequent draw the operations
    # emitters make, so adding capacity data would silently re-roll work
    # orders, holds and attendance for every existing client -- measured: it
    # moved the aged-hold narrative and failed
    # test_at_least_three_holds_are_aged_past_sixty_days. Seeding from the
    # client id keeps this data deterministic AND independent.
    rng = random.Random(f"{cid}-capacity")

    # Late on the last setup day: after every entity emit_setup created, and
    # still strictly before activity_start, which owns whole days of its own.
    stamp_day = setup.activity_start - timedelta(days=1)
    cursor = datetime.combine(stamp_day, time(22, 0))
    minute = 0

    def declare(cls: Type[Event], **kw: Any) -> None:
        nonlocal minute
        emit(cls, cursor + timedelta(seconds=minute), cid, **kw)
        minute += 1

    # --- lines -----------------------------------------------------------
    for i in range(profile.lines_per_client):
        department = DEPARTMENTS[i % len(DEPARTMENTS)]
        declare(
            CapacityLineDefined,
            line_key=f"{cid}-CAPLINE-{i + 1:02d}",
            line_code=f"L{i + 1:02d}",
            line_name=f"Line {i + 1} ({department.title()})",
            department=department,
            # Rated output differs per department: cutting moves faster per
            # unit than assembly, which is what makes one line the bottleneck
            # rather than all of them tying.
            units_per_hour={"CUTTING": "48.00", "SEWING": "18.00", "FINISHING": "36.00"}[department],
            efficiency_factor="0.8500",
            absenteeism_factor="0.0500",
            max_operators=12,
        )

    # --- calendar --------------------------------------------------------
    day = setup.activity_start
    last = as_of + timedelta(days=FORWARD_HORIZON_DAYS)
    while day <= last:
        weekday = day.weekday()
        working = weekday < 5
        declare(
            CapacityCalendarDayDeclared,
            calendar_date=day,
            is_working_day=working,
            # Saturdays are declared non-working with zero hours rather than
            # omitted: an absent row and a closed day are the same thing to a
            # naive reader, and the OVERTIME scenario's whole point is turning
            # closed capacity into open capacity.
            shifts_available=2 if working else 0,
            shift1_hours="8.00" if working else "0.00",
            shift2_hours="4.00" if working else "0.00",
            holiday_name=None,
        )
        day += timedelta(days=1)

    # --- order book, standards, BOMs and stock, all keyed on real styles ---
    styles = [p.style for p in scenario.products]
    for si, product in enumerate(scenario.products):
        style = product.style

        for op_code, op_name, department, sam, setup_min, machine, manual in OPERATIONS:
            declare(
                CapacityStandardDefined,
                style_model=style,
                operation_code=f"{op_code}-{si + 1:02d}",
                operation_name=op_name,
                department=department,
                sam_minutes=sam,
                setup_time_minutes=setup_min,
                machine_time_minutes=machine,
                manual_time_minutes=manual,
            )

        bom_key = f"{cid}-BOM-{si + 1:02d}"
        declare(
            CapacityBomDefined,
            bom_key=bom_key,
            parent_item_code=product.code,
            parent_item_description=product.name,
            style_model=style,
            revision="1.0",
        )
        for comp_code, comp_desc, qty, uom, waste, comp_type in COMPONENTS:
            declare(
                CapacityBomLineDefined,
                bom_key=bom_key,
                component_item_code=f"{comp_code}-{si + 1:02d}",
                component_description=f"{comp_desc} ({style})",
                quantity_per=qty,
                unit_of_measure=uom,
                waste_percentage=waste,
                component_type=comp_type,
            )

    # Two orders per style: one already in progress, one still to plan. A book
    # of only-future orders shows no throughput; only-past shows nothing to
    # schedule.
    order_n = 0
    for si, product in enumerate(scenario.products):
        for leg, (offset_days, status, priority, done_fraction) in enumerate(
            (
                (-21, "IN_PROGRESS", "HIGH", 0.55),
                (18, "CONFIRMED", "NORMAL", 0.0),
            )
        ):
            order_n += 1
            required = as_of + timedelta(days=offset_days)
            quantity = 800 + 200 * ((si + leg) % 4)
            planned_start = required - timedelta(days=14)
            declare(
                CapacityOrderPlaced,
                order_ref=f"{cid}-CAPORD-{order_n:03d}",
                order_number=f"CO-{as_of.year}-{order_n:04d}",
                customer_name=f"{scenario.name.split()[0]} Retail",
                style_model=product.style,
                style_description=product.name,
                order_quantity=quantity,
                completed_quantity=int(quantity * done_fraction),
                order_date=planned_start - timedelta(days=10),
                required_date=required,
                planned_start_date=planned_start,
                planned_end_date=required - timedelta(days=2),
                priority=priority,
                status=status,
                # Order SAM = per-unit standard minutes * quantity, so the
                # workbook's demand hours and the standards table agree.
                order_sam_minutes=f"{13.5 * quantity:.4f}",
            )

    # --- stock, one position per component, counted on the seed's last day --
    for si in range(len(styles)):
        for comp_code, comp_desc, qty, uom, _waste, _ctype in COMPONENTS:
            on_hand = rng.randint(400, 4000)
            allocated = int(on_hand * 0.35)
            on_order = rng.choice((0, 0, 500, 1200))
            declare(
                CapacityStockCounted,
                snapshot_date=as_of,
                item_code=f"{comp_code}-{si + 1:02d}",
                item_description=comp_desc,
                on_hand_quantity=f"{on_hand}.0000",
                allocated_quantity=f"{allocated}.0000",
                on_order_quantity=f"{on_order}.0000",
                # Stated, not recomputed downstream: `available` is what the
                # shortage check reads, and deriving it here keeps the three
                # quantities internally consistent in the row a reader sees.
                available_quantity=f"{on_hand - allocated}.0000",
                unit_of_measure=uom,
                location=f"WH-{(si % 3) + 1:02d}",
            )
