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

#: Largest OFFSET both engines accept. Above it the driver raises rather than
#: returning an empty page: SQLite gives
#: `OverflowError: Python int too large to convert to SQLite INTEGER` (verified
#: at exactly 2**63, on both endpoints), and MariaDB's LIMIT/OFFSET is
#: BIGINT UNSIGNED. `offset` had no upper bound, so ?offset=9223372036854775808
#: was accepted by FastAPI and 500'd — the same defect class as the
#: `end_date=9999-12-31` overflow below: an unhandled crash on accepted input.
#:
#: This bound is a crash guard ONLY. It is the exact largest value that already
#: worked, so no request that previously succeeded changes; what changes is
#: that garbage now gets a 422 instead of a 500. It deliberately does NOT
#: address deep-paging COST, which was triaged separately as ship-as-is
#: (admin-only, negligible at projected volume).
_MAX_SQL_OFFSET = 2**63 - 1

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
    """Exclusive upper bound for an INCLUSIVE end date, on a DateTime column.

    occurred_at is a DateTime, so an inclusive end date must compare against
    the NEXT midnight. Comparing against the date at midnight silently drops
    everything recorded during the final day.

    Naive UTC, deliberately: AUDIT_ENTRY.occurred_at is stored naive (see
    backend/orm/audit_entry.py — neither SQLite nor pymysql/MariaDB retain a
    UTC offset on a DATETIME column), so it must be filtered as naive UTC too.
    A tz-aware bound happens to compare correctly on SQLite but is not safe on
    MariaDB. datetime.max is likewise naive, so the clamp below keeps that
    contract.

    date.max has no next midnight. `end_date` is a plain Optional[date], so
    FastAPI accepts ?end_date=9999-12-31 as valid input — and 9999-12-31 IS a
    storable MariaDB DATETIME day, not a nonsense value to reject — but
    `datetime.combine(date.max, time.min) + timedelta(days=1)` raises
    `OverflowError: date value out of range`, which nothing catches: an
    unhandled 500 on accepted input. Clamping to datetime.max is the correct
    answer, not merely a crash guard: an inclusive end bound of date.max
    excludes nothing that can exist.

    The one value the clamped bound excludes is occurred_at == datetime.max
    exactly (9999-12-31 23:59:59.999999), because the comparison stays `<`.
    That row cannot exist: MariaDB's DATETIME here has whole-second precision
    (max 9999-12-31 23:59:59), and the writer stamps
    `datetime.now(tz=utc)`, which never reaches it.
    """
    if value >= date.max:
        return datetime.max
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
    offset: int = Query(0, ge=0, le=_MAX_SQL_OFFSET),
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
    offset: int = Query(0, ge=0, le=_MAX_SQL_OFFSET),
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
