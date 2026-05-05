"""Cross-reference endpoints: Capacity Orders -> Work Orders (Task 3.1)"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Any, List

from backend.utils.logging_utils import get_module_logger
from backend.database import get_db
from backend.auth.jwt import get_current_user
from backend.orm.user import User
from backend.dependencies import PaginationParams
from backend.schemas.work_order import WorkOrderResponse

logger = get_module_logger(__name__)

work_order_bridge_router = APIRouter()


@work_order_bridge_router.get("/orders/{order_id}/work-orders", response_model=List[WorkOrderResponse])
def get_capacity_order_work_orders(
    order_id: int,
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Get all work orders linked to a capacity order."""
    from backend.services.work_order_service import list_orders_by_capacity_order

    logger.info(
        "Fetching work orders for capacity order %d (skip=%d, limit=%d)", order_id, pagination.skip, pagination.limit
    )
    return list_orders_by_capacity_order(db, order_id, current_user, pagination.skip, pagination.limit)
