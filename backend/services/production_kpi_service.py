"""
Production KPI Service
Orchestrates efficiency, performance, and quality rate calculations.

Phase 1.1: Service Orchestration Layer
Decouples routes from domain calculations for better testability and maintainability.

Phase A.1: Added caching for reference data and daily summaries
Phase A.2: Added batch calculation methods to eliminate N+1 query patterns
"""
from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import date, datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_

from backend.schemas.production_entry import ProductionEntry
from backend.schemas.product import Product
from backend.schemas.shift import Shift
from backend.crud.client_config import get_client_config_or_defaults
from backend.cache import get_cache
from backend.cache.kpi_cache import build_cache_key


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

    Phase A.1: Added caching for reference data (products, shifts) and daily summaries
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._cache = get_cache()

    def _get_product_cached(self, product_id: str) -> Optional[Product]:
        """
        Get product by ID with caching.

        Phase A.1: Cache product lookups for 30 minutes (1800s).

        Args:
            product_id: Product ID

        Returns:
            Product or None if not found
        """
        cache_key = build_cache_key("product", product_id)

        def fetch_product():
            product = self.db.query(Product).filter(
                Product.product_id == product_id
            ).first()
            if product:
                # Return a dict representation for caching (ORM objects can't be pickled)
                return {
                    "product_id": product.product_id,
                    "ideal_cycle_time": product.ideal_cycle_time,
                    "name": getattr(product, 'name', None),
                    "part_number": getattr(product, 'part_number', None),
                    "client_id": getattr(product, 'client_id', None),
                }
            return None

        cached_data = self._cache.get_or_set(cache_key, fetch_product, ttl_seconds=1800)

        if cached_data is None:
            return None

        # Create a minimal Product-like object for compatibility
        return _CachedProduct(cached_data)

    def _get_shift_cached(self, shift_id: str) -> Optional[Shift]:
        """
        Get shift by ID with caching.

        Phase A.1: Cache shift lookups for 30 minutes (1800s).

        Args:
            shift_id: Shift ID

        Returns:
            Shift or None if not found
        """
        cache_key = build_cache_key("shift", shift_id)

        def fetch_shift():
            shift = self.db.query(Shift).filter(
                Shift.shift_id == shift_id
            ).first()
            if shift:
                # Return a dict representation for caching
                return {
                    "shift_id": shift.shift_id,
                    "start_time": str(shift.start_time) if shift.start_time else None,
                    "end_time": str(shift.end_time) if shift.end_time else None,
                    "name": getattr(shift, 'name', None),
                    "client_id": getattr(shift, 'client_id', None),
                }
            return None

        cached_data = self._cache.get_or_set(cache_key, fetch_shift, ttl_seconds=1800)

        if cached_data is None:
            return None

        # Create a minimal Shift-like object for compatibility
        return _CachedShift(cached_data)

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

        Phase A.1: Uses cached product and shift lookups.

        Args:
            entry: Production entry to calculate KPIs for
            product: Optional pre-fetched product (avoids extra query)
            shift: Optional pre-fetched shift (avoids extra query)

        Returns:
            ProductionKPIResult with all KPIs and metadata
        """
        # Fetch data with caching if not provided
        if product is None:
            product = self._get_product_cached(entry.product_id)

        if shift is None:
            shift = self._get_shift_cached(entry.shift_id)

        # Get client configuration for defaults (already cached)
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
            product = self._get_product_cached(entry.product_id)

        if shift is None:
            shift = self._get_shift_cached(entry.shift_id)

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
            product = self._get_product_cached(entry.product_id)

        client_id = getattr(entry, 'client_id', None)
        client_config = self._get_client_config(client_id)

        return self._calculate_performance(entry, product, client_config)

    def calculate_batch_kpis(
        self,
        entries: List[ProductionEntry]
    ) -> Dict[str, ProductionKPIResult]:
        """
        Calculate KPIs for multiple entries efficiently using batch pre-fetching.

        Phase A.2: Eliminates N+1 query patterns by:
        1. Pre-fetching all unique products in a single query
        2. Pre-fetching all unique shifts in a single query
        3. Pre-fetching client configs for all unique client_ids
        4. Calculating KPIs using pre-fetched data

        Args:
            entries: List of ProductionEntry objects to calculate KPIs for

        Returns:
            Dictionary mapping entry_id to ProductionKPIResult
        """
        if not entries:
            return {}

        # Pre-fetch all unique IDs
        product_ids = list(set(e.product_id for e in entries if e.product_id))
        shift_ids = list(set(e.shift_id for e in entries if e.shift_id))
        client_ids = list(set(
            getattr(e, 'client_id', None) for e in entries
            if getattr(e, 'client_id', None)
        ))

        # Batch fetch all products (single query)
        products_by_id: Dict[int, Product] = {}
        if product_ids:
            products = self.db.query(Product).filter(
                Product.product_id.in_(product_ids)
            ).all()
            products_by_id = {p.product_id: p for p in products}

        # Batch fetch all shifts (single query)
        shifts_by_id: Dict[int, Shift] = {}
        if shift_ids:
            shifts = self.db.query(Shift).filter(
                Shift.shift_id.in_(shift_ids)
            ).all()
            shifts_by_id = {s.shift_id: s for s in shifts}

        # Batch fetch client configs (using cache for each)
        configs_by_client: Dict[str, Dict[str, Any]] = {}
        for client_id in client_ids:
            configs_by_client[client_id] = self._get_client_config(client_id)

        # Calculate KPIs for each entry using pre-fetched data
        results: Dict[str, ProductionKPIResult] = {}
        for entry in entries:
            product = products_by_id.get(entry.product_id)
            shift = shifts_by_id.get(entry.shift_id)
            client_id = getattr(entry, 'client_id', None)
            client_config = configs_by_client.get(client_id, {})

            # Calculate each KPI component using pre-fetched data
            efficiency = self._calculate_efficiency(entry, product, shift, client_config)
            performance = self._calculate_performance(entry, product, client_config)
            quality = self._calculate_quality_rate(entry)
            oee = self._calculate_oee(efficiency, performance, quality)

            results[entry.production_entry_id] = ProductionKPIResult(
                efficiency=efficiency,
                performance=performance,
                quality=quality,
                oee=oee,
                entry_id=entry.production_entry_id
            )

        return results

    def recalculate_batch(
        self,
        entry_ids: List[str],
        skip_save: bool = False
    ) -> Dict[str, Any]:
        """
        Batch recalculate KPIs for multiple entries.

        Phase A.2 Optimized: Uses batch pre-fetching to eliminate N+1 queries.
        - Pre-fetches all entries with relationships in a single query using joinedload
        - Uses calculate_batch_kpis for efficient batch calculation

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

        if not entry_ids:
            return results

        # Pre-fetch all entries with relationships in a single query (Phase A.2 optimization)
        entries = self.db.query(ProductionEntry).options(
            joinedload(ProductionEntry.product),
            joinedload(ProductionEntry.shift)
        ).filter(
            ProductionEntry.production_entry_id.in_(entry_ids)
        ).all()

        # Build lookup for found entries
        entries_by_id = {e.production_entry_id: e for e in entries}

        # Track which entry_ids were not found
        found_ids = set(entries_by_id.keys())
        missing_ids = set(entry_ids) - found_ids

        # Record missing entries as failures
        for missing_id in missing_ids:
            results["entries"].append({
                "entry_id": missing_id,
                "success": False,
                "error": "Entry not found"
            })
            results["failed"] += 1

        # Calculate KPIs in batch for all found entries
        try:
            kpi_results = self.calculate_batch_kpis(entries)

            # Process results and optionally save
            for entry_id, kpi_result in kpi_results.items():
                try:
                    if not skip_save:
                        entry = entries_by_id[entry_id]
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

        except Exception as e:
            # If batch calculation fails, fall back to individual processing
            for entry in entries:
                try:
                    kpi_result = self.calculate_entry_kpis(
                        entry,
                        product=getattr(entry, 'product', None),
                        shift=getattr(entry, 'shift', None)
                    )

                    if not skip_save:
                        entry.efficiency_percentage = kpi_result.efficiency.efficiency_percentage
                        entry.performance_percentage = kpi_result.performance.performance_percentage

                    results["entries"].append({
                        "entry_id": entry.production_entry_id,
                        "success": True,
                        "efficiency": float(kpi_result.efficiency.efficiency_percentage),
                        "performance": float(kpi_result.performance.performance_percentage),
                        "is_estimated": kpi_result.efficiency.is_estimated
                    })
                    results["successful"] += 1

                except Exception as entry_error:
                    results["entries"].append({
                        "entry_id": entry.production_entry_id,
                        "success": False,
                        "error": str(entry_error)
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

        Phase A.1: Results are cached for 5 minutes (300s).

        Args:
            target_date: Date to summarize
            client_id: Optional client filter

        Returns:
            Dictionary with daily KPI averages and totals
        """
        # Build cache key
        cache_key = build_cache_key(
            "daily_summary",
            client_id or "all",
            target_date.isoformat()
        )

        def compute_summary():
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

        return self._cache.get_or_set(cache_key, compute_summary, ttl_seconds=300)

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

        OEE = Availability x Performance x Quality

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


# =============================================================================
# Helper classes for cached data
# =============================================================================

class _CachedProduct:
    """Minimal Product-like object reconstructed from cached data."""

    def __init__(self, data: dict):
        self.product_id = data.get("product_id")
        self.ideal_cycle_time = data.get("ideal_cycle_time")
        self.name = data.get("name")
        self.part_number = data.get("part_number")
        self.client_id = data.get("client_id")


class _CachedShift:
    """Minimal Shift-like object reconstructed from cached data."""

    def __init__(self, data: dict):
        from datetime import time
        self.shift_id = data.get("shift_id")
        self.name = data.get("name")
        self.client_id = data.get("client_id")

        # Parse time strings back to time objects
        start_str = data.get("start_time")
        end_str = data.get("end_time")

        if start_str and start_str != "None":
            try:
                parts = start_str.split(":")
                self.start_time = time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
            except (ValueError, IndexError):
                self.start_time = None
        else:
            self.start_time = None

        if end_str and end_str != "None":
            try:
                parts = end_str.split(":")
                self.end_time = time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
            except (ValueError, IndexError):
                self.end_time = None
        else:
            self.end_time = None
