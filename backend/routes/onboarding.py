"""
Onboarding API Routes

Provides a lightweight status endpoint that checks which onboarding steps
have been completed for the current client. Used by the frontend Getting
Started checklist to show operational setup progress.

All queries are multi-tenant isolated via client_id.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.auth.jwt import get_current_user
from backend.database import get_db
from backend.middleware.client_auth import verify_client_access
from backend.orm.capacity.orders import CapacityOrder
from backend.orm.product import Product
from backend.orm.production_entry import ProductionEntry
from backend.orm.shift import Shift
from backend.orm.user import User
from backend.orm.work_order import WorkOrder
from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


def _resolve_client_id(
    client_id: Optional[str],
    current_user: User,
) -> str:
    """
    Determine the effective client_id from the query parameter or the user's
    assigned client.  Admin/poweruser roles must specify client_id explicitly.

    Raises:
        HTTPException 400 if client_id cannot be determined.
    """
    if client_id:
        return client_id

    # Fall back to user's assigned client (operators / leaders with a single client)
    if current_user.client_id_assigned:
        # If comma-separated, take the first one
        first_client = current_user.client_id_assigned.split(",")[0].strip()
        if first_client:
            return first_client

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="client_id query parameter is required for this user role",
    )


@router.get("/status")
def get_onboarding_status(
    client_id: Optional[str] = Query(None, description="Client ID to check onboarding for"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Check which onboarding steps are completed for the given client.

    Returns a dictionary of step names mapped to boolean completion status,
    along with aggregate counts.
    """
    cid = _resolve_client_id(client_id, current_user)

    # Verify the user has access to this client's data
    # verify_client_access raises ClientAccessError (HTTP 403) on denial
    verify_client_access(current_user, cid)

    logger.info(
        "Checking onboarding status for client_id=%s by user=%s",
        cid,
        current_user.user_id,
    )

    steps = {
        "shifts_configured": db.query(Shift).filter(Shift.client_id == cid).count() > 0,
        "products_added": db.query(Product).filter(Product.client_id == cid).count() > 0,
        "work_orders_created": db.query(WorkOrder).filter(WorkOrder.client_id == cid).count() > 0,
        "production_data_entered": (
            db.query(ProductionEntry).filter(ProductionEntry.client_id == cid).count() > 0
        ),
        "capacity_plan_created": (
            db.query(CapacityOrder).filter(CapacityOrder.client_id == cid).count() > 0
        ),
    }

    completed_count = sum(1 for v in steps.values() if v)
    total_steps = len(steps)

    logger.info(
        "Onboarding status for client_id=%s: %d/%d steps completed",
        cid,
        completed_count,
        total_steps,
    )

    return {
        "steps": steps,
        "completed_count": completed_count,
        "total_steps": total_steps,
        "all_complete": all(steps.values()),
    }
