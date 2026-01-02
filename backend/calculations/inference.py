"""
Inference Engine - 5-Level Fallback System
CRITICAL COMPONENT: Handles missing standards with confidence scoring
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import Tuple, Optional
from datetime import date, timedelta
from decimal import Decimal

from backend.schemas.product import Product
from backend.schemas.shift import Shift
from backend.schemas.production_entry import ProductionEntry


class InferenceEngine:
    """
    5-Level fallback system for missing standards
    Returns: (value, confidence_score, source_level, is_estimated)
    """

    @staticmethod
    def infer_ideal_cycle_time(
        db: Session,
        product_id: int,
        shift_id: Optional[int] = None,
        client_id: Optional[int] = None,
        style_id: Optional[str] = None
    ) -> Tuple[Decimal, float, str, bool]:
        """
        Infer ideal cycle time using 5-level fallback

        Level 1: Client/Style standard (highest confidence: 1.0)
        Level 2: Shift/Line standard (confidence: 0.9)
        Level 3: Industry default (confidence: 0.7)
        Level 4: Historical 30-day average (confidence: 0.6)
        Level 5: Global product average (confidence: 0.5)
        """

        # LEVEL 1: Client/Style standard
        product = db.query(Product).filter(Product.product_id == product_id).first()
        if product and product.ideal_cycle_time:
            return (
                Decimal(str(product.ideal_cycle_time)),
                1.0,
                "client_style_standard",
                False
            )

        # LEVEL 2: Shift/Line standard
        if shift_id:
            shift_avg = db.query(
                func.avg(ProductionEntry.run_time_hours / ProductionEntry.units_produced)
            ).filter(
                and_(
                    ProductionEntry.product_id == product_id,
                    ProductionEntry.shift_id == shift_id,
                    ProductionEntry.units_produced > 0
                )
            ).scalar()

            if shift_avg and shift_avg > 0:
                return (
                    Decimal(str(shift_avg)),
                    0.9,
                    "shift_line_standard",
                    True
                )

        # LEVEL 3: Industry default (apparel manufacturing)
        industry_defaults = {
            "T-Shirt": Decimal("0.15"),     # 15 minutes per unit
            "Polo": Decimal("0.20"),         # 20 minutes per unit
            "Dress Shirt": Decimal("0.25"),  # 25 minutes per unit
            "Pants": Decimal("0.30"),        # 30 minutes per unit
            "Jacket": Decimal("0.50"),       # 50 minutes per unit
        }

        if product and product.product_name:
            for key, default_time in industry_defaults.items():
                if key.lower() in product.product_name.lower():
                    return (
                        default_time,
                        0.7,
                        "industry_default",
                        True
                    )

        # LEVEL 4: Historical 30-day average
        thirty_days_ago = date.today() - timedelta(days=30)
        historical_avg = db.query(
            func.avg(ProductionEntry.run_time_hours / ProductionEntry.units_produced)
        ).filter(
            and_(
                ProductionEntry.product_id == product_id,
                ProductionEntry.production_date >= thirty_days_ago,
                ProductionEntry.units_produced > 0
            )
        ).scalar()

        if historical_avg and historical_avg > 0:
            return (
                Decimal(str(historical_avg)),
                0.6,
                "historical_30day_avg",
                True
            )

        # LEVEL 5: Global product average (lowest confidence)
        global_avg = db.query(
            func.avg(ProductionEntry.run_time_hours / ProductionEntry.units_produced)
        ).filter(
            ProductionEntry.units_produced > 0
        ).scalar()

        if global_avg and global_avg > 0:
            return (
                Decimal(str(global_avg)),
                0.5,
                "global_product_avg",
                True
            )

        # FALLBACK: Default to 0.20 hours (12 minutes) with very low confidence
        return (
            Decimal("0.20"),
            0.3,
            "system_fallback",
            True
        )

    @staticmethod
    def infer_target_oee(
        db: Session,
        product_id: int,
        shift_id: Optional[int] = None
    ) -> Tuple[Decimal, float, str]:
        """
        Infer target OEE percentage

        Industry standards:
        - World Class: 85%
        - Good: 75%
        - Average: 60%
        - Needs Improvement: <60%
        """

        # Check if product has specific target
        product = db.query(Product).filter(Product.product_id == product_id).first()
        if product and hasattr(product, 'target_oee') and product.target_oee:
            return (
                Decimal(str(product.target_oee)),
                1.0,
                "product_standard"
            )

        # Historical 30-day average OEE
        thirty_days_ago = date.today() - timedelta(days=30)
        historical_oee = db.query(
            func.avg(ProductionEntry.efficiency_percentage * ProductionEntry.performance_percentage / 100)
        ).filter(
            and_(
                ProductionEntry.product_id == product_id,
                ProductionEntry.production_date >= thirty_days_ago,
                ProductionEntry.efficiency_percentage.isnot(None),
                ProductionEntry.performance_percentage.isnot(None)
            )
        ).scalar()

        if historical_oee and historical_oee > 0:
            return (
                Decimal(str(historical_oee)),
                0.8,
                "historical_avg"
            )

        # Industry standard: 75% (Good manufacturing)
        return (
            Decimal("75.00"),
            0.6,
            "industry_standard"
        )

    @staticmethod
    def infer_target_ppm(
        db: Session,
        product_id: int,
        defect_category: Optional[str] = None
    ) -> Tuple[Decimal, float, str]:
        """
        Infer target PPM (Parts Per Million) defect rate

        Industry standards:
        - Six Sigma (6σ): 3.4 PPM
        - Five Sigma (5σ): 233 PPM
        - Four Sigma (4σ): 6,210 PPM
        - Three Sigma (3σ): 66,807 PPM
        """

        # Check product-specific target
        product = db.query(Product).filter(Product.product_id == product_id).first()
        if product and hasattr(product, 'target_ppm') and product.target_ppm:
            return (
                Decimal(str(product.target_ppm)),
                1.0,
                "product_standard"
            )

        # Apparel industry standard: ~2,500 PPM (between 4σ and 5σ)
        return (
            Decimal("2500.00"),
            0.7,
            "industry_standard"
        )

    @staticmethod
    def infer_target_absenteeism(
        db: Session,
        shift_id: int
    ) -> Tuple[Decimal, float, str]:
        """
        Infer target absenteeism rate

        Industry standards:
        - Excellent: <3%
        - Good: 3-5%
        - Average: 5-8%
        - Poor: >8%
        """

        # Historical shift average
        thirty_days_ago = date.today() - timedelta(days=30)

        # This would query attendance records when available
        # For now, return industry standard

        # Manufacturing industry standard: 5%
        return (
            Decimal("5.00"),
            0.7,
            "industry_standard"
        )

    @staticmethod
    def calculate_confidence_score(
        source_level: str,
        data_points: int = 0,
        recency_days: int = 0
    ) -> float:
        """
        Calculate overall confidence score based on multiple factors

        Factors:
        - Source level (base confidence)
        - Number of data points (more = higher confidence)
        - Recency (more recent = higher confidence)
        """

        # Base confidence from source
        base_confidence = {
            "client_style_standard": 1.0,
            "shift_line_standard": 0.9,
            "industry_default": 0.7,
            "historical_30day_avg": 0.6,
            "global_product_avg": 0.5,
            "system_fallback": 0.3
        }.get(source_level, 0.5)

        # Adjust for data points (cap at 0.1 bonus)
        if data_points > 0:
            data_bonus = min(0.1, data_points / 100)
            base_confidence += data_bonus

        # Adjust for recency (cap at 0.1 bonus)
        if recency_days > 0:
            recency_factor = max(0, 1 - (recency_days / 30))
            recency_bonus = recency_factor * 0.1
            base_confidence += recency_bonus

        # Cap at 1.0
        return min(1.0, base_confidence)

    @staticmethod
    def flag_low_confidence(
        confidence: float,
        threshold: float = 0.7
    ) -> dict:
        """
        Flag estimates with low confidence

        Returns dict with warning and recommendation
        """
        if confidence < threshold:
            return {
                "warning": "LOW_CONFIDENCE_ESTIMATE",
                "confidence": confidence,
                "recommendation": "Consider updating product standards or collecting more historical data",
                "needs_review": True
            }

        return {
            "warning": None,
            "confidence": confidence,
            "recommendation": None,
            "needs_review": False
        }
