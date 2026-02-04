"""
Capacity Analysis Service
Phase B.2: Backend Services for Capacity Planning

Implements the 12-step capacity calculation methodology:
1. Get working days from calendar
2. Get shifts per day
3. Get hours per shift
4. Calculate gross hours
5. Apply efficiency factor
6. Apply absenteeism
7. Calculate net hours
8. Multiply by operators
9. Get demand hours (from SAM)
10. Calculate utilization
11. Identify bottlenecks
12. Store results
"""
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from backend.schemas.capacity.analysis import CapacityAnalysis
from backend.schemas.capacity.calendar import CapacityCalendar
from backend.schemas.capacity.production_lines import CapacityProductionLine
from backend.schemas.capacity.schedule import CapacitySchedule, CapacityScheduleDetail, ScheduleStatus
from backend.schemas.capacity.standards import CapacityProductionStandard
from backend.schemas.capacity.orders import CapacityOrder
from backend.events.bus import event_bus
from backend.events.domain_events import CapacityOverloadDetected


@dataclass
class LineCapacityResult:
    """Capacity analysis result for a single production line."""
    line_id: int
    line_code: str
    line_name: str
    department: Optional[str]
    # Step inputs
    working_days: int
    shifts_per_day: int
    hours_per_shift: Decimal
    operators_available: int
    efficiency_factor: Decimal
    absenteeism_factor: Decimal
    # Calculated values
    gross_hours: Decimal
    net_hours: Decimal
    capacity_hours: Decimal
    demand_hours: Decimal
    demand_units: int
    # Results
    utilization_percent: Decimal
    is_bottleneck: bool
    available_capacity_hours: Decimal


@dataclass
class CapacityAnalysisResult:
    """Complete capacity analysis result for a period."""
    analysis_date: date
    period_start: date
    period_end: date
    lines_analyzed: int
    total_capacity_hours: Decimal
    total_demand_hours: Decimal
    overall_utilization: Decimal
    bottleneck_count: int
    lines: List[LineCapacityResult]


class CapacityAnalysisService:
    """
    Service for capacity analysis operations.

    Implements the 12-step capacity calculation methodology
    for production line utilization analysis.

    Multi-tenant isolation via client_id on all operations.
    """

    def __init__(self, db: Session):
        """
        Initialize analysis service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.bottleneck_threshold = Decimal("95.0")

    def analyze_capacity(
        self,
        client_id: str,
        period_start: date,
        period_end: date,
        line_ids: Optional[List[int]] = None,
        schedule_id: Optional[int] = None
    ) -> CapacityAnalysisResult:
        """
        Run capacity analysis for specified period.

        Implements the 12-step calculation:
        1. Get working days from calendar
        2. Get shifts per day
        3. Get hours per shift
        4. Calculate gross hours
        5. Apply efficiency factor
        6. Apply absenteeism
        7. Calculate net hours
        8. Multiply by operators
        9. Get demand hours (from SAM)
        10. Calculate utilization
        11. Identify bottlenecks
        12. Store results

        Args:
            client_id: Client ID for tenant isolation
            period_start: Start date of analysis period
            period_end: End date of analysis period
            line_ids: Optional list of specific line IDs to analyze
            schedule_id: Optional schedule ID to get demand from

        Returns:
            CapacityAnalysisResult with all line analyses
        """
        analysis_date = date.today()

        # Get production lines
        lines = self._get_production_lines(client_id, line_ids)

        if not lines:
            return CapacityAnalysisResult(
                analysis_date=analysis_date,
                period_start=period_start,
                period_end=period_end,
                lines_analyzed=0,
                total_capacity_hours=Decimal("0"),
                total_demand_hours=Decimal("0"),
                overall_utilization=Decimal("0"),
                bottleneck_count=0,
                lines=[]
            )

        # Get calendar data for period
        calendar_data = self._get_calendar_data(client_id, period_start, period_end)

        # Get demand by line (from schedule or orders)
        demand_by_line = self._get_demand_by_line(
            client_id, period_start, period_end, schedule_id
        )

        # Analyze each line
        line_results: List[LineCapacityResult] = []
        total_capacity = Decimal("0")
        total_demand = Decimal("0")
        bottleneck_count = 0

        for line in lines:
            result = self._analyze_line(
                client_id=client_id,
                line=line,
                calendar_data=calendar_data,
                demand_hours=demand_by_line.get(line.id, {}).get("hours", Decimal("0")),
                demand_units=demand_by_line.get(line.id, {}).get("units", 0),
                analysis_date=analysis_date
            )

            line_results.append(result)
            total_capacity += result.capacity_hours
            total_demand += result.demand_hours

            if result.is_bottleneck:
                bottleneck_count += 1
                # Emit overload event
                event = CapacityOverloadDetected(
                    aggregate_id=f"analysis_{client_id}_{analysis_date}_{line.id}",
                    client_id=client_id,
                    line_id=str(line.id),
                    line_name=line.line_name,
                    analysis_date=analysis_date,
                    utilization_percent=result.utilization_percent,
                    available_hours=result.capacity_hours,
                    required_hours=result.demand_hours
                )
                event_bus.collect(event)

            # Store analysis result
            self._store_analysis_result(client_id, analysis_date, line, result)

        # Calculate overall utilization
        overall_utilization = Decimal("0")
        if total_capacity > 0:
            overall_utilization = (total_demand / total_capacity) * 100

        return CapacityAnalysisResult(
            analysis_date=analysis_date,
            period_start=period_start,
            period_end=period_end,
            lines_analyzed=len(line_results),
            total_capacity_hours=total_capacity,
            total_demand_hours=total_demand,
            overall_utilization=overall_utilization,
            bottleneck_count=bottleneck_count,
            lines=line_results
        )

    def get_line_capacity(
        self,
        client_id: str,
        line_id: int,
        period_start: date,
        period_end: date
    ) -> Optional[LineCapacityResult]:
        """
        Get capacity for a single line.

        Args:
            client_id: Client ID for tenant isolation
            line_id: Production line ID
            period_start: Start date of period
            period_end: End date of period

        Returns:
            LineCapacityResult or None if line not found
        """
        line = self.db.query(CapacityProductionLine).filter(
            CapacityProductionLine.client_id == client_id,
            CapacityProductionLine.id == line_id,
            CapacityProductionLine.is_active == True
        ).first()

        if not line:
            return None

        calendar_data = self._get_calendar_data(client_id, period_start, period_end)
        demand_by_line = self._get_demand_by_line(
            client_id, period_start, period_end, None
        )

        return self._analyze_line(
            client_id=client_id,
            line=line,
            calendar_data=calendar_data,
            demand_hours=demand_by_line.get(line.id, {}).get("hours", Decimal("0")),
            demand_units=demand_by_line.get(line.id, {}).get("units", 0),
            analysis_date=date.today()
        )

    def get_historical_analysis(
        self,
        client_id: str,
        line_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[CapacityAnalysis]:
        """
        Get historical capacity analysis records.

        Args:
            client_id: Client ID for tenant isolation
            line_id: Optional line ID filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of CapacityAnalysis records
        """
        query = self.db.query(CapacityAnalysis).filter(
            CapacityAnalysis.client_id == client_id
        )

        if line_id:
            query = query.filter(CapacityAnalysis.line_id == line_id)
        if start_date:
            query = query.filter(CapacityAnalysis.analysis_date >= start_date)
        if end_date:
            query = query.filter(CapacityAnalysis.analysis_date <= end_date)

        return query.order_by(CapacityAnalysis.analysis_date.desc()).all()

    def identify_bottlenecks(
        self,
        client_id: str,
        period_start: date,
        period_end: date,
        threshold: Optional[Decimal] = None
    ) -> List[LineCapacityResult]:
        """
        Identify bottleneck lines for a period.

        Args:
            client_id: Client ID for tenant isolation
            period_start: Start date of period
            period_end: End date of period
            threshold: Optional utilization threshold (default 95%)

        Returns:
            List of LineCapacityResult for bottleneck lines
        """
        if threshold is not None:
            self.bottleneck_threshold = threshold

        result = self.analyze_capacity(client_id, period_start, period_end)
        return [line for line in result.lines if line.is_bottleneck]

    def _get_production_lines(
        self,
        client_id: str,
        line_ids: Optional[List[int]] = None
    ) -> List[CapacityProductionLine]:
        """Get production lines for analysis."""
        query = self.db.query(CapacityProductionLine).filter(
            CapacityProductionLine.client_id == client_id,
            CapacityProductionLine.is_active == True
        )

        if line_ids:
            query = query.filter(CapacityProductionLine.id.in_(line_ids))

        return query.all()

    def _get_calendar_data(
        self,
        client_id: str,
        period_start: date,
        period_end: date
    ) -> Dict:
        """
        Get calendar data for the period.

        Returns:
            Dict with working_days, total_shifts, total_hours
        """
        calendars = self.db.query(CapacityCalendar).filter(
            CapacityCalendar.client_id == client_id,
            CapacityCalendar.calendar_date >= period_start,
            CapacityCalendar.calendar_date <= period_end,
            CapacityCalendar.is_working_day == True
        ).all()

        if not calendars:
            # Default: calculate from date range assuming 5 day week
            total_days = (period_end - period_start).days + 1
            working_days = int(total_days * 5 / 7)
            return {
                "working_days": working_days,
                "shifts_per_day": 1,
                "hours_per_shift": Decimal("8.0")
            }

        working_days = len(calendars)
        total_shifts = sum(c.shifts_available for c in calendars)
        total_hours = sum(Decimal(str(c.total_hours())) for c in calendars)

        avg_shifts = total_shifts / working_days if working_days > 0 else 1
        avg_hours = total_hours / total_shifts if total_shifts > 0 else Decimal("8.0")

        return {
            "working_days": working_days,
            "shifts_per_day": int(round(avg_shifts)),
            "hours_per_shift": avg_hours / avg_shifts if avg_shifts > 0 else Decimal("8.0")
        }

    def _get_demand_by_line(
        self,
        client_id: str,
        period_start: date,
        period_end: date,
        schedule_id: Optional[int]
    ) -> Dict[int, Dict]:
        """
        Get demand by line from schedule or orders.

        Returns:
            Dict of line_id -> {"hours": Decimal, "units": int}
        """
        demand_by_line: Dict[int, Dict] = {}

        if schedule_id:
            # Get demand from specific schedule
            details = self.db.query(CapacityScheduleDetail).filter(
                CapacityScheduleDetail.client_id == client_id,
                CapacityScheduleDetail.schedule_id == schedule_id,
                CapacityScheduleDetail.scheduled_date >= period_start,
                CapacityScheduleDetail.scheduled_date <= period_end
            ).all()
        else:
            # Get demand from committed schedules
            schedule_ids = self.db.query(CapacitySchedule.id).filter(
                CapacitySchedule.client_id == client_id,
                CapacitySchedule.status.in_([ScheduleStatus.COMMITTED, ScheduleStatus.ACTIVE]),
                CapacitySchedule.period_start <= period_end,
                CapacitySchedule.period_end >= period_start
            ).all()

            schedule_ids = [s[0] for s in schedule_ids]

            if not schedule_ids:
                return demand_by_line

            details = self.db.query(CapacityScheduleDetail).filter(
                CapacityScheduleDetail.client_id == client_id,
                CapacityScheduleDetail.schedule_id.in_(schedule_ids),
                CapacityScheduleDetail.scheduled_date >= period_start,
                CapacityScheduleDetail.scheduled_date <= period_end
            ).all()

        # Get SAM data for style codes
        style_codes = list(set(d.style_code for d in details if d.style_code))
        sam_by_style = self._get_sam_by_style(client_id, style_codes)

        # Calculate demand per line
        for detail in details:
            if not detail.line_id:
                continue

            if detail.line_id not in demand_by_line:
                demand_by_line[detail.line_id] = {"hours": Decimal("0"), "units": 0}

            units = detail.scheduled_quantity or 0
            sam_minutes = sam_by_style.get(detail.style_code, Decimal("0"))
            hours = (Decimal(str(units)) * sam_minutes) / Decimal("60")

            demand_by_line[detail.line_id]["hours"] += hours
            demand_by_line[detail.line_id]["units"] += units

        return demand_by_line

    def _get_sam_by_style(
        self,
        client_id: str,
        style_codes: List[str]
    ) -> Dict[str, Decimal]:
        """Get total SAM by style code."""
        if not style_codes:
            return {}

        # Aggregate SAM per style (sum of all operations)
        results = self.db.query(
            CapacityProductionStandard.style_code,
            func.sum(CapacityProductionStandard.sam_minutes).label('total_sam')
        ).filter(
            CapacityProductionStandard.client_id == client_id,
            CapacityProductionStandard.style_code.in_(style_codes)
        ).group_by(CapacityProductionStandard.style_code).all()

        return {r.style_code: Decimal(str(r.total_sam or 0)) for r in results}

    def _analyze_line(
        self,
        client_id: str,
        line: CapacityProductionLine,
        calendar_data: Dict,
        demand_hours: Decimal,
        demand_units: int,
        analysis_date: date
    ) -> LineCapacityResult:
        """
        Analyze capacity for a single line using 12-step calculation.

        Steps:
        1-3: Get working days, shifts, hours from calendar
        4: Calculate gross hours
        5-6: Apply efficiency and absenteeism factors
        7-8: Calculate net hours and capacity hours
        9-11: Compare to demand and calculate utilization
        12: Identify bottleneck
        """
        # Steps 1-3: Calendar inputs
        working_days = calendar_data["working_days"]
        shifts_per_day = calendar_data["shifts_per_day"]
        hours_per_shift = Decimal(str(calendar_data["hours_per_shift"]))

        # Step 4: Gross hours
        gross_hours = Decimal(str(working_days * shifts_per_day)) * hours_per_shift

        # Steps 5-6: Efficiency factors from line
        efficiency_factor = Decimal(str(line.efficiency_factor or 0.85))
        absenteeism_factor = Decimal(str(line.absenteeism_factor or 0.05))

        # Step 7: Net hours (apply efficiency and absenteeism)
        net_hours = gross_hours * efficiency_factor * (1 - absenteeism_factor)

        # Step 8: Capacity hours (multiply by operators)
        operators = line.max_operators or 1
        capacity_hours = net_hours * Decimal(str(operators))

        # Steps 9-11: Calculate utilization
        utilization_percent = Decimal("0")
        if capacity_hours > 0:
            utilization_percent = (demand_hours / capacity_hours) * 100

        # Step 12: Identify bottleneck
        is_bottleneck = utilization_percent >= self.bottleneck_threshold

        # Available capacity
        available_capacity = max(Decimal("0"), capacity_hours - demand_hours)

        return LineCapacityResult(
            line_id=line.id,
            line_code=line.line_code,
            line_name=line.line_name,
            department=line.department,
            working_days=working_days,
            shifts_per_day=shifts_per_day,
            hours_per_shift=hours_per_shift,
            operators_available=operators,
            efficiency_factor=efficiency_factor,
            absenteeism_factor=absenteeism_factor,
            gross_hours=gross_hours,
            net_hours=net_hours,
            capacity_hours=capacity_hours,
            demand_hours=demand_hours,
            demand_units=demand_units,
            utilization_percent=utilization_percent,
            is_bottleneck=is_bottleneck,
            available_capacity_hours=available_capacity
        )

    def _store_analysis_result(
        self,
        client_id: str,
        analysis_date: date,
        line: CapacityProductionLine,
        result: LineCapacityResult
    ) -> None:
        """Store analysis result in database."""
        analysis = CapacityAnalysis(
            client_id=client_id,
            analysis_date=analysis_date,
            line_id=line.id,
            line_code=line.line_code,
            department=line.department,
            working_days=result.working_days,
            shifts_per_day=result.shifts_per_day,
            hours_per_shift=result.hours_per_shift,
            operators_available=result.operators_available,
            efficiency_factor=result.efficiency_factor,
            absenteeism_factor=result.absenteeism_factor,
            gross_hours=result.gross_hours,
            net_hours=result.net_hours,
            capacity_hours=result.capacity_hours,
            demand_hours=result.demand_hours,
            demand_units=result.demand_units,
            utilization_percent=result.utilization_percent,
            is_bottleneck=result.is_bottleneck
        )
        self.db.add(analysis)
        self.db.commit()
