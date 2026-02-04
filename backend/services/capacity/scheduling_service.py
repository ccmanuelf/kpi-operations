"""
Scheduling Service
Phase B.2: Backend Services for Capacity Planning

Provides schedule generation, management, and commitment operations.
Supports auto-generation based on orders and capacity constraints.
"""
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from backend.schemas.capacity.schedule import (
    CapacitySchedule, CapacityScheduleDetail, ScheduleStatus
)
from backend.schemas.capacity.orders import CapacityOrder, OrderStatus, OrderPriority
from backend.schemas.capacity.production_lines import CapacityProductionLine
from backend.schemas.capacity.standards import CapacityProductionStandard
from backend.schemas.capacity.calendar import CapacityCalendar
from backend.exceptions.domain_exceptions import SchedulingError, ValidationError
from backend.events.bus import event_bus
from backend.events.domain_events import OrderScheduled, ScheduleCommitted


@dataclass
class ScheduleLineItem:
    """A single line item in the schedule."""
    order_id: int
    order_number: str
    style_code: str
    line_id: int
    line_code: str
    scheduled_date: date
    scheduled_quantity: int
    sequence: int


@dataclass
class ScheduleSummary:
    """Summary of a schedule."""
    schedule_id: int
    schedule_name: str
    status: ScheduleStatus
    period_start: date
    period_end: date
    total_orders: int
    total_quantity: int
    total_lines_used: int
    completion_percent: float


@dataclass
class GeneratedSchedule:
    """Result of schedule generation."""
    schedule_name: str
    period_start: date
    period_end: date
    items: List[ScheduleLineItem]
    unscheduled_orders: List[int]
    total_scheduled_quantity: int
    utilization_percent: Decimal


class SchedulingService:
    """
    Service for production scheduling operations.

    Provides:
    - Auto-generate schedules based on orders and capacity
    - Commit schedules for KPI tracking
    - Schedule summary and status management

    Multi-tenant isolation via client_id on all operations.
    """

    def __init__(self, db: Session):
        """
        Initialize scheduling service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def generate_schedule(
        self,
        client_id: str,
        schedule_name: str,
        period_start: date,
        period_end: date,
        order_ids: Optional[List[int]] = None,
        line_ids: Optional[List[int]] = None,
        prioritize_by: str = "required_date"
    ) -> GeneratedSchedule:
        """
        Auto-generate schedule based on orders and capacity.

        Algorithm:
        1. Get orders to schedule (filter by IDs or all pending)
        2. Sort orders by priority (date, priority level)
        3. Get available production lines
        4. Get calendar/capacity for period
        5. Assign orders to lines based on capacity
        6. Return generated schedule

        Args:
            client_id: Client ID for tenant isolation
            schedule_name: Name for the schedule
            period_start: Start date of schedule period
            period_end: End date of schedule period
            order_ids: Optional list of specific order IDs to schedule
            line_ids: Optional list of specific line IDs to use
            prioritize_by: "required_date" or "priority"

        Returns:
            GeneratedSchedule with scheduled items and unscheduled orders
        """
        # Get orders to schedule
        orders = self._get_orders_to_schedule(client_id, order_ids)
        if not orders:
            return GeneratedSchedule(
                schedule_name=schedule_name,
                period_start=period_start,
                period_end=period_end,
                items=[],
                unscheduled_orders=[],
                total_scheduled_quantity=0,
                utilization_percent=Decimal("0")
            )

        # Sort orders by priority
        orders = self._sort_orders(orders, prioritize_by)

        # Get production lines
        lines = self._get_production_lines(client_id, line_ids)
        if not lines:
            return GeneratedSchedule(
                schedule_name=schedule_name,
                period_start=period_start,
                period_end=period_end,
                items=[],
                unscheduled_orders=[o.id for o in orders],
                total_scheduled_quantity=0,
                utilization_percent=Decimal("0")
            )

        # Get SAM data for styles
        style_codes = list(set(o.style_code for o in orders))
        sam_by_style = self._get_sam_by_style(client_id, style_codes)

        # Get working days in period
        working_days = self._get_working_days(client_id, period_start, period_end)

        # Calculate capacity per line
        capacity_by_line = self._calculate_line_capacity(lines, len(working_days))

        # Assign orders to lines
        schedule_items, unscheduled = self._assign_orders_to_lines(
            orders=orders,
            lines=lines,
            working_days=working_days,
            sam_by_style=sam_by_style,
            capacity_by_line=capacity_by_line
        )

        # Calculate totals
        total_quantity = sum(item.scheduled_quantity for item in schedule_items)
        total_capacity = sum(capacity_by_line.values())
        total_demand = self._calculate_total_demand(schedule_items, sam_by_style)
        utilization = Decimal("0")
        if total_capacity > 0:
            utilization = (total_demand / total_capacity) * 100

        return GeneratedSchedule(
            schedule_name=schedule_name,
            period_start=period_start,
            period_end=period_end,
            items=schedule_items,
            unscheduled_orders=[o.id for o in unscheduled],
            total_scheduled_quantity=total_quantity,
            utilization_percent=utilization
        )

    def create_schedule(
        self,
        client_id: str,
        schedule_name: str,
        period_start: date,
        period_end: date,
        items: List[Dict]
    ) -> CapacitySchedule:
        """
        Create a new schedule with specified items.

        Args:
            client_id: Client ID for tenant isolation
            schedule_name: Name for the schedule
            period_start: Start date of schedule period
            period_end: End date of schedule period
            items: List of schedule items

        Returns:
            Created CapacitySchedule
        """
        # Create schedule header
        schedule = CapacitySchedule(
            client_id=client_id,
            schedule_name=schedule_name,
            period_start=period_start,
            period_end=period_end,
            status=ScheduleStatus.DRAFT
        )
        self.db.add(schedule)
        self.db.flush()

        # Create schedule details
        for item in items:
            detail = CapacityScheduleDetail(
                schedule_id=schedule.id,
                client_id=client_id,
                order_id=item.get("order_id"),
                order_number=item.get("order_number"),
                style_code=item.get("style_code"),
                line_id=item.get("line_id"),
                line_code=item.get("line_code"),
                scheduled_date=item.get("scheduled_date"),
                scheduled_quantity=item.get("scheduled_quantity", 0),
                sequence=item.get("sequence", 1)
            )
            self.db.add(detail)

            # Emit event
            event = OrderScheduled(
                aggregate_id=f"schedule_{schedule.id}",
                client_id=client_id,
                order_id=str(item.get("order_id")),
                line_id=str(item.get("line_id")),
                scheduled_date=item.get("scheduled_date"),
                scheduled_quantity=item.get("scheduled_quantity", 0)
            )
            event_bus.collect(event)

        self.db.commit()
        return schedule

    def commit_schedule(
        self,
        client_id: str,
        schedule_id: int,
        committed_by: int,
        kpi_commitments: Optional[Dict] = None
    ) -> CapacitySchedule:
        """
        Commit a schedule for KPI tracking.

        Args:
            client_id: Client ID for tenant isolation
            schedule_id: Schedule ID to commit
            committed_by: User ID committing the schedule
            kpi_commitments: Optional KPI targets to commit

        Returns:
            Updated CapacitySchedule

        Raises:
            SchedulingError: If schedule not found or not in DRAFT status
        """
        schedule = self.db.query(CapacitySchedule).filter(
            CapacitySchedule.client_id == client_id,
            CapacitySchedule.id == schedule_id
        ).first()

        if not schedule:
            raise SchedulingError(
                message=f"Schedule {schedule_id} not found",
                order_id=str(schedule_id)
            )

        if schedule.status != ScheduleStatus.DRAFT:
            raise SchedulingError(
                message=f"Schedule {schedule_id} is not in DRAFT status",
                order_id=str(schedule_id)
            )

        # Update schedule
        schedule.status = ScheduleStatus.COMMITTED
        schedule.committed_at = date.today()
        schedule.committed_by = committed_by
        schedule.kpi_commitments_json = kpi_commitments

        # Emit event
        event = ScheduleCommitted(
            aggregate_id=f"schedule_{schedule.id}",
            client_id=client_id,
            schedule_id=schedule.id,
            schedule_name=schedule.schedule_name,
            committed_by=committed_by,
            kpi_commitments=kpi_commitments or {},
            period_start=schedule.period_start,
            period_end=schedule.period_end
        )
        event_bus.collect(event)

        self.db.commit()
        return schedule

    def activate_schedule(
        self,
        client_id: str,
        schedule_id: int
    ) -> CapacitySchedule:
        """
        Activate a committed schedule for execution.

        Args:
            client_id: Client ID for tenant isolation
            schedule_id: Schedule ID to activate

        Returns:
            Updated CapacitySchedule
        """
        schedule = self.db.query(CapacitySchedule).filter(
            CapacitySchedule.client_id == client_id,
            CapacitySchedule.id == schedule_id
        ).first()

        if not schedule:
            raise SchedulingError(
                message=f"Schedule {schedule_id} not found",
                order_id=str(schedule_id)
            )

        if schedule.status != ScheduleStatus.COMMITTED:
            raise SchedulingError(
                message=f"Schedule {schedule_id} must be COMMITTED before activation",
                order_id=str(schedule_id)
            )

        schedule.status = ScheduleStatus.ACTIVE
        self.db.commit()
        return schedule

    def get_schedule_summary(
        self,
        client_id: str,
        schedule_id: int
    ) -> Optional[ScheduleSummary]:
        """
        Get summary of a schedule.

        Args:
            client_id: Client ID for tenant isolation
            schedule_id: Schedule ID

        Returns:
            ScheduleSummary or None if not found
        """
        schedule = self.db.query(CapacitySchedule).filter(
            CapacitySchedule.client_id == client_id,
            CapacitySchedule.id == schedule_id
        ).first()

        if not schedule:
            return None

        # Get aggregated details
        details = self.db.query(
            func.count(CapacityScheduleDetail.id).label('total_items'),
            func.sum(CapacityScheduleDetail.scheduled_quantity).label('total_scheduled'),
            func.sum(CapacityScheduleDetail.completed_quantity).label('total_completed'),
            func.count(func.distinct(CapacityScheduleDetail.order_id)).label('total_orders'),
            func.count(func.distinct(CapacityScheduleDetail.line_id)).label('total_lines')
        ).filter(
            CapacityScheduleDetail.schedule_id == schedule_id,
            CapacityScheduleDetail.client_id == client_id
        ).first()

        total_scheduled = int(details.total_scheduled or 0)
        total_completed = int(details.total_completed or 0)
        completion_percent = 0.0
        if total_scheduled > 0:
            completion_percent = (total_completed / total_scheduled) * 100

        return ScheduleSummary(
            schedule_id=schedule.id,
            schedule_name=schedule.schedule_name,
            status=schedule.status,
            period_start=schedule.period_start,
            period_end=schedule.period_end,
            total_orders=int(details.total_orders or 0),
            total_quantity=total_scheduled,
            total_lines_used=int(details.total_lines or 0),
            completion_percent=completion_percent
        )

    def list_schedules(
        self,
        client_id: str,
        status: Optional[ScheduleStatus] = None,
        period_start: Optional[date] = None,
        period_end: Optional[date] = None
    ) -> List[CapacitySchedule]:
        """
        List schedules with optional filters.

        Args:
            client_id: Client ID for tenant isolation
            status: Optional status filter
            period_start: Optional period start filter
            period_end: Optional period end filter

        Returns:
            List of CapacitySchedule
        """
        query = self.db.query(CapacitySchedule).filter(
            CapacitySchedule.client_id == client_id
        )

        if status:
            query = query.filter(CapacitySchedule.status == status)
        if period_start:
            query = query.filter(CapacitySchedule.period_end >= period_start)
        if period_end:
            query = query.filter(CapacitySchedule.period_start <= period_end)

        return query.order_by(CapacitySchedule.created_at.desc()).all()

    def _get_orders_to_schedule(
        self,
        client_id: str,
        order_ids: Optional[List[int]] = None
    ) -> List[CapacityOrder]:
        """Get orders available for scheduling."""
        query = self.db.query(CapacityOrder).filter(
            CapacityOrder.client_id == client_id,
            CapacityOrder.status.in_([OrderStatus.DRAFT, OrderStatus.CONFIRMED])
        )

        if order_ids:
            query = query.filter(CapacityOrder.id.in_(order_ids))

        return query.all()

    def _sort_orders(
        self,
        orders: List[CapacityOrder],
        prioritize_by: str
    ) -> List[CapacityOrder]:
        """Sort orders by priority."""
        priority_order = {
            OrderPriority.URGENT: 0,
            OrderPriority.HIGH: 1,
            OrderPriority.NORMAL: 2,
            OrderPriority.LOW: 3
        }

        if prioritize_by == "priority":
            return sorted(orders, key=lambda o: (
                priority_order.get(o.priority, 2),
                o.required_date
            ))
        else:
            return sorted(orders, key=lambda o: (
                o.required_date,
                priority_order.get(o.priority, 2)
            ))

    def _get_production_lines(
        self,
        client_id: str,
        line_ids: Optional[List[int]] = None
    ) -> List[CapacityProductionLine]:
        """Get available production lines."""
        query = self.db.query(CapacityProductionLine).filter(
            CapacityProductionLine.client_id == client_id,
            CapacityProductionLine.is_active == True
        )

        if line_ids:
            query = query.filter(CapacityProductionLine.id.in_(line_ids))

        return query.all()

    def _get_sam_by_style(
        self,
        client_id: str,
        style_codes: List[str]
    ) -> Dict[str, Decimal]:
        """Get total SAM by style code."""
        if not style_codes:
            return {}

        results = self.db.query(
            CapacityProductionStandard.style_code,
            func.sum(CapacityProductionStandard.sam_minutes).label('total_sam')
        ).filter(
            CapacityProductionStandard.client_id == client_id,
            CapacityProductionStandard.style_code.in_(style_codes)
        ).group_by(CapacityProductionStandard.style_code).all()

        return {r.style_code: Decimal(str(r.total_sam or 0)) for r in results}

    def _get_working_days(
        self,
        client_id: str,
        period_start: date,
        period_end: date
    ) -> List[date]:
        """Get working days in period."""
        calendars = self.db.query(CapacityCalendar).filter(
            CapacityCalendar.client_id == client_id,
            CapacityCalendar.calendar_date >= period_start,
            CapacityCalendar.calendar_date <= period_end,
            CapacityCalendar.is_working_day == True
        ).order_by(CapacityCalendar.calendar_date).all()

        if calendars:
            return [c.calendar_date for c in calendars]

        # Default: all weekdays in period
        working_days = []
        current = period_start
        while current <= period_end:
            if current.weekday() < 5:  # Mon-Fri
                working_days.append(current)
            current += timedelta(days=1)

        return working_days

    def _calculate_line_capacity(
        self,
        lines: List[CapacityProductionLine],
        working_days: int
    ) -> Dict[int, Decimal]:
        """Calculate capacity hours per line."""
        capacity_by_line = {}
        for line in lines:
            # Assume 8 hours per day, apply efficiency
            base_hours = Decimal(str(working_days * 8))
            efficiency = Decimal(str(line.efficiency_factor or 0.85))
            absenteeism = Decimal(str(line.absenteeism_factor or 0.05))
            operators = line.max_operators or 1

            net_hours = base_hours * efficiency * (1 - absenteeism)
            capacity_hours = net_hours * Decimal(str(operators))
            capacity_by_line[line.id] = capacity_hours

        return capacity_by_line

    def _assign_orders_to_lines(
        self,
        orders: List[CapacityOrder],
        lines: List[CapacityProductionLine],
        working_days: List[date],
        sam_by_style: Dict[str, Decimal],
        capacity_by_line: Dict[int, Decimal]
    ) -> Tuple[List[ScheduleLineItem], List[CapacityOrder]]:
        """Assign orders to lines based on capacity."""
        schedule_items: List[ScheduleLineItem] = []
        unscheduled: List[CapacityOrder] = []

        # Track remaining capacity per line
        remaining_capacity = dict(capacity_by_line)

        # Track line assignment by day
        line_day_sequence: Dict[Tuple[int, date], int] = {}

        for order in orders:
            sam = sam_by_style.get(order.style_code, Decimal("1.0"))
            order_hours = (Decimal(str(order.order_quantity)) * sam) / Decimal("60")

            # Find best line with capacity
            assigned = False
            for line in lines:
                if remaining_capacity[line.id] >= order_hours:
                    # Find the best date to schedule
                    for work_date in working_days:
                        if work_date >= order.required_date - timedelta(days=7):
                            # Get sequence for this line/date
                            key = (line.id, work_date)
                            seq = line_day_sequence.get(key, 0) + 1
                            line_day_sequence[key] = seq

                            schedule_items.append(ScheduleLineItem(
                                order_id=order.id,
                                order_number=order.order_number,
                                style_code=order.style_code,
                                line_id=line.id,
                                line_code=line.line_code,
                                scheduled_date=work_date,
                                scheduled_quantity=order.order_quantity,
                                sequence=seq
                            ))

                            remaining_capacity[line.id] -= order_hours
                            assigned = True
                            break
                    if assigned:
                        break

            if not assigned:
                unscheduled.append(order)

        return schedule_items, unscheduled

    def _calculate_total_demand(
        self,
        items: List[ScheduleLineItem],
        sam_by_style: Dict[str, Decimal]
    ) -> Decimal:
        """Calculate total demand hours from schedule items."""
        total = Decimal("0")
        for item in items:
            sam = sam_by_style.get(item.style_code, Decimal("1.0"))
            hours = (Decimal(str(item.scheduled_quantity)) * sam) / Decimal("60")
            total += hours
        return total
