"""Append-only recorder for HOLD_ENTRY.hold_status changes.

Mirrors backend/crud/workflow/transition_log.py. Every hold_status write in
the codebase pairs with a call here, in the same transaction, so the history
cannot disagree with the hold row it describes.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.orm.hold_entry import HoldEntry
from backend.orm.hold_status_transition import HoldStatusTransition
from backend.orm.user import User

_UNSET = object()


def record_hold_transition(
    db: Session,
    hold: HoldEntry,
    to_status: str,
    current_user: Optional[User] = None,
    from_status: object = _UNSET,
    notes: Optional[str] = None,
    transitioned_at: Optional[datetime] = None,
) -> HoldStatusTransition:
    """Record one hold_status change.

    Call BEFORE assigning the new status, so the default `from_status` reads
    the value being replaced. Pass `from_status=None` explicitly for the row
    that records hold creation.

    `transitioned_at` defaults to now. The parameter exists for callers that
    write historical rows; the one production caller that passes an explicit
    instant is `create_wip_hold`'s OPENING transition (stamped at the hold's
    own `hold_date`), so that a back-dated CSV import has its history agree
    with the hold_date it imported, not with the moment the import ran. Every
    other write site records something happening right now, so it takes the
    default.
    """
    resolved_from = hold.hold_status if from_status is _UNSET else from_status

    # Truncate to whole seconds (both the caller-supplied value and the
    # default): MariaDB DATETIME columns are declared without fractional
    # seconds and ROUND rather than truncate on store, so a value like
    # 23:59:59.500000 on day D would be persisted as 00:00:00 on day D+1 --
    # silently moving the transition across a day boundary and making
    # active_as_of attribute the wrong day's status. SQLite stores the
    # microseconds verbatim, so this also keeps the two dialects agreeing.
    # snapshot_cutoff (calculations/wip_aging.py) avoids fractional seconds
    # for this same reason, and the (transitioned_at, transition_id)
    # tie-break in active_as_of already assumes whole-second resolution.
    resolved_at = (transitioned_at or datetime.utcnow()).replace(microsecond=0)

    row = HoldStatusTransition(
        hold_entry_id=hold.hold_entry_id,
        client_id=hold.client_id,
        from_status=resolved_from,
        to_status=to_status,
        transitioned_by=getattr(current_user, "user_id", None),
        transitioned_at=resolved_at,
        notes=notes,
    )
    db.add(row)
    return row
