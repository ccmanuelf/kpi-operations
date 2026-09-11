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

#: Statuses that must not be painted as an alarm by a renderer's colour rule.
#: Both mean "no judgement was made" rather than "the judgement is bad".
UNEVALUATED_STATUSES = ("N/A", NO_TARGET)

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
        higher_is_better=(row.higher_is_better or "Y").upper() == "Y",
    )


def load_targets(db: Session, client_id: Optional[str]) -> Dict[str, Target]:
    """`kpi_key` -> `Target` for one client, or for the global defaults.

    `client_id=None` means an all-clients report, which has no single client's
    overrides to apply and so reads the global configuration alone.
    """
    query = db.query(KPIThreshold)
    if client_id:
        query = query.filter(or_(KPIThreshold.client_id.is_(None), KPIThreshold.client_id == client_id))
    else:
        query = query.filter(KPIThreshold.client_id.is_(None))

    # Global first, then the client's own rows overwrite them key by key. Sorted
    # here rather than in SQL so the ordering is the data's and not the query
    # plan's -- NULLs do sort before a non-null client_id on both dialects, but
    # relying on that is relying on something neither engine promises.
    #
    # `threshold_id` is the tiebreak, and it is load-bearing rather than tidiness:
    # both dialects exclude NULLs from a UNIQUE index, so
    # UNIQUE(client_id, kpi_key) does NOT prevent two GLOBAL rows sharing a
    # kpi_key. Without a total order, which of them a report reads would depend
    # on the engine. (Nothing creates a duplicate today -- the PUT route updates
    # in place and this migration inserts if absent -- but the schema permits it,
    # and a nondeterministic target is worse than a wrong one.)
    resolved: Dict[str, Target] = {}
    for row in sorted(query.all(), key=lambda r: (r.client_id is not None, r.threshold_id)):
        resolved[row.kpi_key] = _as_target(row)
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
