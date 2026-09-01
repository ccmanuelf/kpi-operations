"""The machine registry and the DPMO metadata that gives a defect count a
denominator.

Both tables were empty in every demo before this, and each empty table hid a
feature rather than merely showing a short list:

  * GET /api/equipment/shared filters on is_shared, so with no shared row it
    could only ever return [] -- the route looked broken rather than unused;
  * dpmo.get_opportunities_for_part falls back to a default when no row
    matches the part, so every DPMO on the site read the fallback while
    looking configured.

Nothing here draws from the stream's RNG. Both tables are registry data a
plant sets up once, not sampled behaviour, so the values are derived from the
route and BOM the rest of the seed already defines.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Optional, Type

from backend.seed.emitters_capacity import COMPONENTS, DEPARTMENTS, OPERATIONS
from backend.seed.emitters_master import ClientSetup
from backend.seed.events import EquipmentRegistered, Event, PartOpportunityDefined
from backend.seed.profiles import Profile
from backend.seed.scenarios import ClientScenario

#: The machine each department runs, so equipment_type reads as the floor
#: would name it rather than as a database category. Keyed by the same
#: DEPARTMENTS the capacity route is built from, so a department added there
#: fails loudly here instead of silently producing typeless machines.
MACHINE_BY_DEPARTMENT = {
    "CUTTING": ("Cutting table", "Cutting Table"),
    "SEWING": ("Assembly machine", "Sewing Machine"),
    "FINISHING": ("Press and pack station", "Press"),
}

#: What each client makes, for PART_OPPORTUNITIES.part_category. Read off the
#: product names in SCENARIOS rather than invented; a client added without an
#: entry gets the generic category instead of a KeyError.
PART_CATEGORY_BY_CLIENT = {
    "DEMO-PIECE": "Apparel",
    "DEMO-HOURLY": "Machined Component",
    "DEMO-HYBRID": "Assembly",
    "SAMPLE_REF": "Reference",
}
DEFAULT_PART_CATEGORY = "Finished Good"

#: Defect opportunities per finished unit: every operation that can be
#: performed wrong, plus every component that can be attached wrong. Derived
#: from the route and BOM rather than typed, so adding an operation moves the
#: DPMO denominator with it. The seed runs one shared route, so this is the
#: same for every product -- a per-product number would be fiction.
OPPORTUNITIES_PER_UNIT = len(OPERATIONS) + len(COMPONENTS)

#: Maintenance cadence, in days either side of the as-of date.
SERVICE_INTERVAL_DAYS = 45
OVERDUE_DAYS = 5
RETIRED_LAST_SERVICE_DAYS = 300


def emit_equipment(
    emit: Callable[..., None],
    scenario: ClientScenario,
    profile: Profile,
    setup: ClientSetup,
    as_of: date,
) -> None:
    cid = scenario.client_id
    stamp = datetime.combine(setup.activity_start - timedelta(days=1), time(18, 0))
    minute = 0

    def declare(cls: Type[Event], **kw: Any) -> None:
        nonlocal minute
        emit(cls, stamp + timedelta(seconds=minute), cid, **kw)
        minute += 1

    def machine(
        seq: int,
        line_key: Optional[str],
        department: str,
        status: str,
        *,
        is_shared: bool = False,
        is_active: bool = True,
        name: Optional[str] = None,
        equipment_type: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        base_name, base_type = MACHINE_BY_DEPARTMENT[department]
        if status == "MAINTENANCE":
            last = as_of - timedelta(days=SERVICE_INTERVAL_DAYS * 2)
            nxt: Optional[date] = as_of - timedelta(days=OVERDUE_DAYS)
        elif status == "RETIRED":
            last = as_of - timedelta(days=RETIRED_LAST_SERVICE_DAYS)
            nxt = None
        else:
            last = as_of - timedelta(days=SERVICE_INTERVAL_DAYS)
            nxt = as_of + timedelta(days=SERVICE_INTERVAL_DAYS)
        declare(
            EquipmentRegistered,
            equipment_key=f"{cid}-EQP-{seq:03d}",
            line_key=line_key,
            equipment_code=f"MCH-{seq:03d}",
            equipment_name=name or base_name,
            equipment_type=equipment_type or base_type,
            is_shared=is_shared,
            status=status,
            is_active=is_active,
            last_maintenance_date=last,
            next_maintenance_date=nxt,
            notes=notes,
        )

    seq = 0
    for line_index, line_key in enumerate(setup.lines):
        for department in DEPARTMENTS:
            seq += 1
            # One machine down for service, on the second line's bottleneck
            # department. A registry where every row is ACTIVE never shows
            # what the status column is for.
            down = line_index == 1 and department == "SEWING"
            machine(
                seq,
                line_key,
                department,
                "MAINTENANCE" if down else "ACTIVE",
                notes="Bearing replacement scheduled; line running on the adjacent machine." if down else None,
            )

    # Not tied to a line: the only kind of row GET /api/equipment/shared
    # can return.
    seq += 1
    machine(
        seq,
        None,
        "FINISHING",
        "ACTIVE",
        is_shared=True,
        name="Shared compressor",
        equipment_type="Air Compressor",
        notes="Serves every line; scheduled downtime affects the whole floor.",
    )

    # Retired but not deleted, so the status filter has all three values and
    # the default list still shows it.
    seq += 1
    machine(
        seq,
        setup.lines[0],
        "CUTTING",
        "RETIRED",
        name="Manual cutting table (retired)",
        notes="Replaced by the automated table; kept for the maintenance record.",
    )

    # Soft-deleted, which is a different axis from RETIRED: this one is only
    # visible with include_inactive=True.
    seq += 1
    machine(
        seq,
        setup.lines[0],
        "SEWING",
        "RETIRED",
        is_active=False,
        name="Scrapped machine",
        notes="Scrapped after flood damage; kept out of the default list.",
    )

    for product_key in setup.products:
        product = setup.products_by_id[product_key]
        declare(
            PartOpportunityDefined,
            part_number=product.code,
            opportunities_per_unit=OPPORTUNITIES_PER_UNIT,
            part_description=product.name,
            part_category=PART_CATEGORY_BY_CLIENT.get(cid, DEFAULT_PART_CATEGORY),
        )
