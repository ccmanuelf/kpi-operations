"""
CRUD operations for Hold Aging calculations
Batch aging updates and maintenance
"""
from sqlalchemy.orm import Session
from datetime import date

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
        hold.aging_days = (date.today() - hold.hold_date).days
        count += 1

    db.commit()
    return count
