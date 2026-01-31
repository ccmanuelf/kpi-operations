"""
Quality KPI Service
Orchestrates PPM, DPMO, FPY, RTY calculations.

Phase 1.1: Service Orchestration Layer
Decouples routes from domain calculations for better testability.
"""
from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, cast, Date

from backend.schemas.quality_entry import QualityEntry
from backend.schemas.job import Job
from backend.schemas.part_opportunities import PartOpportunities
from backend.crud.client_config import get_client_config_or_defaults


@dataclass
class PPMResult:
    """Result of PPM calculation with metadata."""
    ppm: Decimal
    total_inspected: int
    total_defects: int
    calculation_period: Dict[str, str] = field(default_factory=dict)


@dataclass
class DPMOResult:
    """Result of DPMO calculation with metadata."""
    dpmo: Decimal
    sigma_level: Decimal
    total_units: int
    total_defects: int
    total_opportunities: int
    opportunities_per_unit: int
    using_part_specific_opportunities: bool = False


@dataclass
class FPYResult:
    """Result of FPY (First Pass Yield) calculation."""
    fpy_percentage: Decimal
    first_pass_good: int
    total_units: int
    units_reworked: int
    units_requiring_repair: int
    units_scrapped: int


@dataclass
class RTYResult:
    """Result of RTY (Rolled Throughput Yield) calculation."""
    rty_percentage: Decimal
    step_details: List[Dict[str, Any]]
    total_rework: int
    total_repair: int
    total_scrap: int
    rework_impact_percentage: Decimal
    repair_impact_percentage: Decimal
    interpretation: str


@dataclass
class QualityKPIResult:
    """Complete quality KPI result."""
    ppm: PPMResult
    dpmo: DPMOResult
    fpy: FPYResult
    rty: Optional[RTYResult] = None
    calculated_at: datetime = field(default_factory=datetime.utcnow)


class QualityKPIService:
    """
    Service layer for quality KPI calculations.

    Coordinates data fetching and delegates to pure calculation functions.
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def calculate_ppm(
        self,
        start_date: date,
        end_date: date,
        work_order_id: Optional[str] = None,
        client_id: Optional[str] = None
    ) -> PPMResult:
        """
        Calculate PPM for a date range.

        PPM = (Total Defects / Total Units Inspected) * 1,000,000

        Args:
            start_date: Start of date range
            end_date: End of date range
            work_order_id: Optional work order filter
            client_id: Optional client filter

        Returns:
            PPMResult with calculation details
        """
        from backend.calculations.ppm import calculate_ppm_pure

        # Fetch aggregated data
        aggregates = self._fetch_quality_aggregates(
            start_date, end_date, work_order_id, client_id
        )

        # Call pure calculation
        ppm = calculate_ppm_pure(
            total_inspected=aggregates["total_inspected"],
            total_defects=aggregates["total_defects"]
        )

        return PPMResult(
            ppm=ppm,
            total_inspected=aggregates["total_inspected"],
            total_defects=aggregates["total_defects"],
            calculation_period={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            }
        )

    def calculate_dpmo(
        self,
        start_date: date,
        end_date: date,
        work_order_id: Optional[str] = None,
        part_number: Optional[str] = None,
        opportunities_per_unit: Optional[int] = None,
        client_id: Optional[str] = None
    ) -> DPMOResult:
        """
        Calculate DPMO for a date range.

        DPMO = (Total Defects / (Total Units × Opportunities per Unit)) * 1,000,000

        Args:
            start_date: Start of date range
            end_date: End of date range
            work_order_id: Optional work order filter
            part_number: Optional part number to look up opportunities
            opportunities_per_unit: Manual override for opportunities
            client_id: Optional client filter

        Returns:
            DPMOResult with calculation details
        """
        from backend.calculations.dpmo import (
            calculate_dpmo_pure,
            calculate_sigma_level,
            get_opportunities_for_part,
            get_client_opportunities_default
        )

        # Determine opportunities per unit
        using_part_specific = False
        if opportunities_per_unit is not None:
            effective_opportunities = opportunities_per_unit
        elif part_number:
            effective_opportunities = get_opportunities_for_part(
                self.db, part_number, client_id
            )
            using_part_specific = True
        else:
            effective_opportunities = get_client_opportunities_default(self.db, client_id)

        # Fetch aggregated data
        aggregates = self._fetch_quality_aggregates(
            start_date, end_date, work_order_id, client_id
        )

        # Call pure calculation
        dpmo, total_opportunities = calculate_dpmo_pure(
            total_defects=aggregates["total_defects_count"],
            total_units=aggregates["total_inspected"],
            opportunities_per_unit=effective_opportunities
        )

        sigma_level = calculate_sigma_level(dpmo)

        return DPMOResult(
            dpmo=dpmo,
            sigma_level=sigma_level,
            total_units=aggregates["total_inspected"],
            total_defects=aggregates["total_defects_count"],
            total_opportunities=total_opportunities,
            opportunities_per_unit=effective_opportunities,
            using_part_specific_opportunities=using_part_specific
        )

    def calculate_dpmo_by_part(
        self,
        start_date: date,
        end_date: date,
        client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate DPMO with part-specific opportunities breakdown.

        Groups quality entries by part number and calculates DPMO
        using part-specific opportunities from PART_OPPORTUNITIES table.
        """
        from backend.calculations.dpmo import (
            calculate_dpmo_pure,
            calculate_sigma_level,
            get_opportunities_for_parts,
            get_client_opportunities_default
        )

        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        # Get quality entries with job info
        query = self.db.query(QualityEntry).filter(
            and_(
                QualityEntry.shift_date >= start_datetime,
                QualityEntry.shift_date <= end_datetime
            )
        )

        if client_id:
            query = query.filter(QualityEntry.client_id == client_id)

        quality_entries = query.all()

        if not quality_entries:
            return {
                "overall_dpmo": Decimal("0"),
                "overall_sigma_level": Decimal("0"),
                "total_units": 0,
                "total_defects": 0,
                "total_opportunities": 0,
                "by_part": [],
                "using_part_specific_opportunities": False
            }

        # Get part numbers from jobs
        job_ids = [qe.job_id for qe in quality_entries if qe.job_id]
        jobs = []
        part_numbers = []

        if job_ids:
            jobs = self.db.query(Job).filter(Job.job_id.in_(job_ids)).all()
            part_numbers = [j.part_number for j in jobs if j.part_number]

        # Batch lookup opportunities
        opportunities_map = get_opportunities_for_parts(self.db, part_numbers, client_id)
        client_default = get_client_opportunities_default(self.db, client_id)

        # Group by part and calculate
        part_metrics = {}
        for qe in quality_entries:
            part_number = None
            if qe.job_id:
                for j in jobs:
                    if j.job_id == qe.job_id:
                        part_number = j.part_number
                        break

            key = part_number or "UNKNOWN"
            if key not in part_metrics:
                opportunities = opportunities_map.get(part_number, client_default)
                part_metrics[key] = {
                    "part_number": key,
                    "opportunities_per_unit": opportunities,
                    "units_inspected": 0,
                    "defects_found": 0
                }

            part_metrics[key]["units_inspected"] += qe.units_inspected or 0
            part_metrics[key]["defects_found"] += qe.total_defects_count or qe.units_defective or 0

        # Calculate DPMO per part and overall
        total_opportunities = 0
        total_defects = 0
        total_units = 0
        by_part = []

        for key, metrics in part_metrics.items():
            units = metrics["units_inspected"]
            defects = metrics["defects_found"]
            opps = metrics["opportunities_per_unit"]

            part_dpmo, part_opps = calculate_dpmo_pure(defects, units, opps)

            total_units += units
            total_defects += defects
            total_opportunities += part_opps

            by_part.append({
                "part_number": key,
                "units_inspected": units,
                "defects_found": defects,
                "opportunities_per_unit": opps,
                "total_opportunities": part_opps,
                "dpmo": float(part_dpmo),
                "sigma_level": float(calculate_sigma_level(part_dpmo))
            })

        # Overall DPMO
        if total_opportunities > 0:
            overall_dpmo = (Decimal(str(total_defects)) / Decimal(str(total_opportunities))) * Decimal("1000000")
        else:
            overall_dpmo = Decimal("0")

        overall_sigma = calculate_sigma_level(overall_dpmo)

        return {
            "overall_dpmo": float(overall_dpmo),
            "overall_sigma_level": float(overall_sigma),
            "total_units": total_units,
            "total_defects": total_defects,
            "total_opportunities": total_opportunities,
            "by_part": by_part,
            "using_part_specific_opportunities": len(part_numbers) > 0
        }

    def calculate_fpy(
        self,
        start_date: date,
        end_date: date,
        inspection_stage: Optional[str] = None,
        client_id: Optional[str] = None
    ) -> FPYResult:
        """
        Calculate First Pass Yield for a date range.

        FPY = (Units Passed First Time / Total Units Inspected) * 100

        Args:
            start_date: Start of date range
            end_date: End of date range
            inspection_stage: Optional stage filter
            client_id: Optional client filter

        Returns:
            FPYResult with calculation details
        """
        from backend.calculations.fpy_rty import calculate_fpy_pure

        # Fetch aggregated data
        aggregates = self._fetch_fpy_aggregates(
            start_date, end_date, inspection_stage, client_id
        )

        # Call pure calculation
        fpy = calculate_fpy_pure(
            total_passed=aggregates["total_passed"],
            total_inspected=aggregates["total_inspected"]
        )

        return FPYResult(
            fpy_percentage=fpy,
            first_pass_good=aggregates["total_passed"],
            total_units=aggregates["total_inspected"],
            units_reworked=aggregates["total_rework"],
            units_requiring_repair=aggregates["total_repair"],
            units_scrapped=aggregates["total_scrap"]
        )

    def calculate_rty(
        self,
        start_date: date,
        end_date: date,
        process_steps: Optional[List[str]] = None,
        client_id: Optional[str] = None
    ) -> RTYResult:
        """
        Calculate Rolled Throughput Yield across process steps.

        RTY = FPY_step1 × FPY_step2 × ... × FPY_stepN

        Args:
            start_date: Start of date range
            end_date: End of date range
            process_steps: List of inspection stages (default: standard apparel stages)
            client_id: Optional client filter

        Returns:
            RTYResult with calculation details
        """
        from backend.calculations.fpy_rty import calculate_rty_pure, get_rty_interpretation

        if not process_steps:
            process_steps = ['Incoming', 'In-Process', 'Final']

        # Calculate FPY for each step
        step_details = []
        step_fpys = []
        total_rework = 0
        total_repair = 0
        total_scrap = 0
        total_inspected = 0

        for step in process_steps:
            aggregates = self._fetch_fpy_aggregates(
                start_date, end_date, step, client_id
            )

            fpy = calculate_fpy_pure(
                aggregates["total_passed"],
                aggregates["total_inspected"]
            )

            step_fpys.append(fpy)
            total_rework += aggregates["total_rework"]
            total_repair += aggregates["total_repair"]
            total_scrap += aggregates["total_scrap"]
            total_inspected += aggregates["total_inspected"]

            step_details.append({
                "step": step,
                "fpy_percentage": float(fpy),
                "first_pass_good": aggregates["total_passed"],
                "total_inspected": aggregates["total_inspected"],
                "units_reworked": aggregates["total_rework"],
                "units_requiring_repair": aggregates["total_repair"],
                "units_scrapped": aggregates["total_scrap"]
            })

        # Calculate RTY
        rty = calculate_rty_pure(step_fpys)

        # Calculate impact percentages
        if total_inspected > 0:
            rework_impact = (Decimal(str(total_rework)) / Decimal(str(total_inspected))) * 100
            repair_impact = (Decimal(str(total_repair)) / Decimal(str(total_inspected))) * 100
        else:
            rework_impact = repair_impact = Decimal("0")

        return RTYResult(
            rty_percentage=rty,
            step_details=step_details,
            total_rework=total_rework,
            total_repair=total_repair,
            total_scrap=total_scrap,
            rework_impact_percentage=rework_impact,
            repair_impact_percentage=repair_impact,
            interpretation=get_rty_interpretation(rty, repair_impact)
        )

    def calculate_work_order_job_rty(
        self,
        work_order_id: str,
        client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate RTY across all jobs within a work order.

        Job-level RTY provides more granular insight into which
        operations have yield issues.
        """
        from backend.calculations.fpy_rty import calculate_work_order_job_rty

        return calculate_work_order_job_rty(self.db, work_order_id, client_id)

    def get_quality_summary(
        self,
        start_date: date,
        end_date: date,
        client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive quality summary for a date range.

        Returns all quality KPIs in a single call.
        """
        ppm = self.calculate_ppm(start_date, end_date, client_id=client_id)
        dpmo = self.calculate_dpmo(start_date, end_date, client_id=client_id)
        fpy = self.calculate_fpy(start_date, end_date, client_id=client_id)
        rty = self.calculate_rty(start_date, end_date, client_id=client_id)

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "ppm": {
                "value": float(ppm.ppm),
                "total_inspected": ppm.total_inspected,
                "total_defects": ppm.total_defects
            },
            "dpmo": {
                "value": float(dpmo.dpmo),
                "sigma_level": float(dpmo.sigma_level),
                "opportunities_per_unit": dpmo.opportunities_per_unit
            },
            "fpy": {
                "value": float(fpy.fpy_percentage),
                "first_pass_good": fpy.first_pass_good,
                "total_units": fpy.total_units
            },
            "rty": {
                "value": float(rty.rty_percentage),
                "step_count": len(rty.step_details),
                "interpretation": rty.interpretation
            },
            "calculated_at": datetime.utcnow().isoformat()
        }

    # ========================================================================
    # Private data fetching methods
    # ========================================================================

    def _fetch_quality_aggregates(
        self,
        start_date: date,
        end_date: date,
        work_order_id: Optional[str] = None,
        client_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Fetch aggregated quality data for calculations."""
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        query = self.db.query(
            func.sum(QualityEntry.units_inspected).label('total_inspected'),
            func.sum(QualityEntry.units_defective).label('total_defects'),
            func.sum(QualityEntry.total_defects_count).label('total_defects_count')
        ).filter(
            and_(
                QualityEntry.shift_date >= start_datetime,
                QualityEntry.shift_date <= end_datetime
            )
        )

        if work_order_id:
            query = query.filter(QualityEntry.work_order_id == work_order_id)

        if client_id:
            query = query.filter(QualityEntry.client_id == client_id)

        result = query.first()

        return {
            "total_inspected": result.total_inspected or 0,
            "total_defects": result.total_defects or 0,
            "total_defects_count": result.total_defects_count or result.total_defects or 0
        }

    def _fetch_fpy_aggregates(
        self,
        start_date: date,
        end_date: date,
        inspection_stage: Optional[str] = None,
        client_id: Optional[str] = None
    ) -> Dict[str, int]:
        """Fetch aggregated FPY data for calculations."""
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        query = self.db.query(
            func.sum(QualityEntry.units_inspected).label('total_inspected'),
            func.sum(QualityEntry.units_passed).label('total_passed'),
            func.sum(QualityEntry.units_reworked).label('total_rework'),
            func.sum(QualityEntry.units_requiring_repair).label('total_repair'),
            func.sum(QualityEntry.units_scrapped).label('total_scrap')
        ).filter(
            and_(
                QualityEntry.shift_date >= start_datetime,
                QualityEntry.shift_date <= end_datetime
            )
        )

        if inspection_stage:
            query = query.filter(QualityEntry.inspection_stage == inspection_stage)

        if client_id:
            query = query.filter(QualityEntry.client_id == client_id)

        result = query.first()

        return {
            "total_inspected": result.total_inspected or 0,
            "total_passed": result.total_passed or 0,
            "total_rework": result.total_rework or 0,
            "total_repair": result.total_repair or 0,
            "total_scrap": result.total_scrap or 0
        }
