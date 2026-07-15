"""Data-driven cause analysis for out-of-control KPI trend points (SP2).

Each driver takes an open Session, an optional client filter, and a single day,
and returns the dominant contributing factor for that day as a CauseResult, or
None when there is no operational data behind the metric that day.

All date filtering uses datetime.combine bounds (portable SQLite + MariaDB); no
SQLite-only date functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.quality_entry import QualityEntry
from backend.orm.defect_detail import DefectDetail
from backend.orm.attendance_entry import AttendanceEntry
from backend.orm.work_order import WorkOrder
from backend.orm.hold_entry import HoldEntry, HoldStatus
from backend.orm.production_entry import ProductionEntry


@dataclass
class CauseResult:
    kind: str  # "downtime"|"defect"|"absence"|"lateOrders"|"hold"|"component"
    factor: str
    value: float | None
    unit: str
    share: float | None


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    return datetime.combine(day, datetime.min.time()), datetime.combine(day, datetime.max.time())


def top_downtime_reason(session: Session, client_id: str | None, day: date) -> CauseResult | None:
    start, end = _day_bounds(day)
    q = session.query(
        DowntimeEntry.downtime_reason,
        func.sum(DowntimeEntry.downtime_duration_minutes).label("mins"),
    ).filter(DowntimeEntry.shift_date >= start, DowntimeEntry.shift_date <= end)
    if client_id:
        q = q.filter(DowntimeEntry.client_id == client_id)
    rows = (
        q.group_by(DowntimeEntry.downtime_reason)
        .order_by(func.sum(DowntimeEntry.downtime_duration_minutes).desc())
        .all()
    )
    if not rows:
        return None
    total = sum(float(r.mins or 0) for r in rows)
    top = rows[0]
    top_val = float(top.mins or 0)
    return CauseResult(
        kind="downtime",
        factor=str(top.downtime_reason),
        value=top_val,
        unit="min",
        share=(top_val / total if total > 0 else None),
    )


def top_defect_type(session: Session, client_id: str | None, day: date) -> CauseResult | None:
    start, end = _day_bounds(day)
    q = (
        session.query(DefectDetail.defect_type, func.sum(DefectDetail.defect_count).label("cnt"))
        .join(QualityEntry, DefectDetail.quality_entry_id == QualityEntry.quality_entry_id)
        .filter(QualityEntry.shift_date >= start, QualityEntry.shift_date <= end)
    )
    if client_id:
        q = q.filter(DefectDetail.client_id_fk == client_id)
    rows = q.group_by(DefectDetail.defect_type).order_by(func.sum(DefectDetail.defect_count).desc()).all()
    if not rows:
        return None
    total = sum(int(r.cnt or 0) for r in rows)
    top = rows[0]
    top_val = float(int(top.cnt or 0))
    return CauseResult(
        kind="defect",
        factor=str(top.defect_type),
        value=top_val,
        unit="count",
        share=(top_val / total if total > 0 else None),
    )


def top_absence_type(session: Session, client_id: str | None, day: date) -> CauseResult | None:
    start, end = _day_bounds(day)
    # Group by the RAW enum column — never coalesce a string literal through an
    # Enum-typed column, or SQLAlchemy decodes the literal through the enum's
    # result-processor and raises LookupError when any absent row has a NULL
    # absence_type (a legitimate case: is_absent=1 with no reason recorded).
    q = session.query(
        AttendanceEntry.absence_type.label("reason"),
        func.count().label("cnt"),
    ).filter(
        AttendanceEntry.shift_date >= start,
        AttendanceEntry.shift_date <= end,
        AttendanceEntry.is_absent == 1,
    )
    if client_id:
        q = q.filter(AttendanceEntry.client_id == client_id)
    rows = q.group_by(AttendanceEntry.absence_type).order_by(func.count().desc()).all()
    if not rows:
        return None
    total = sum(int(r.cnt) for r in rows)
    top = rows[0]
    top_val = float(int(top.cnt))
    # Resolve the label in Python: NULL -> "Unspecified"; AbsenceType member ->
    # its .value (e.g. "MEDICAL_LEAVE"); a raw string (some drivers) -> as-is.
    raw = top.reason
    if raw is None:
        factor = "Unspecified"
    elif hasattr(raw, "value"):
        factor = raw.value
    else:
        factor = str(raw)
    return CauseResult(
        kind="absence",
        factor=factor,
        value=top_val,
        unit="count",
        share=(top_val / total if total > 0 else None),
    )


def late_work_orders(session: Session, client_id: str | None, day: date) -> CauseResult | None:
    start, end = _day_bounds(day)
    q = session.query(func.count(WorkOrder.work_order_id)).filter(
        WorkOrder.required_date >= start,
        WorkOrder.required_date <= end,
        or_(
            WorkOrder.actual_delivery_date.is_(None),
            WorkOrder.actual_delivery_date > WorkOrder.required_date,
        ),
    )
    if client_id:
        q = q.filter(WorkOrder.client_id == client_id)
    late = int(q.scalar() or 0)
    if late == 0:
        return None
    return CauseResult(kind="lateOrders", factor=str(late), value=float(late), unit="count", share=None)


def oldest_active_hold(session: Session, client_id: str | None, day: date) -> CauseResult | None:
    _, end = _day_bounds(day)
    q = session.query(HoldEntry).filter(
        HoldEntry.hold_status == HoldStatus.ON_HOLD,
        HoldEntry.hold_date.isnot(None),
        HoldEntry.hold_date <= end,
        or_(HoldEntry.resume_date.is_(None), HoldEntry.resume_date > end),
    )
    if client_id:
        q = q.filter(HoldEntry.client_id == client_id)
    hold = q.order_by(HoldEntry.hold_date.asc()).first()
    if hold is None or hold.hold_date is None:
        return None
    age_days = (day - hold.hold_date.date()).days
    return CauseResult(
        kind="hold",
        factor=str(hold.hold_reason or "Unspecified"),
        value=float(age_days),
        unit="days",
        share=None,
    )


def oee_dominant_loss(session: Session, client_id: str | None, day: date) -> CauseResult | None:
    """Decompose the day's OEE (mirroring /oee/trend math) and return the dominant loss's driver."""
    start, end = _day_bounds(day)

    perf_q = session.query(
        func.avg(ProductionEntry.performance_percentage).label("perf"),
        func.count(ProductionEntry.production_entry_id).label("entries"),
    ).filter(ProductionEntry.shift_date >= start, ProductionEntry.shift_date <= end)
    if client_id:
        perf_q = perf_q.filter(ProductionEntry.client_id == client_id)
    pr = perf_q.one()
    entries = int(pr.entries or 0)
    if entries == 0:
        return None
    performance = float(pr.perf) if pr.perf else 95.0

    qual_q = session.query(
        func.sum(QualityEntry.units_passed).label("passed"),
        func.sum(QualityEntry.units_inspected).label("inspected"),
    ).filter(QualityEntry.shift_date >= start, QualityEntry.shift_date <= end)
    if client_id:
        qual_q = qual_q.filter(QualityEntry.client_id == client_id)
    qr = qual_q.one()
    quality = (float(qr.passed) / float(qr.inspected) * 100) if qr.inspected and qr.inspected > 0 else 97.0

    dt_q = session.query(func.sum(DowntimeEntry.downtime_duration_minutes).label("mins")).filter(
        DowntimeEntry.shift_date >= start, DowntimeEntry.shift_date <= end
    )
    if client_id:
        dt_q = dt_q.filter(DowntimeEntry.client_id == client_id)
    downtime_mins = dt_q.scalar()
    downtime = float(downtime_mins) / 60 if downtime_mins else 0.0

    scheduled = entries * 8
    availability = ((scheduled - downtime) / scheduled * 100) if scheduled > 0 else 90.0

    losses = {
        "availability": 100 - min(availability, 100),
        "performance": 100 - min(performance, 100),
        "quality": 100 - min(quality, 100),
    }
    name, loss = max(losses.items(), key=lambda kv: kv[1])
    if loss <= 0:
        return None

    if name == "availability":
        return top_downtime_reason(session, client_id, day) or CauseResult(
            kind="component", factor="availability", value=None, unit="", share=None
        )
    if name == "quality":
        return top_defect_type(session, client_id, day) or CauseResult(
            kind="component", factor="quality", value=None, unit="", share=None
        )
    return CauseResult(kind="component", factor="performance", value=None, unit="", share=None)
