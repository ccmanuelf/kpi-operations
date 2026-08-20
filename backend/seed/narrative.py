"""The scripted-episode layer: which multipliers and vocabularies a client-day
sits under.

Its own module so the emitters can consume it without the generator having to
import them back: generator -> emitters -> narrative is acyclic, while
generator <-> emitters would not be.

Pure, like every other module here: no database, no clock, no randomness. These
functions decide WHICH distribution a day draws from; they never draw.
"""

from datetime import date, timedelta
from typing import Dict, Tuple

from backend.seed.scenarios import (
    REASON_BY_ROOT_CAUSE,
    UNPLANNED_REASON_BY_ROOT_CAUSE,
    ClientScenario,
    NarrativeWindow,
)

# Narrative multipliers. "Roughly" per the brief -- these scale the drawn
# baseline rather than replace it, so days inside a window still differ from
# each other instead of collapsing to a constant.
DEFECT_CRISIS_SCALE = 3.0
DOWNTIME_DECLINE_SCALE = 3.0
ATTENDANCE_DISRUPTION_SCALE = 2.0 / 3.0  # "reduce by roughly a third"
HOLD_RATE_BASELINE = 0.15
HOLD_RATE_QUALITY_CRISIS = 0.5

#: Probability that a work order which reaches SHIPPED ships late. Baseline is
#: exactly ZERO, not merely low: SAMPLE_REF's narrative tuple is empty, so it
#: never touches a window and this constant is what makes it structurally
#: never late (spec section 6's healthy control) rather than just unlikely to
#: be. 0.9, not 1.0, inside a window so the RNG still decides which of the
#: eligible orders ship on time -- a hard 100% would read as scripted rather
#: than drawn.
LATE_RATE_BASELINE = 0.0
LATE_RATE_NARRATIVE = 0.9

# Reason pools for a hold. The crisis pool is the baseline with QUALITY
# weighted up, not replaced -- a crisis makes quality holds dominant, it does
# not make every other cause vanish.
BASELINE_REASONS = ("QUALITY", "MATERIAL", "ENGINEERING")
QUALITY_CRISIS_REASONS = ("QUALITY", "QUALITY", "QUALITY", "MATERIAL", "ENGINEERING")

# Root-cause pools for downtime, weighted the same way and for the same reason.
EQUIPMENT_DECLINE_CAUSES = ("machine", "machine", "machine", "machine", "materials", "other")
SCHEDULING_PRESSURE_CAUSES = ("scheduling", "scheduling", "machine", "materials", "other")
BASELINE_CAUSES = ("attendance", "machine", "materials", "other", "scheduling")


def window_bounds(window: NarrativeWindow, as_of: date) -> tuple:
    """A window's calendar bounds, resolved from as_of and its month offsets.
    Offsets are negative -- the EARLIER bound comes from the larger magnitude
    (start_month=-8 is further back than end_month=-6)."""
    earlier = as_of - timedelta(days=abs(window.start_month) * 30)
    later = as_of - timedelta(days=abs(window.end_month) * 30)
    return earlier, later


def window_active(scenario: ClientScenario, day: date, as_of: date, kind: str) -> bool:
    """Whether one of the scenario's windows of the given kind covers `day`."""
    for window in scenario.narrative:
        if window.kind != kind:
            continue
        earlier, later = window_bounds(window, as_of)
        if earlier <= day <= later:
            return True
    return False


def narrative_scale(scenario: ClientScenario, day: date, as_of: date) -> dict:
    """Multipliers applied to the drawn baseline for a client-day. Multiplying
    rather than overriding keeps the day-to-day RNG variation alive inside a
    scripted episode -- setting a constant would make every day identical and
    read as synthetic."""
    scale = {"defects": 1.0, "downtime": 1.0, "attendance": 1.0}
    if window_active(scenario, day, as_of, "supplier_quality_crisis"):
        scale["defects"] *= DEFECT_CRISIS_SCALE
    if window_active(scenario, day, as_of, "equipment_reliability_decline"):
        scale["downtime"] *= DOWNTIME_DECLINE_SCALE
    if window_active(scenario, day, as_of, "labor_disruption"):
        scale["attendance"] *= ATTENDANCE_DISRUPTION_SCALE
    return scale


def narrative_window_touches(scenario: ClientScenario, start: date, end: date, as_of: date) -> bool:
    """Whether the interval [start, end] overlaps ANY of the scenario's
    narrative windows, regardless of kind.

    Used for delivery lateness rather than a single anchor day: a narrative
    window is ~60 days wide and only about a third of work orders reach
    SHIPPED at all, so gating on one day (the way hold_rate gates on the
    hold's own day) leaves too few orders eligible to move a whole-year
    aggregate OTD rate. The order's own commitment span -- received to
    required -- is up to 60 days wide too, so checking it against the window
    for ANY overlap (not containment) captures the orders whose delivery
    promise falls under the story's shadow even if they were received before
    it started.

    Every scripted failure mode plausibly slows delivery (a quality crisis
    triggers holds and rework, an equipment decline slows throughput, a labor
    disruption reduces capacity), so this is not keyed to one specific `kind`
    the way defects/downtime/attendance are. SAMPLE_REF's narrative tuple is
    empty, so this is always False for it.
    """
    for window in scenario.narrative:
        earlier, later = window_bounds(window, as_of)
        if start <= later and end >= earlier:
            return True
    return False


def late_rate(touches_window: bool) -> float:
    """Delivery-lateness probability for a work order that reaches SHIPPED."""
    return LATE_RATE_NARRATIVE if touches_window else LATE_RATE_BASELINE


def hold_rate(in_quality_crisis: bool) -> float:
    """Baseline hold probability, raised while a supplier-quality-crisis
    window covers the date the HOLD would fall on -- not the date its order
    was received. A hold is caused by conditions at the moment it is placed;
    keying on receipt spread the elevation across the whole year and left the
    crisis window statistically indistinguishable."""
    return HOLD_RATE_QUALITY_CRISIS if in_quality_crisis else HOLD_RATE_BASELINE


def downtime_taxonomy(scenario: ClientScenario, day: date, as_of: date) -> Tuple[Tuple[str, ...], Dict[str, str]]:
    """Which root causes are plausible on this client-day, and which downtime
    reason each of them is written as.

    Biasing the POOL rather than forcing a value keeps the RNG varying which
    shifts get which cause, so a window reads as a shift in the MIX rather than
    a block of identical rows.

    The pool and the reason map are returned together, from one place, because
    they have to agree: an equipment-reliability decline both makes `machine`
    the dominant cause AND makes that cause a FAILURE rather than routine
    maintenance. Choosing them separately is how the decline came out written
    entirely as MAINTENANCE -- a PLANNED reason calculate_mtbf filters out,
    leaving the client's headline reliability metric flat through its own
    reliability episode. See UNPLANNED_REASON_BY_ROOT_CAUSE in scenarios.py.

    Consults narrative state but draws no randomness, so calling it cannot
    perturb the stream regardless of which windows are open.
    """
    if window_active(scenario, day, as_of, "equipment_reliability_decline"):
        return EQUIPMENT_DECLINE_CAUSES, UNPLANNED_REASON_BY_ROOT_CAUSE
    if window_active(scenario, day, as_of, "labor_disruption"):
        return SCHEDULING_PRESSURE_CAUSES, REASON_BY_ROOT_CAUSE
    return BASELINE_CAUSES, REASON_BY_ROOT_CAUSE
