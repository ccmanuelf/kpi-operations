"""
Audit Trail API Routes
Admin-only reads over the entity-level change trail.
"""

from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_admin
from backend.database import get_db
from backend.orm.audit_entry import AuditEntry
from backend.orm.user import User
from backend.schemas.audit import AuditEntryResponse, AuditListResponse

router = APIRouter(prefix="/api/audit", tags=["Audit"])

#: Newest first, with a deterministic tiebreaker. Both endpoints MUST use this.
#:
#: occurred_at alone is not a total order on production: it is a plain
#: `DateTime`, which MariaDB renders as DATETIME with WHOLE-SECOND precision.
#: Verified against a live mariadb:11.4 — 20 rows written with 20 distinct
#: microsecond values collapsed to ONE distinct stored occurred_at, and five
#: changes committed in order then came back OLDEST-first, i.e. the exact
#: reverse of this API's documented contract. Rows written in the same second
#: are the normal case, not an edge case: a single flush writes several and a
#: CSV upload writes hundreds per second. SQLite stores full microseconds, so
#: the whole defect is invisible there.
#:
#: entry_id is a monotonic autoincrement PK, so it is both a correct
#: chronological tiebreaker and what makes offset pagination stable (without
#: it, two pages of a tied set can repeat or skip rows).
_NEWEST_FIRST = (AuditEntry.occurred_at.desc(), AuditEntry.entry_id.desc())


def _end_of_day(value: date) -> datetime:
    """Inclusive end bound for a DateTime column.

    occurred_at is a DateTime, so an inclusive end date must compare against
    the NEXT midnight. Comparing against the date at midnight silently drops
    everything recorded during the final day.

    Naive UTC, deliberately: AUDIT_ENTRY.occurred_at is stored naive (see
    backend/orm/audit_entry.py — neither SQLite nor pymysql/MariaDB retain a
    UTC offset on a DATETIME column), so it must be filtered as naive UTC too.
    A tz-aware bound happens to compare correctly on SQLite but is not safe on
    MariaDB.
    """
    return datetime.combine(value, time.min) + timedelta(days=1)


def _trail_started_at(db: Session) -> Optional[datetime]:
    """When the trail begins, or None if empty.

    Shared by both endpoints deliberately: there is no backfill, so "the trail
    starts here" is load-bearing for interpreting an empty result, and it needs
    exactly one definition. Both responses carry it.
    """
    result = db.query(func.min(AuditEntry.occurred_at)).scalar()
    return result if isinstance(result, datetime) else None


@router.get("", response_model=AuditListResponse)
def list_audit_entries(
    table_name: Optional[str] = Query(None),
    actor_user_id: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> AuditListResponse:
    """Recent changes, newest first. Admin only."""
    query = db.query(AuditEntry)

    if table_name:
        query = query.filter(AuditEntry.table_name == table_name)
    if actor_user_id:
        query = query.filter(AuditEntry.actor_user_id == actor_user_id)
    if client_id:
        query = query.filter(AuditEntry.client_id == client_id)
    if start_date:
        # Naive UTC — see _end_of_day for why.
        query = query.filter(AuditEntry.occurred_at >= datetime.combine(start_date, time.min))
    if end_date:
        query = query.filter(AuditEntry.occurred_at < _end_of_day(end_date))

    total = query.count()
    rows = query.order_by(*_NEWEST_FIRST).offset(offset).limit(limit).all()
    trail_started_at = _trail_started_at(db)

    return AuditListResponse(
        entries=[AuditEntryResponse.model_validate(r) for r in rows],
        total=total,
        trail_started_at=trail_started_at,
    )


@router.get("/{table_name}/{record_pk}", response_model=AuditListResponse)
def get_entity_history(
    table_name: str,
    record_pk: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> AuditListResponse:
    """Full change history for one entity. Admin only.

    An empty result is a legitimate answer: the trail has no backfill, so
    changes made before it was deployed were never recorded. trail_started_at
    lets callers tell "nothing happened" apart from "before we were watching".
    """
    query = db.query(AuditEntry).filter(
        AuditEntry.table_name == table_name,
        AuditEntry.record_pk == record_pk,
    )
    total = query.count()
    rows = query.order_by(*_NEWEST_FIRST).offset(offset).limit(limit).all()
    trail_started_at = _trail_started_at(db)

    return AuditListResponse(
        entries=[AuditEntryResponse.model_validate(r) for r in rows],
        total=total,
        trail_started_at=trail_started_at,
    )
