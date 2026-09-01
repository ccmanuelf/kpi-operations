"""Alert events -> rows.

All three alert tables use STRING primary keys the stream already carries, so
unlike the capacity writers there are no integer allocators here: the emitter
mints ids in the app's own `ALT-YYYYMMDD-XXXXXXXX` shape and the writer uses
them verbatim.

ALERT_HISTORY.alert_id is a ForeignKey to ALERT.alert_id, and both come from
the same emitter in the same pass, so the child cannot reference an alert the
stream never raised.
"""

from __future__ import annotations

from typing import Callable, Dict, Type

from backend.seed import events as ev
from backend.seed.identity import IdMap, IntPkAllocator
from backend.seed.materialize import RowSink


def handle(event: ev.Event, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> bool:
    handler = _HANDLERS.get(type(event))
    if handler is None:
        return False
    handler(event, sink, ids, allocators)
    return True


def _alert_configured(e: ev.AlertConfigured, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> None:
    sink.add(
        "ALERT_CONFIG",
        {
            "config_id": e.config_key,
            "client_id": e.client_id,
            "alert_type": e.alert_type,
            "enabled": e.enabled,
            "warning_threshold": e.warning_threshold,
            "critical_threshold": e.critical_threshold,
            "notification_email": e.notification_email,
            "notification_sms": e.notification_sms,
            "check_frequency_minutes": e.check_frequency_minutes,
            "created_at": e.at,
            # Explicit, like every capacity table: the column carries
            # `server_default=func.now()`, so omitting it stamps the row with
            # the wall clock inside a back-dated seed.
            "updated_at": e.at,
        },
    )


def _alert_raised(e: ev.AlertRaised, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]) -> None:
    sink.add(
        "ALERT",
        {
            "alert_id": e.alert_key,
            "category": e.category,
            "severity": e.severity,
            "status": e.status,
            "title": e.title,
            "message": e.message,
            "recommendation": e.recommendation,
            "client_id": e.client_id,
            "kpi_key": e.kpi_key,
            "work_order_id": e.work_order_id,
            "current_value": e.current_value,
            "threshold_value": e.threshold_value,
            "predicted_value": e.predicted_value,
            "confidence": e.confidence,
            "alert_metadata": dict(e.alert_metadata),
            "created_at": e.at,
            "acknowledged_at": e.acknowledged_at,
            "acknowledged_by": e.acknowledged_by,
            "resolved_at": e.resolved_at,
            "resolved_by": e.resolved_by,
            "resolution_notes": e.resolution_notes,
        },
    )


def _prediction_recorded(
    e: ev.AlertPredictionRecorded, sink: RowSink, ids: IdMap, allocators: Dict[str, IntPkAllocator]
) -> None:
    sink.add(
        "ALERT_HISTORY",
        {
            "history_id": e.history_key,
            "alert_id": e.alert_key,
            "predicted_value": e.predicted_value,
            "actual_value": e.actual_value,
            "prediction_date": e.prediction_date,
            "actual_date": e.actual_date,
            "was_accurate": e.was_accurate,
            "error_percent": e.error_percent,
            "created_at": e.at,
        },
    )


_HANDLERS: Dict[Type[ev.Event], Callable] = {
    ev.AlertConfigured: _alert_configured,
    ev.AlertRaised: _alert_raised,
    ev.AlertPredictionRecorded: _prediction_recorded,
}
