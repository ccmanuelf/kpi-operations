"""
CRUD query operations for WIP hold tracking
List, filter, and lookup operations
"""

from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date

from backend.schemas.hold_entry import HoldEntry as WIPHold, HoldStatus
from backend.models.hold import WIPHoldResponse
from backend.middleware.client_auth import verify_client_access, build_client_filter_clause
from backend.schemas.user import User


def get_wip_holds(
    db: Session,
    current_user: User,
    skip: int = 0,
    limit: int = 100,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    work_order_id: Optional[str] = None,
    released: Optional[bool] = None,
    hold_reason_category: Optional[str] = None,
) -> List[WIPHold]:
    """Get WIP holds with filters - uses HOLD_ENTRY schema"""
    query = db.query(WIPHold)

    # Apply client filtering based on user role
    client_filter = build_client_filter_clause(current_user, WIPHold.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    # Additional client filter if provided
    if client_id:
        query = query.filter(WIPHold.client_id == client_id)

    if start_date:
        query = query.filter(WIPHold.hold_date >= start_date)

    if end_date:
        query = query.filter(WIPHold.hold_date <= end_date)

    if work_order_id:
        query = query.filter(WIPHold.work_order_id == work_order_id)

    if released is not None:
        if released:
            query = query.filter(WIPHold.hold_status == HoldStatus.RESUMED)
        else:
            query = query.filter(WIPHold.hold_status == HoldStatus.ON_HOLD)

    if hold_reason_category:
        query = query.filter(WIPHold.hold_reason_category == hold_reason_category)

    return query.order_by(WIPHold.hold_date.desc()).offset(skip).limit(limit).all()


def get_holds_by_work_order(db: Session, work_order_number: str, current_user: User) -> List[WIPHoldResponse]:
    """
    Get all holds for a specific work order
    P2-001: Helper function for WIP aging

    Args:
        db: Database session
        work_order_number: Work order number
        current_user: Authenticated user

    Returns:
        List of WIPHoldResponse for the work order
    """
    query = db.query(WIPHold).filter(WIPHold.work_order_id == work_order_number)

    # Apply client filtering
    client_filter = build_client_filter_clause(current_user, WIPHold.client_id)
    if client_filter is not None:
        query = query.filter(client_filter)

    holds = query.order_by(WIPHold.hold_date.desc()).all()

    return [WIPHoldResponse.model_validate(h) for h in holds]
