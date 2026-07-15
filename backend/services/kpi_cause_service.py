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

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.orm.downtime_entry import DowntimeEntry
from backend.orm.quality_entry import QualityEntry
from backend.orm.defect_detail import DefectDetail
from backend.orm.attendance_entry import AttendanceEntry


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
    label = func.coalesce(AttendanceEntry.absence_type, "Unspecified").label("reason")
    q = session.query(label, func.count().label("cnt")).filter(
        AttendanceEntry.shift_date >= start,
        AttendanceEntry.shift_date <= end,
        AttendanceEntry.is_absent == 1,
    )
    if client_id:
        q = q.filter(AttendanceEntry.client_id == client_id)
    rows = q.group_by(label).order_by(func.count().desc()).all()
    if not rows:
        return None
    total = sum(int(r.cnt) for r in rows)
    top = rows[0]
    top_val = float(int(top.cnt))
    reason = top.reason.value if hasattr(top.reason, "value") else top.reason
    return CauseResult(
        kind="absence",
        factor=str(reason),
        value=top_val,
        unit="count",
        share=(top_val / total if total > 0 else None),
    )
