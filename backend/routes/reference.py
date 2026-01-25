"""
Reference Data API Routes
Products, shifts, and inference engine endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.database import get_db
from backend.calculations.inference import InferenceEngine
from backend.auth.jwt import get_current_user
from backend.schemas.user import User
from backend.schemas.product import Product
from backend.schemas.shift import Shift


router = APIRouter(
    prefix="/api",
    tags=["Reference Data"]
)


@router.get("/products", response_model=List[dict])
def list_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all active products (authentication required)"""
    products = db.query(Product).filter(Product.is_active == True).all()
    return [
        {
            "product_id": p.product_id,
            "product_code": p.product_code,
            "product_name": p.product_name,
            "ideal_cycle_time": float(p.ideal_cycle_time) if p.ideal_cycle_time else None
        }
        for p in products
    ]


@router.get("/shifts", response_model=List[dict])
def list_shifts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all active shifts (authentication required)"""
    shifts = db.query(Shift).filter(Shift.is_active == True).all()
    return [
        {
            "shift_id": s.shift_id,
            "shift_name": s.shift_name,
            "start_time": s.start_time.strftime("%H:%M"),
            "end_time": s.end_time.strftime("%H:%M")
        }
        for s in shifts
    ]


@router.get("/inference/cycle-time/{product_id}")
def infer_cycle_time(
    product_id: int,
    shift_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Infer ideal cycle time using 5-level fallback"""
    value, confidence, source, is_estimated = InferenceEngine.infer_ideal_cycle_time(
        db, product_id, shift_id
    )

    confidence_flag = InferenceEngine.flag_low_confidence(confidence)

    return {
        "product_id": product_id,
        "shift_id": shift_id,
        "ideal_cycle_time": value,
        "confidence_score": confidence,
        "source_level": source,
        "is_estimated": is_estimated,
        **confidence_flag
    }
