"""Where a report's targets and its status verdict come from.

Both generators used to carry inline literals -- efficiency 85, FPY 99, PPM
1000, absenteeism 5 -- and judged every client against them. `KPI_THRESHOLD` has
stored per-client and global targets all along, and the KPI threshold editor on
the admin settings screen is the one section of that page that really persists.
So an admin could set a per-client target, see it save, and then read a report
that marked the client At Risk against a different number. Four of the five
summary literals disagreed with what the product itself stored.

`CLIENT_CONFIG` also has seven `*_target_*` columns. They are deliberately NOT
used here: nothing but their own CRUD schemas reads them, they are per-client
only with no global fallback, and they carry no warning/critical band or
direction. `KPI_THRESHOLD` is keyed per metric, has a real global row, and
carries every field the status column needs.

Resolution matches what `/api/kpi-thresholds` already implements: the global
(`client_id IS NULL`) rows are the base, and a client's own rows override them
per `kpi_key`.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.calculations.alerts import check_threshold_breach
from backend.orm.kpi_threshold import KPIThreshold

#: Status values this module can return. `NO_TARGET` is distinct from the
#: generators' existing "N/A" (a row that reports a raw total and is not
#: evaluated at all) -- this one means the metric IS evaluated against a target,
#: and nobody has configured one.
ON_TARGET = "On Target"
AT_RISK = "At Risk"
WARNING = "Warning"
CRITICAL = "Critical"
URGENT = "Urgent"
NO_TARGET = "No Target"
#: The measurement itself was never recorded -- distinct from NO_TARGET (the
#: number is real, nobody said what it should be) and from "N/A" (a raw total that
#: is not evaluated at all). See backend/reports/measurements.py.
NOT_RECORDED = "Not Recorded"

#: Statuses that must not be painted as an alarm by a renderer's colour rule.
#: Both mean "no judgement was made" rather than "the judgement is bad".
UNEVALUATED_STATUSES = ("N/A", NO_TARGET, NOT_RECORDED)

_BREACH_STATUS = {"warning": WARNING, "critical": CRITICAL, "urgent": URGENT}


@dataclass(frozen=True)
class Target:
    """One configured KPI target, as the report needs to read it.

    No `unit`: `KPI_THRESHOLD` stores one, but each generator already hardcodes
    the matching number format beside the cell it writes (`'0.0"%"'`, `"#,##0"`),
    so presentation belongs to the caller. Carrying the column here while the
    format stayed hardcoded would be half a decision, and nothing read it.
    """

    value: float
    warning: Optional[float]
    critical: Optional[float]
    higher_is_better: bool


def _as_target(row: KPIThreshold) -> Target:
    return Target(
        value=float(row.target_value),
        warning=float(row.warning_threshold) if row.warning_threshold is not None else None,
        critical=float(row.critical_threshold) if row.critical_threshold is not None else None,
        # A Y/N CHAR column, not a boolean -- and defaulting a missing value to
        # "higher is better" matches the column's own server default.
        # A NULL direction defaults to "higher is better", matching the column's
        # own default. Inheritance across the global-to-client boundary is
        # `_merge`'s job, and it reads the raw row rather than this conversion --
        # so this default applies only where there is nothing to inherit from.
        higher_is_better=(row.higher_is_better or "Y").upper() == "Y",
    )


def _merge(base: Target, row: KPIThreshold) -> Target:
    """`row`'s values over `base`'s, field by field.

    Wholesale replacement made a target-only client row silently erase the global
    warning/critical bands, so the same measured number read "At Risk" for one
    metric and "Urgent" for another. The admin UI cannot set bands per-client at
    all -- one numeric field per KPI -- so inheritance is the only mechanism by
    which a client's bands can exist, and `update_kpi_thresholds` creates client
    rows with bands of None as well, so this is not merely the seeder's shape.

    Keyed on `is None`, never truthiness: a band of 0 is a legitimate
    configuration, and reading it as "unset" would inherit straight over it --
    the same defect `check_threshold_breach` carried.

    `higher_is_better` is inherited for a sharper reason than the bands: the
    column is nullable, and defaulting a NULL to "higher is better" would invert
    the verdict for every lower-is-better metric (a PPM of 2000 against a target
    of 500 would read On Target). Reads the RAW row, not `_as_target`, precisely
    so that conversion's own default cannot pre-empt the inheritance.
    """
    return Target(
        value=float(row.target_value),
        warning=_first_set(row.warning_threshold, base.warning),
        critical=_first_set(row.critical_threshold, base.critical),
        higher_is_better=(
            base.higher_is_better if row.higher_is_better is None else row.higher_is_better.upper() == "Y"
        ),
    )


def _first_set(incoming: Optional[float], inherited: Optional[float]) -> Optional[float]:
    return inherited if incoming is None else float(incoming)


def load_targets(db: Session, client_id: Optional[str]) -> Dict[str, Target]:
    """`kpi_key` -> `Target` for one client, or for the global defaults.

    `client_id=None` means an all-clients report, which has no single client's
    overrides to apply and so reads the global configuration alone.

    A NULL `higher_is_better` on a client row inherits the global row's direction
    rather than defaulting -- defaulting would invert the verdict for every
    lower-is-better metric. (Not reachable through the ORM, whose column default
    supplies "Y"; reachable by direct SQL.)

    TWO PASSES, not one. A client's row merges over the global row per field (see
    `_merge`), but two GLOBAL rows for one key must NOT merge into each other --
    that would splice a target from one row with bands from another and produce a
    threshold nobody configured. Within a scope the highest `threshold_id` simply
    wins; merging happens only across the global-to-client boundary.

    The `threshold_id` ordering is load-bearing rather than tidiness: both
    dialects exclude NULLs from a UNIQUE index, so UNIQUE(client_id, kpi_key)
    does NOT prevent two global rows sharing a kpi_key. Nothing creates a
    duplicate today -- the PUT route updates in place and migration 0009 inserts
    if absent -- but the schema permits it, and a nondeterministic target is
    worse than a wrong one.
    """
    query = db.query(KPIThreshold)
    if client_id:
        query = query.filter(or_(KPIThreshold.client_id.is_(None), KPIThreshold.client_id == client_id))
    else:
        query = query.filter(KPIThreshold.client_id.is_(None))

    rows = query.all()
    by_id = sorted(rows, key=lambda r: r.threshold_id)

    resolved: Dict[str, Target] = {}
    for row in (r for r in by_id if r.client_id is None):
        resolved[row.kpi_key] = _as_target(row)
    for row in (r for r in by_id if r.client_id is not None):
        base = resolved.get(row.kpi_key)
        resolved[row.kpi_key] = _as_target(row) if base is None else _merge(base, row)

    return resolved


def status_for(value: float, target: Optional[Target]) -> str:
    """The summary column's verdict for one measured value.

    Two questions, composed, because neither answers the column on its own:

    * Does it meet target? A direction-aware comparison -- which is all the
      column has ever claimed to show.
    * How bad is a miss? `check_threshold_breach`, the product's own breach
      definition, reused rather than re-derived so a report and an alert cannot
      disagree about the same number.

    The composition is load-bearing. `check_threshold_breach` answers "should
    this raise an alarm", and with no bands configured it returns None for
    anything above half of target -- so asked alone it would call an efficiency
    of 50% against an 85% target "no breach". Conversely a bare `>= target` test
    cannot tell a near miss from a collapse. Asking both gives a scale that uses
    every configured field and invents none.
    """
    if target is None:
        return NO_TARGET

    meets = value >= target.value if target.higher_is_better else value <= target.value
    if meets:
        return ON_TARGET

    # Only escalate past At Risk on a band the admin actually configured. With
    # no bands, check_threshold_breach's one unconditional rule (the
    # half-of-target ratio) would still fire, and promoting that into the report
    # would be inventing a severity nobody set -- the same class of invention
    # this module exists to remove.
    if target.warning is None and target.critical is None:
        return AT_RISK

    breach = check_threshold_breach(
        Decimal(str(value)),
        Decimal(str(target.value)),
        Decimal(str(target.warning)) if target.warning is not None else None,
        Decimal(str(target.critical)) if target.critical is not None else None,
        target.higher_is_better,
    )
    return _BREACH_STATUS.get(breach or "", AT_RISK)
