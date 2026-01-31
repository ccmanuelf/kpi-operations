"""
Production KPI Service
Orchestrates efficiency, performance, and quality rate calculations.

Phase 1.1: Service Orchestration Layer
Decouples routes from domain calculations for better testability and maintainability.
"""
from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from backend.schemas.production_entry import ProductionEntry
from backend.schemas.product import Product
from backend.schemas.shift import Shift
from backend.crud.client_config import get_client_config_or_defaults


@dataclass
class InferenceMetadata:
    """Metadata about inferred values for ESTIMATED flag support."""
    is_inferred: bool
    source: str
    confidence: float


@dataclass
class EfficiencyResult:
    """Result of efficiency calculation with full metadata."""
    efficiency_percentage: Decimal
    ideal_cycle_time_used: Decimal
    employees_used: int
    scheduled_hours: Decimal
    is_estimated: bool
    inference_sources: Dict[str, InferenceMetadata] = field(default_factory=dict)


@dataclass
class PerformanceResult:
    """Result of performance calculation with metadata."""
    performance_percentage: Decimal
    ideal_cycle_time_used: Decimal
    is_estimated: bool
    actual_rate: Decimal  # Units per hour actually achieved


@dataclass
class QualityRateResult:
    """Result of quality rate calculation."""
    quality_rate: Decimal
    good_units: int
    total_units: int
    defect_count: int
    scrap_count: int


@dataclass
class OEEResult:
    """Result of OEE calculation with component breakdown."""
    oee: Decimal
    availability: Decimal
    performance: Decimal
    quality: Decimal
    is_estimated: bool


@dataclass
class ProductionKPIResult:
    """Complete KPI calculation result for a production entry."""
    efficiency: EfficiencyResult
    performance: PerformanceResult
    quality: QualityRateResult
    oee: OEEResult
    entry_id: str
    calculated_at: datetime = field(default_factory=datetime.utcnow)


class ProductionKPIService:
    """
    Service layer for production KPI calculations.

    Coordinates data fetching and delegates to pure calculation functions.
    This separation enables unit testing without database access.
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def calculate_entry_kpis(
        self,
        entry: ProductionEntry,
        product: Optional[Product] = None,
        shift: Optional[Shift] = None
    ) -> ProductionKPIResult:
        """
        Calculate all KPIs for a production entry.

        This method:
        1. Fetches required data (product, shift, client config)
        2. Calls pure calculation functions
        3. Returns results with full metadata

        Args:
            entry: Production entry to calculate KPIs for
            product: Optional pre-fetched product (avoids extra query)
            shift: Optional pre-fetched shift (avoids extra query)

        Returns:
            ProductionKPIResult with all KPIs and metadata
        """
        # Fetch data if not provided
        if product is None:
            product = self.db.query(Product).filter(
                Product.product_id == entry.product_id
            ).first()

        if shift is None:
            shift = self.db.query(Shift).filter(
                Shift.shift_id == entry.shift_id
            ).first()

        # Get client configuration for defaults
        client_id = getattr(entry, 'client_id', None)
        client_config = self._get_client_config(client_id)

        # Calculate each KPI component
        efficiency = self._calculate_efficiency(entry, product, shift, client_config)
        performance = self._calculate_performance(entry, product, client_config)
        quality = self._calculate_quality_rate(entry)
        oee = self._calculate_oee(efficiency, performance, quality)

        return ProductionKPIResult(
            efficiency=efficiency,
            performance=performance,
            quality=quality,
            oee=oee,
            entry_id=entry.production_entry_id
        )

    def calculate_efficiency_only(
        self,
        entry: ProductionEntry,
        product: Optional[Product] = None,
        shift: Optional[Shift] = None
    ) -> EfficiencyResult:
        """
        Calculate efficiency for a single entry.

        Use this when only efficiency is needed.
        """
        if product is None:
            product = self.db.query(Product).filter(
                Product.product_id == entry.product_id
            ).first()

        if shift is None:
            shift = self.db.query(Shift).filter(
                Shift.shift_id == entry.shift_id
            ).first()

        client_id = getattr(entry, 'client_id', None)
        client_config = self._get_client_config(client_id)

        return self._calculate_efficiency(entry, product, shift, client_config)

    def calculate_performance_only(
        self,
        entry: ProductionEntry,
        product: Optional[Product] = None
    ) -> PerformanceResult:
        """
        Calculate performance for a single entry.

        Use this when only performance is needed.
        """
        if product is None:
            product = self.db.query(Product).filter(
                Product.product_id == entry.product_id
            ).first()

        client_id = getattr(entry, 'client_id', None)
        client_config = self._get_client_config(client_id)

        return self._calculate_performance(entry, product, client_config)

    def recalculate_batch(
        self,
        entry_ids: List[str],
        skip_save: bool = False
    ) -> Dict[str, Any]:
        """
        Batch recalculate KPIs for multiple entries.

        Useful for deferred calculation or bulk updates.

        Args:
            entry_ids: List of production entry IDs
            skip_save: If True, calculate but don't save to database

        Returns:
            Dictionary with results and any errors
        """
        results = {
            "total": len(entry_ids),
            "successful": 0,
            "failed": 0,
            "entries": []
        }

        for entry_id in entry_ids:
            try:
                entry = self.db.query(ProductionEntry).filter(
                    ProductionEntry.production_entry_id == entry_id
                ).first()

                if not entry:
                    results["entries"].append({
                        "entry_id": entry_id,
                        "success": False,
                        "error": "Entry not found"
                    })
                    results["failed"] += 1
                    continue

                kpi_result = self.calculate_entry_kpis(entry)

                if not skip_save:
                    entry.efficiency_percentage = kpi_result.efficiency.efficiency_percentage
                    entry.performance_percentage = kpi_result.performance.performance_percentage

                results["entries"].append({
                    "entry_id": entry_id,
                    "success": True,
                    "efficiency": float(kpi_result.efficiency.efficiency_percentage),
                    "performance": float(kpi_result.performance.performance_percentage),
                    "is_estimated": kpi_result.efficiency.is_estimated
                })
                results["successful"] += 1

            except Exception as e:
                results["entries"].append({
                    "entry_id": entry_id,
                    "success": False,
                    "error": str(e)
                })
                results["failed"] += 1

        if not skip_save:
            self.db.commit()

        return results

    def get_daily_kpi_summary(
        self,
        target_date: date,
        client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated KPI summary for a day.

        Args:
            target_date: Date to summarize
            client_id: Optional client filter

        Returns:
            Dictionary with daily KPI averages and totals
        """
        query = self.db.query(
            func.sum(ProductionEntry.units_produced).label("total_units"),
            func.avg(ProductionEntry.efficiency_percentage).label("avg_efficiency"),
            func.avg(ProductionEntry.performance_percentage).label("avg_performance"),
            func.sum(ProductionEntry.defect_count).label("total_defects"),
            func.sum(ProductionEntry.scrap_count).label("total_scrap"),
            func.count(ProductionEntry.production_entry_id).label("entry_count")
        ).filter(
            func.date(ProductionEntry.production_date) == target_date
        )

        if client_id:
            query = query.filter(ProductionEntry.client_id == client_id)

        result = query.first()

        total_units = result.total_units or 0
        total_defects = result.total_defects or 0
        total_scrap = result.total_scrap or 0

        # Calculate quality rate from aggregates
        if total_units > 0:
            good_units = total_units - total_defects - total_scrap
            quality_rate = (Decimal(str(good_units)) / Decimal(str(total_units))) * 100
        else:
            quality_rate = Decimal("0")

        return {
            "date": target_date.isoformat(),
            "total_units_produced": total_units,
            "avg_efficiency": float(result.avg_efficiency or 0),
            "avg_performance": float(result.avg_performance or 0),
            "quality_rate": float(quality_rate),
            "total_defects": total_defects,
            "total_scrap": total_scrap,
            "entry_count": result.entry_count or 0
        }

    # ========================================================================
    # Private calculation methods
    # These orchestrate data fetching and call pure calculation functions
    # ========================================================================

    def _get_client_config(self, client_id: Optional[str]) -> Dict[str, Any]:
        """Get client configuration or defaults."""
        if not client_id:
            return {}
        try:
            return get_client_config_or_defaults(self.db, client_id)
        except Exception:
            return {}

    def _calculate_efficiency(
        self,
        entry: ProductionEntry,
        product: Optional[Product],
        shift: Optional[Shift],
        client_config: Dict[str, Any]
    ) -> EfficiencyResult:
        """
        Calculate efficiency with data fetching abstracted.

        Delegates to pure calculation function after gathering inputs.
        """
        from backend.calculations.efficiency import (
            calculate_efficiency_pure,
            infer_employees_count,
            infer_ideal_cycle_time,
            calculate_shift_hours,
            DEFAULT_CYCLE_TIME,
            DEFAULT_SHIFT_HOURS,
        )

        inference_sources = {}

        # Get ideal cycle time
        if product and product.ideal_cycle_time is not None:
            ideal_cycle_time = Decimal(str(product.ideal_cycle_time))
            cycle_time_inferred = False
            cycle_time_source = "product_standard"
            cycle_time_confidence = 1.0
        else:
            # Use inference chain
            ideal_cycle_time, cycle_time_inferred = infer_ideal_cycle_time(
                self.db,
                entry.product_id,
                entry.production_entry_id,
                getattr(entry, 'client_id', None)
            )
            cycle_time_source = "historical_avg" if cycle_time_inferred else "client_default"
            cycle_time_confidence = 0.6 if cycle_time_inferred else 0.4

        inference_sources["cycle_time"] = InferenceMetadata(
            is_inferred=cycle_time_inferred,
            source=cycle_time_source,
            confidence=cycle_time_confidence
        )

        # Get scheduled hours from shift
        if shift and shift.start_time and shift.end_time:
            scheduled_hours = calculate_shift_hours(shift.start_time, shift.end_time)
            hours_inferred = False
        else:
            scheduled_hours = DEFAULT_SHIFT_HOURS
            hours_inferred = True

        inference_sources["scheduled_hours"] = InferenceMetadata(
            is_inferred=hours_inferred,
            source="shift_times" if not hours_inferred else "default",
            confidence=1.0 if not hours_inferred else 0.5
        )

        # Get employees count with inference
        inferred_employees = infer_employees_count(self.db, entry)
        employees_count = inferred_employees.count

        inference_sources["employees"] = InferenceMetadata(
            is_inferred=inferred_employees.is_inferred,
            source=inferred_employees.inference_source,
            confidence=inferred_employees.confidence_score
        )

        # Call pure calculation
        efficiency = calculate_efficiency_pure(
            units_produced=entry.units_produced,
            ideal_cycle_time=ideal_cycle_time,
            employees_count=employees_count,
            scheduled_hours=scheduled_hours
        )

        # Determine if any value was inferred
        any_inferred = (
            cycle_time_inferred or
            hours_inferred or
            inferred_employees.is_inferred
        )

        return EfficiencyResult(
            efficiency_percentage=efficiency,
            ideal_cycle_time_used=ideal_cycle_time,
            employees_used=employees_count,
            scheduled_hours=scheduled_hours,
            is_estimated=any_inferred,
            inference_sources=inference_sources
        )

    def _calculate_performance(
        self,
        entry: ProductionEntry,
        product: Optional[Product],
        client_config: Dict[str, Any]
    ) -> PerformanceResult:
        """
        Calculate performance with data fetching abstracted.
        """
        from backend.calculations.efficiency import infer_ideal_cycle_time
        from backend.calculations.performance import calculate_performance_pure

        # Get ideal cycle time
        if product and product.ideal_cycle_time is not None:
            ideal_cycle_time = Decimal(str(product.ideal_cycle_time))
            was_inferred = False
        else:
            ideal_cycle_time, was_inferred = infer_ideal_cycle_time(
                self.db,
                entry.product_id,
                entry.production_entry_id,
                getattr(entry, 'client_id', None)
            )

        # Call pure calculation
        performance, actual_rate = calculate_performance_pure(
            units_produced=entry.units_produced,
            run_time_hours=Decimal(str(entry.run_time_hours)),
            ideal_cycle_time=ideal_cycle_time
        )

        return PerformanceResult(
            performance_percentage=performance,
            ideal_cycle_time_used=ideal_cycle_time,
            is_estimated=was_inferred,
            actual_rate=actual_rate
        )

    def _calculate_quality_rate(self, entry: ProductionEntry) -> QualityRateResult:
        """
        Calculate quality rate for a production entry.

        This is a pure calculation - no database access needed.
        """
        from backend.calculations.performance import calculate_quality_rate_pure

        quality_rate, good_units = calculate_quality_rate_pure(
            units_produced=entry.units_produced,
            defect_count=entry.defect_count or 0,
            scrap_count=entry.scrap_count or 0
        )

        return QualityRateResult(
            quality_rate=quality_rate,
            good_units=good_units,
            total_units=entry.units_produced,
            defect_count=entry.defect_count or 0,
            scrap_count=entry.scrap_count or 0
        )

    def _calculate_oee(
        self,
        efficiency: EfficiencyResult,
        performance: PerformanceResult,
        quality: QualityRateResult
    ) -> OEEResult:
        """
        Calculate OEE from component values.

        OEE = Availability × Performance × Quality

        Note: For Phase 1, we assume 100% availability.
        Full availability tracking requires downtime integration (Phase 2).
        """
        from backend.calculations.performance import calculate_oee_pure

        # Assume 100% availability for now (requires downtime tracking for actual)
        availability = Decimal("100")

        oee = calculate_oee_pure(
            availability=availability,
            performance=performance.performance_percentage,
            quality=quality.quality_rate
        )

        return OEEResult(
            oee=oee,
            availability=availability,
            performance=performance.performance_percentage,
            quality=quality.quality_rate,
            is_estimated=performance.is_estimated or efficiency.is_estimated
        )
