"""The alert board: configuration, live alerts, and prediction accuracy.

Three tables the alerts section reads and nothing wrote. The dashboard groups
by severity and by category, so an alert board holding one row demonstrates a
list rather than a board -- these span both axes, and all three statuses, so
the counts, the filters and the acknowledge/resolve workflow all have
something to show.

VOCABULARY IS THE APP'S OWN. `routes/alerts/generate.py` writes categories
`otd`, `hold` and `capacity` with `kpi_key`s `otd` and `hold_approval`, and
ids shaped `ALT-YYYYMMDD-XXXXXXXX`. Seeded rows use the same, so a seeded
alert is indistinguishable from a generated one instead of a row that merely
fills the table.

Emitted AFTER the work orders, because the OTD alerts reference real ones. An
alert pointing at a work order that does not exist is worse than no alert: it
renders, and its link goes nowhere.
"""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta
from typing import Callable, List, Tuple

from backend.seed.emitters_master import ClientSetup
from backend.seed.events import AlertConfigured, AlertPredictionRecorded, AlertRaised
from backend.seed.profiles import Profile
from backend.seed.scenarios import USERS, ClientScenario

#: Who acknowledges and who resolves. Resolved from the roster, not typed:
#: both columns are ForeignKeys to USER.user_id.
ACKNOWLEDGED_BY = next(u.user_id for u in USERS if u.role == "supervisor")
RESOLVED_BY = next(u.user_id for u in USERS if u.role == "poweruser")

#: One config per alert type the app checks, with the thresholds a plant would
#: actually set. `enabled=False` on one of them deliberately: a configuration
#: screen where every row is on never shows what a disabled row looks like.
ALERT_CONFIGS = (
    ("otd", True, 90.0, 80.0, True, False, 60),
    ("quality", True, 97.0, 94.0, True, False, 60),
    ("efficiency", True, 85.0, 75.0, True, False, 120),
    ("capacity", True, 90.0, 100.0, True, True, 30),
    ("hold_approval", False, 48.0, 72.0, False, False, 240),
)

#: The board itself. Spread across category, severity and status so the
#: dashboard's two groupings and the acknowledge/resolve workflow all have
#: rows. `wo_offset` picks a work order from the client's own book; None means
#: the alert is not about one order (a hold or capacity alert never is).
#:
#: (category, severity, status, kpi_key, wo_offset, title, message, recommendation)
ALERT_SPECS = (
    (
        "otd",
        "critical",
        "active",
        "otd",
        0,
        "Order at risk of missing its date",
        "Completion is tracking below plan with the required date inside two weeks.",
        "Re-sequence onto the fastest line, or raise the shortfall with the customer today.",
    ),
    (
        "otd",
        "warning",
        "active",
        "otd",
        3,
        "Order behind plan",
        "Completion is behind the planned curve but the date is still recoverable.",
        "Watch the next two shifts before committing overtime.",
    ),
    (
        "otd",
        "warning",
        "acknowledged",
        "otd",
        7,
        "Order behind plan",
        "Completion is behind the planned curve on a second order for the same style.",
        "Acknowledged by the supervisor; recovery plan agreed for the coming week.",
    ),
    (
        "capacity",
        "urgent",
        "active",
        "capacity",
        None,
        "Line utilisation above committed capacity",
        "A line is scheduled beyond the hours its calendar and crew can deliver.",
        "Add the overtime scenario, or move work to a line with slack.",
    ),
    (
        "capacity",
        "info",
        "resolved",
        "capacity",
        None,
        "Capacity restored after schedule change",
        "Utilisation returned inside the committed envelope after work was re-sequenced.",
        None,
    ),
    (
        "hold",
        "critical",
        "active",
        "hold_approval",
        None,
        "Hold awaiting approval past its window",
        "A hold has been open beyond the approval window agreed with the customer.",
        "Escalate to the area leader; the order cannot move while the hold stands.",
    ),
    (
        "hold",
        "warning",
        "resolved",
        "hold_approval",
        None,
        "Hold approved",
        "A hold that breached its approval window has since been approved and closed.",
        None,
    ),
    (
        "quality",
        "info",
        "acknowledged",
        "quality",
        None,
        "First pass yield below target",
        "FPY sat under target for a full week without breaching the critical threshold.",
        "Review the top defect code with the line before it becomes a trend.",
    ),
)


def emit_alerts(
    emit: Callable[..., None],
    scenario: ClientScenario,
    profile: Profile,
    setup: ClientSetup,
    received: List[Tuple[date, str, int]],
    as_of: date,
) -> None:
    cid = scenario.client_id

    # Local generator, like the capacity emitter: drawing from the stream's
    # shared rng here would shift every draw made after it and silently
    # re-roll the operations data for every client.
    rng = random.Random(f"{cid}-alerts")

    # Alerts are raised DURING the active window, not at setup: an alert board where
    # every row was created on day one reads as fixture data. They are stamped
    # across the final fortnight, newest last.
    def stamp(days_before: int) -> datetime:
        return datetime.combine(as_of - timedelta(days=days_before), time(7, 30))

    def alert_id(when: datetime) -> str:
        # The app's own format, `ALT-YYYYMMDD-XXXXXXXX`. Deterministic here
        # because the seeder cannot call uuid4 -- the purity guard forbids it,
        # and a seed that produced different ids each run would not be
        # reproducible.
        return f"ALT-{when:%Y%m%d}-{rng.getrandbits(32):08X}"

    for alert_type, enabled, warn, crit, email, sms, freq in ALERT_CONFIGS:
        emit(
            AlertConfigured,
            datetime.combine(setup.activity_start, time(5, 0)),
            cid,
            config_key=f"{cid}-ALERTCFG-{alert_type}",
            alert_type=alert_type,
            enabled=enabled,
            warning_threshold=warn,
            critical_threshold=crit,
            notification_email=email,
            notification_sms=sms,
            check_frequency_minutes=freq,
        )

    work_order_ids = [wo_id for _day, wo_id, _ops in received]

    for i, (category, severity, status, kpi_key, wo_offset, title, message, recommendation) in enumerate(ALERT_SPECS):
        raised_at = stamp(13 - i)
        key = alert_id(raised_at)
        work_order_id = (
            work_order_ids[wo_offset % len(work_order_ids)] if wo_offset is not None and work_order_ids else None
        )

        acknowledged_at = raised_at + timedelta(hours=3) if status in ("acknowledged", "resolved") else None
        resolved_at = raised_at + timedelta(hours=27) if status == "resolved" else None

        current = round(rng.uniform(62.0, 88.0), 2)
        threshold = 90.0 if category == "otd" else 95.0
        emit(
            AlertRaised,
            raised_at,
            cid,
            alert_key=key,
            category=category,
            severity=severity,
            status=status,
            title=title,
            message=message,
            recommendation=recommendation,
            kpi_key=kpi_key,
            work_order_id=work_order_id,
            current_value=current,
            threshold_value=threshold,
            # Only the forward-looking categories carry a prediction; a
            # confidence on a hold alert would imply a model that does not
            # exist.
            predicted_value=round(current - rng.uniform(1.0, 6.0), 2) if category == "otd" else None,
            confidence=round(rng.uniform(0.62, 0.94), 2) if category == "otd" else None,
            alert_metadata={"source": "seed", "category": category},
            acknowledged_at=acknowledged_at,
            acknowledged_by=ACKNOWLEDGED_BY if acknowledged_at else None,
            resolved_at=resolved_at,
            resolved_by=RESOLVED_BY if resolved_at else None,
            resolution_notes=("Recovered after re-sequencing." if resolved_at else None),
        )

        # Accuracy ledger, for the predictive category only. Both outcomes
        # appear: a history where every prediction was right shows a column,
        # not a track record.
        if category == "otd":
            predicted = round(current - rng.uniform(1.0, 6.0), 2)
            actual = round(predicted + rng.uniform(-4.0, 4.0), 2)
            error = abs(actual - predicted) / predicted * 100 if predicted else 0.0
            emit(
                AlertPredictionRecorded,
                raised_at + timedelta(days=2),
                cid,
                history_key=f"{key}-H1",
                alert_key=key,
                predicted_value=predicted,
                actual_value=actual,
                prediction_date=raised_at,
                actual_date=raised_at + timedelta(days=2),
                was_accurate=error <= 5.0,
                error_percent=round(error, 2),
            )
