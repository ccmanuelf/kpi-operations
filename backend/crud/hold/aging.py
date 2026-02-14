"""
CRUD operations for Hold Aging calculations
Batch aging updates and maintenance
"""

from sqlalchemy.orm import Session
from datetime import date, datetime

from backend.schemas.hold_entry import HoldEntry as WIPHold
from backend.middleware.client_auth import build_client_filter_clause
from backend.schemas.user import User


def bulk_update_aging(db: Session, current_user: User) -> int:
    """Update aging for all unreleased holds (batch job)"""
    query = db.query(WIPHold).filter(WIPHold.resume_date.is_(None))

    # Apply client filtering based on user role
    client_filter = build_client_filter_clause(current_user, WIPHold.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    holds = query.all()

    count = 0
    for hold in holds:
        if hold.hold_date:
            # hold_date is a DateTime column — extract date for arithmetic
            hold_date_val = hold.hold_date.date() if isinstance(hold.hold_date, datetime) else hold.hold_date
            aging = (date.today() - hold_date_val).days
            # Note: aging_days is not a persisted column; store on instance only
            hold.aging_days = aging
        count += 1

    db.commit()
    return count
