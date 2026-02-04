"""
KPI Integration Service
Phase B.2 & B.8: Backend Services for Capacity Planning - Complete KPI Integration

Provides integration between capacity planning and KPI tracking.
Reads actuals from PRODUCTION_ENTRY and WORK_ORDER tables.
Stores KPI commitments and calculates variance.

Phase B.8 Enhancements:
- Read actual KPIs from production data (efficiency, performance, quality, OTD)
- Store KPI commitments from schedules
- Calculate variance and emit alerts when threshold exceeded
- Provide KPI history for trending
"""
from decimal import Decimal
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case

from backend.schemas.capacity.kpi_commitment import CapacityKPICommitment
from backend.schemas.capacity.schedule import CapacitySchedule, CapacityScheduleDetail, ScheduleStatus
from backend.schemas.production_entry import ProductionEntry
from backend.schemas.work_order import WorkOrder
from backend.events.bus import event_bus
from backend.events.domain_events import KPIVarianceAlert
from backend.exceptions import ResourceNotFoundError


@dataclass
class KPIActual:
    """Actual KPI value from production data."""
    kpi_key: str
    kpi_name: str
    actual_value: Decimal
    period_start: date
    period_end: date
    source: str  # 'production_entry' or 'work_order'


@dataclass
class KPIVariance:
    """Variance between committed and actual KPI."""
    kpi_key: str
    kpi_name: str
    committed_value: Decimal
    actual_value: Decimal
    variance: Decimal
    variance_percent: Decimal
    is_on_target: bool
    alert_level: Optional[str]  # 'warning', 'critical', None


@dataclass
class KPICommitmentResult:
    """Result of storing KPI commitments."""
    schedule_id: int
    kpis_stored: int
    kpi_keys: List[str]


# Standard KPI definitions
STANDARD_KPIS = {
    "efficiency": {
        "name": "Production Efficiency",
        "unit": "percent",
        "direction": "higher_better",
        "default_target": Decimal("85.0")
    },
    "performance": {
        "name": "Performance",
        "unit": "percent",
        "direction": "higher_better",
        "default_target": Decimal("90.0")
    },
    "quality": {
        "name": "Quality/Yield Rate",
        "unit": "percent",
        "direction": "higher_better",
        "default_target": Decimal("98.5")
    },
    "quality_rate": {
        "name": "Quality Rate",
        "unit": "percent",
        "direction": "higher_better",
        "default_target": Decimal("98.5")
    },
    "otd": {
        "name": "On-Time Delivery",
        "unit": "percent",
        "direction": "higher_better",
        "default_target": Decimal("95.0")
    },
    "otd_rate": {
        "name": "On-Time Delivery",
        "unit": "percent",
        "direction": "higher_better",
        "default_target": Decimal("95.0")
    },
    "utilization": {
        "name": "Capacity Utilization",
        "unit": "percent",
        "direction": "target",
        "default_target": Decimal("85.0")
    },
    "output": {
        "name": "Total Output",
        "unit": "units",
        "direction": "higher_better",
        "default_target": Decimal("0")
    },
    "oee": {
        "name": "Overall Equipment Effectiveness",
        "unit": "percent",
        "direction": "higher_better",
        "default_target": Decimal("85.0")
    }
}

# KPI name mapping for commitments
KPI_NAMES = {
    'efficiency': 'Efficiency',
    'performance': 'Performance',
    'quality': 'Quality Rate',
    'quality_rate': 'Quality Rate',
    'otd': 'On-Time Delivery',
    'otd_rate': 'On-Time Delivery',
    'oee': 'OEE',
    'utilization': 'Capacity Utilization',
    'output': 'Total Output'
}


class KPIIntegrationService:
    """
    Service for KPI integration between capacity planning and production.

    Provides:
    - Read actuals from PRODUCTION_ENTRY, WORK_ORDER
    - Store KPI commitments for schedules
    - Calculate variance between committed and actual
    - Emit alerts when variance exceeds threshold

    Multi-tenant isolation via client_id on all operations.
    """

    def __init__(self, db: Session, variance_threshold: Decimal = Decimal("10.0")):
        """
        Initialize KPI integration service.

        Args:
            db: SQLAlchemy database session
            variance_threshold: Default variance threshold for alerts (percent)
        """
        self.db = db
        self.variance_threshold = variance_threshold

    def get_actual_kpis(
        self,
        client_id: str,
        period_start: date,
        period_end: date,
        kpi_keys: Optional[List[str]] = None
    ) -> List[KPIActual]:
        """
        Get actual KPI values from production data.

        Reads from:
        - PRODUCTION_ENTRY: efficiency, quality, output
        - WORK_ORDER: otd (on-time delivery)

        Args:
            client_id: Client ID for tenant isolation
            period_start: Start date of period
            period_end: End date of period
            kpi_keys: Optional list of specific KPIs to retrieve

        Returns:
            List of KPIActual values
        """
        actuals: List[KPIActual] = []
        keys_to_get = kpi_keys or list(STANDARD_KPIS.keys())

        if "efficiency" in keys_to_get:
            efficiency = self._get_efficiency_actual(client_id, period_start, period_end)
            if efficiency is not None:
                actuals.append(KPIActual(
                    kpi_key="efficiency",
                    kpi_name="Production Efficiency",
                    actual_value=efficiency,
                    period_start=period_start,
                    period_end=period_end,
                    source="production_entry"
                ))

        if "performance" in keys_to_get:
            performance = self.get_performance_actual(client_id, period_start, period_end)
            if performance is not None:
                actuals.append(KPIActual(
                    kpi_key="performance",
                    kpi_name="Performance",
                    actual_value=performance,
                    period_start=period_start,
                    period_end=period_end,
                    source="production_entry"
                ))

        if "quality" in keys_to_get:
            quality = self._get_quality_actual(client_id, period_start, period_end)
            if quality is not None:
                actuals.append(KPIActual(
                    kpi_key="quality",
                    kpi_name="Quality/Yield Rate",
                    actual_value=quality,
                    period_start=period_start,
                    period_end=period_end,
                    source="production_entry"
                ))

        if "output" in keys_to_get:
            output = self._get_output_actual(client_id, period_start, period_end)
            if output is not None:
                actuals.append(KPIActual(
                    kpi_key="output",
                    kpi_name="Total Output",
                    actual_value=output,
                    period_start=period_start,
                    period_end=period_end,
                    source="production_entry"
                ))

        if "otd" in keys_to_get:
            otd = self._get_otd_actual(client_id, period_start, period_end)
            if otd is not None:
                actuals.append(KPIActual(
                    kpi_key="otd",
                    kpi_name="On-Time Delivery",
                    actual_value=otd,
                    period_start=period_start,
                    period_end=period_end,
                    source="work_order"
                ))

        if "utilization" in keys_to_get:
            utilization = self._get_utilization_actual(client_id, period_start, period_end)
            if utilization is not None:
                actuals.append(KPIActual(
                    kpi_key="utilization",
                    kpi_name="Capacity Utilization",
                    actual_value=utilization,
                    period_start=period_start,
                    period_end=period_end,
                    source="production_entry"
                ))

        return actuals

    def get_actual_kpis_dict(
        self,
        client_id: str,
        period_start: date,
        period_end: date
    ) -> Dict[str, Any]:
        """
        Get actual KPI values from production data as a dictionary.

        Phase B.8: Complete KPI Integration
        Reads from:
        - PRODUCTION_ENTRY for efficiency, performance
        - PRODUCTION_ENTRY for quality (units, defects, scrap)
        - WORK_ORDER for OTD calculation

        Args:
            client_id: Client ID for tenant isolation
            period_start: Start date of period
            period_end: End date of period

        Returns:
            Dict containing all actual KPI values and raw metrics
        """
        # Query PRODUCTION_ENTRY for efficiency, performance, and quality metrics
        efficiency_result = self.db.query(
            func.avg(ProductionEntry.efficiency_percentage).label('avg_efficiency'),
            func.avg(ProductionEntry.performance_percentage).label('avg_performance'),
            func.sum(ProductionEntry.units_produced).label('total_units'),
            func.sum(ProductionEntry.defect_count).label('total_defects'),
            func.sum(ProductionEntry.scrap_count).label('total_scrap')
        ).filter(
            ProductionEntry.client_id == client_id,
            ProductionEntry.production_date >= period_start,
            ProductionEntry.production_date <= period_end
        ).first()

        # Calculate quality rate: (good_units / total_units) * 100
        total_units = int(efficiency_result.total_units or 0)
        total_defects = int(efficiency_result.total_defects or 0)
        total_scrap = int(efficiency_result.total_scrap or 0)
        good_units = total_units - total_defects - total_scrap
        quality_rate = (good_units / total_units * 100) if total_units > 0 else 0.0

        # Query WORK_ORDER for OTD calculation
        # OTD = (on_time_orders / total_orders) * 100
        otd_result = self.db.query(
            func.count(WorkOrder.work_order_id).label('total_orders'),
            func.sum(
                case(
                    (WorkOrder.actual_delivery_date <= WorkOrder.required_date, 1),
                    else_=0
                )
            ).label('on_time_orders')
        ).filter(
            WorkOrder.client_id == client_id,
            WorkOrder.actual_delivery_date >= period_start,
            WorkOrder.actual_delivery_date <= period_end,
            WorkOrder.status == 'CLOSED'
        ).first()

        total_orders = int(otd_result.total_orders or 0)
        on_time_orders = int(otd_result.on_time_orders or 0)
        otd_rate = (on_time_orders / total_orders * 100) if total_orders > 0 else 0.0

        # Calculate OEE = Availability * Performance * Quality (simplified)
        avg_efficiency = float(efficiency_result.avg_efficiency or 0)
        avg_performance = float(efficiency_result.avg_performance or 0)
        oee = (avg_efficiency / 100) * (avg_performance / 100) * (quality_rate / 100) * 100 if total_units > 0 else 0.0

        return {
            'efficiency': avg_efficiency,
            'performance': avg_performance,
            'quality_rate': quality_rate,
            'otd_rate': otd_rate,
            'oee': oee,
            'total_units': total_units,
            'total_defects': total_defects,
            'total_scrap': total_scrap,
            'good_units': good_units,
            'total_orders': total_orders,
            'on_time_orders': on_time_orders,
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat()
        }

    def store_kpi_commitments(
        self,
        client_id: str,
        schedule_id: int,
        kpi_targets: Dict[str, Decimal]
    ) -> KPICommitmentResult:
        """
        Store KPI commitments for a schedule.

        Args:
            client_id: Client ID for tenant isolation
            schedule_id: Schedule ID to store commitments for
            kpi_targets: Dict of kpi_key -> target_value

        Returns:
            KPICommitmentResult with stored KPIs
        """
        # Get schedule for period
        schedule = self.db.query(CapacitySchedule).filter(
            CapacitySchedule.client_id == client_id,
            CapacitySchedule.id == schedule_id
        ).first()

        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")

        stored_keys = []
        for kpi_key, target_value in kpi_targets.items():
            kpi_info = STANDARD_KPIS.get(kpi_key, {"name": kpi_key})

            commitment = CapacityKPICommitment(
                client_id=client_id,
                schedule_id=schedule_id,
                kpi_key=kpi_key,
                kpi_name=kpi_info.get("name", kpi_key),
                period_start=schedule.period_start,
                period_end=schedule.period_end,
                committed_value=target_value
            )
            self.db.add(commitment)
            stored_keys.append(kpi_key)

        self.db.commit()

        return KPICommitmentResult(
            schedule_id=schedule_id,
            kpis_stored=len(stored_keys),
            kpi_keys=stored_keys
        )

    def store_kpi_commitments_list(
        self,
        client_id: str,
        schedule_id: int,
        commitments: Dict[str, Decimal]
    ) -> List[CapacityKPICommitment]:
        """
        Store committed KPI targets from schedule and return the list of commitments.

        Phase B.8: Complete KPI Integration

        Args:
            client_id: Client ID
            schedule_id: Schedule being committed
            commitments: Dict of kpi_key -> committed_value
                e.g., {'efficiency': 85.0, 'quality': 98.0, 'otd': 95.0}

        Returns:
            List of CapacityKPICommitment objects created

        Raises:
            ResourceNotFoundError: If schedule not found
        """
        # Get schedule for period dates
        schedule = self.db.query(CapacitySchedule).filter(
            CapacitySchedule.id == schedule_id,
            CapacitySchedule.client_id == client_id
        ).first()

        if not schedule:
            raise ResourceNotFoundError("CapacitySchedule", str(schedule_id))

        stored: List[CapacityKPICommitment] = []
        for kpi_key, committed_value in commitments.items():
            kpi_name = KPI_NAMES.get(kpi_key, STANDARD_KPIS.get(kpi_key, {}).get("name", kpi_key))

            commitment = CapacityKPICommitment(
                client_id=client_id,
                schedule_id=schedule_id,
                kpi_key=kpi_key,
                kpi_name=kpi_name,
                period_start=schedule.period_start,
                period_end=schedule.period_end,
                committed_value=Decimal(str(committed_value))
            )
            self.db.add(commitment)
            stored.append(commitment)

        self.db.commit()

        # Refresh to get IDs
        for c in stored:
            self.db.refresh(c)

        return stored

    def calculate_variance(
        self,
        client_id: str,
        schedule_id: int,
        update_actuals: bool = True
    ) -> List[KPIVariance]:
        """
        Calculate variance between committed and actual KPIs.

        Args:
            client_id: Client ID for tenant isolation
            schedule_id: Schedule ID
            update_actuals: If True, update actual values in database

        Returns:
            List of KPIVariance for each committed KPI
        """
        # Get schedule
        schedule = self.db.query(CapacitySchedule).filter(
            CapacitySchedule.client_id == client_id,
            CapacitySchedule.id == schedule_id
        ).first()

        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")

        # Get commitments
        commitments = self.db.query(CapacityKPICommitment).filter(
            CapacityKPICommitment.client_id == client_id,
            CapacityKPICommitment.schedule_id == schedule_id
        ).all()

        if not commitments:
            return []

        # Get actuals
        kpi_keys = [c.kpi_key for c in commitments]
        actuals = self.get_actual_kpis(
            client_id=client_id,
            period_start=schedule.period_start,
            period_end=schedule.period_end,
            kpi_keys=kpi_keys
        )
        actuals_by_key = {a.kpi_key: a.actual_value for a in actuals}

        # Calculate variance for each commitment
        variances: List[KPIVariance] = []
        for commitment in commitments:
            actual_value = actuals_by_key.get(commitment.kpi_key)

            if actual_value is None:
                continue

            committed = Decimal(str(commitment.committed_value))
            actual = Decimal(str(actual_value))
            variance = actual - committed

            variance_percent = Decimal("0")
            if committed != 0:
                variance_percent = (variance / committed) * 100

            # Determine alert level
            alert_level = None
            is_on_target = abs(variance_percent) <= self.variance_threshold
            if not is_on_target:
                if abs(variance_percent) > self.variance_threshold * 2:
                    alert_level = "critical"
                else:
                    alert_level = "warning"

            variances.append(KPIVariance(
                kpi_key=commitment.kpi_key,
                kpi_name=commitment.kpi_name or commitment.kpi_key,
                committed_value=committed,
                actual_value=actual,
                variance=variance,
                variance_percent=variance_percent,
                is_on_target=is_on_target,
                alert_level=alert_level
            ))

            # Update commitment with actual
            if update_actuals:
                commitment.actual_value = actual
                commitment.calculate_variance()

        if update_actuals:
            self.db.commit()

        return variances

    def calculate_variance_detailed(
        self,
        client_id: str,
        schedule_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Calculate variance between committed and actual KPIs with detailed output.

        Phase B.8: Complete KPI Integration
        Emits KPIVarianceAlert event if variance > 10%.

        Args:
            client_id: Client ID for tenant isolation
            schedule_id: Optional schedule ID (if None, returns all)

        Returns:
            List of dicts with detailed variance information
        """
        # Get commitments
        query = self.db.query(CapacityKPICommitment).filter(
            CapacityKPICommitment.client_id == client_id
        )
        if schedule_id:
            query = query.filter(CapacityKPICommitment.schedule_id == schedule_id)

        commitments = query.all()

        if not commitments:
            return []

        results: List[Dict[str, Any]] = []
        for commitment in commitments:
            # Get actuals for the commitment period using dict method
            actuals = self.get_actual_kpis_dict(
                client_id,
                commitment.period_start,
                commitment.period_end
            )

            # Map kpi_key to the correct actual value
            kpi_key = commitment.kpi_key
            actual_value = actuals.get(kpi_key)
            if actual_value is None:
                # Try alternate key names
                if kpi_key == 'quality':
                    actual_value = actuals.get('quality_rate', 0)
                elif kpi_key == 'otd':
                    actual_value = actuals.get('otd_rate', 0)
                else:
                    actual_value = 0

            committed_value = float(commitment.committed_value)

            variance = actual_value - committed_value
            variance_percent = (variance / committed_value * 100) if committed_value != 0 else 0

            # Update commitment record
            commitment.actual_value = Decimal(str(actual_value))
            commitment.variance = Decimal(str(variance))
            commitment.variance_percent = Decimal(str(variance_percent))

            # Emit alert if variance exceeds threshold
            if abs(variance_percent) > 10:
                event = KPIVarianceAlert(
                    aggregate_id=f"kpi_commitment_{commitment.id}",
                    client_id=client_id,
                    kpi_key=commitment.kpi_key,
                    kpi_name=commitment.kpi_name,
                    committed_value=commitment.committed_value,
                    actual_value=Decimal(str(actual_value)),
                    variance_percent=Decimal(str(variance_percent)),
                    threshold_percent=Decimal("10.0"),
                    alert_level="critical" if abs(variance_percent) > 15 else "warning"
                )
                event_bus.collect(event)

            # Determine status
            if abs(variance_percent) <= 5:
                status = 'on_target'
            elif abs(variance_percent) <= 10:
                status = 'warning'
            else:
                status = 'critical'

            results.append({
                'kpi_key': commitment.kpi_key,
                'kpi_name': commitment.kpi_name,
                'committed': committed_value,
                'actual': actual_value,
                'variance': variance,
                'variance_percent': variance_percent,
                'period_start': commitment.period_start.isoformat(),
                'period_end': commitment.period_end.isoformat(),
                'status': status
            })

        self.db.commit()

        return results

    def check_variance_alerts(
        self,
        client_id: str,
        schedule_id: int,
        threshold: Optional[Decimal] = None
    ) -> List[KPIVariance]:
        """
        Check for variance alerts and emit events.

        Args:
            client_id: Client ID for tenant isolation
            schedule_id: Schedule ID
            threshold: Optional custom threshold (uses default if not provided)

        Returns:
            List of KPIVariance that exceeded threshold
        """
        if threshold is not None:
            self.variance_threshold = threshold

        variances = self.calculate_variance(client_id, schedule_id)
        alerts = [v for v in variances if v.alert_level is not None]

        for alert in alerts:
            event = KPIVarianceAlert(
                aggregate_id=f"kpi_variance_{client_id}_{schedule_id}_{alert.kpi_key}",
                client_id=client_id,
                kpi_key=alert.kpi_key,
                kpi_name=alert.kpi_name,
                committed_value=alert.committed_value,
                actual_value=alert.actual_value,
                variance_percent=alert.variance_percent,
                threshold_percent=self.variance_threshold,
                alert_level=alert.alert_level
            )
            event_bus.collect(event)

        return alerts

    def get_kpi_commitments(
        self,
        client_id: str,
        schedule_id: int
    ) -> List[CapacityKPICommitment]:
        """
        Get KPI commitments for a schedule.

        Args:
            client_id: Client ID for tenant isolation
            schedule_id: Schedule ID

        Returns:
            List of CapacityKPICommitment
        """
        return self.db.query(CapacityKPICommitment).filter(
            CapacityKPICommitment.client_id == client_id,
            CapacityKPICommitment.schedule_id == schedule_id
        ).all()

    def get_kpi_history(
        self,
        client_id: str,
        kpi_key: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict]:
        """
        Get historical KPI values over time.

        Args:
            client_id: Client ID for tenant isolation
            kpi_key: KPI key to retrieve history for
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of dicts with period, committed, actual values
        """
        query = self.db.query(CapacityKPICommitment).filter(
            CapacityKPICommitment.client_id == client_id,
            CapacityKPICommitment.kpi_key == kpi_key
        )

        if start_date:
            query = query.filter(CapacityKPICommitment.period_start >= start_date)
        if end_date:
            query = query.filter(CapacityKPICommitment.period_end <= end_date)

        commitments = query.order_by(CapacityKPICommitment.period_start).all()

        return [
            {
                "period_start": c.period_start,
                "period_end": c.period_end,
                "committed_value": float(c.committed_value) if c.committed_value else None,
                "actual_value": float(c.actual_value) if c.actual_value else None,
                "variance": float(c.variance) if c.variance else None,
                "variance_percent": float(c.variance_percent) if c.variance_percent else None
            }
            for c in commitments
        ]

    def get_kpi_history_trending(
        self,
        client_id: str,
        kpi_key: str,
        periods: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Get historical KPI values for trending over monthly periods.

        Phase B.8: Complete KPI Integration
        Retrieves historical data for the specified number of periods going back.

        Args:
            client_id: Client ID for tenant isolation
            kpi_key: KPI key to retrieve history for
            periods: Number of monthly periods to retrieve (default 12)

        Returns:
            List of dicts with period info, committed, and actual values
        """
        today = date.today()
        results: List[Dict[str, Any]] = []

        for i in range(periods - 1, -1, -1):
            # Calculate period dates (monthly)
            period_end = today - relativedelta(months=i)
            period_start = date(period_end.year, period_end.month, 1)
            if period_end.month == 12:
                period_end = date(period_end.year, 12, 31)
            else:
                period_end = date(period_end.year, period_end.month + 1, 1) - timedelta(days=1)

            # Check for commitments in this period
            commitment = self.db.query(CapacityKPICommitment).filter(
                CapacityKPICommitment.client_id == client_id,
                CapacityKPICommitment.kpi_key == kpi_key,
                CapacityKPICommitment.period_start <= period_end,
                CapacityKPICommitment.period_end >= period_start
            ).first()

            # Get actual value from production data
            actuals = self.get_actual_kpis_dict(client_id, period_start, period_end)
            actual_value = actuals.get(kpi_key)
            if actual_value is None and kpi_key == 'quality':
                actual_value = actuals.get('quality_rate')
            elif actual_value is None and kpi_key == 'otd':
                actual_value = actuals.get('otd_rate')

            committed_value = float(commitment.committed_value) if commitment and commitment.committed_value else None

            results.append({
                'period_start': period_start.isoformat(),
                'period_end': period_end.isoformat(),
                'period_label': period_start.strftime('%b %Y'),
                'committed_value': committed_value,
                'actual_value': actual_value,
                'variance': (actual_value - committed_value) if actual_value is not None and committed_value is not None else None,
                'variance_percent': ((actual_value - committed_value) / committed_value * 100) if actual_value is not None and committed_value else None
            })

        return results

    def get_performance_actual(
        self,
        client_id: str,
        period_start: date,
        period_end: date
    ) -> Optional[Decimal]:
        """
        Get performance percentage from production entries.

        Performance = Actual output / Expected output * 100
        Uses average of performance_percentage field.

        Args:
            client_id: Client ID for tenant isolation
            period_start: Start date of period
            period_end: End date of period

        Returns:
            Performance percentage as Decimal, or None if no data
        """
        result = self.db.query(
            func.avg(ProductionEntry.performance_percentage)
        ).filter(
            ProductionEntry.client_id == client_id,
            ProductionEntry.production_date >= period_start,
            ProductionEntry.production_date <= period_end,
            ProductionEntry.performance_percentage.isnot(None)
        ).scalar()

        return Decimal(str(result)) if result else None

    def _get_efficiency_actual(
        self,
        client_id: str,
        period_start: date,
        period_end: date
    ) -> Optional[Decimal]:
        """Get efficiency from production entries."""
        result = self.db.query(
            func.avg(ProductionEntry.efficiency_percentage)
        ).filter(
            ProductionEntry.client_id == client_id,
            ProductionEntry.production_date >= period_start,
            ProductionEntry.production_date <= period_end,
            ProductionEntry.efficiency_percentage.isnot(None)
        ).scalar()

        return Decimal(str(result)) if result else None

    def _get_quality_actual(
        self,
        client_id: str,
        period_start: date,
        period_end: date
    ) -> Optional[Decimal]:
        """Get quality rate from production entries."""
        # Quality = (Total - Defects - Scrap) / Total * 100
        result = self.db.query(
            func.sum(ProductionEntry.units_produced).label('total'),
            func.sum(ProductionEntry.defect_count).label('defects'),
            func.sum(ProductionEntry.scrap_count).label('scrap')
        ).filter(
            ProductionEntry.client_id == client_id,
            ProductionEntry.production_date >= period_start,
            ProductionEntry.production_date <= period_end
        ).first()

        if result and result.total and result.total > 0:
            total = Decimal(str(result.total))
            defects = Decimal(str(result.defects or 0))
            scrap = Decimal(str(result.scrap or 0))
            good_units = total - defects - scrap
            return (good_units / total) * 100

        return None

    def _get_output_actual(
        self,
        client_id: str,
        period_start: date,
        period_end: date
    ) -> Optional[Decimal]:
        """Get total output from production entries."""
        result = self.db.query(
            func.sum(ProductionEntry.units_produced)
        ).filter(
            ProductionEntry.client_id == client_id,
            ProductionEntry.production_date >= period_start,
            ProductionEntry.production_date <= period_end
        ).scalar()

        return Decimal(str(result)) if result else None

    def _get_otd_actual(
        self,
        client_id: str,
        period_start: date,
        period_end: date
    ) -> Optional[Decimal]:
        """Get on-time delivery rate from work orders."""
        # OTD = Orders completed on time / Total completed orders * 100
        total_completed = self.db.query(func.count(WorkOrder.work_order_id)).filter(
            WorkOrder.client_id == client_id,
            WorkOrder.status == "CLOSED",
            WorkOrder.actual_ship_date.isnot(None),
            WorkOrder.actual_ship_date >= period_start,
            WorkOrder.actual_ship_date <= period_end
        ).scalar()

        if not total_completed or total_completed == 0:
            return None

        on_time = self.db.query(func.count(WorkOrder.work_order_id)).filter(
            WorkOrder.client_id == client_id,
            WorkOrder.status == "CLOSED",
            WorkOrder.actual_ship_date.isnot(None),
            WorkOrder.actual_ship_date >= period_start,
            WorkOrder.actual_ship_date <= period_end,
            WorkOrder.actual_ship_date <= WorkOrder.required_date
        ).scalar()

        return (Decimal(str(on_time or 0)) / Decimal(str(total_completed))) * 100

    def _get_utilization_actual(
        self,
        client_id: str,
        period_start: date,
        period_end: date
    ) -> Optional[Decimal]:
        """
        Get capacity utilization from production entries.

        Utilization = run_time_hours / (run_time_hours + downtime_hours + setup_time_hours) * 100
        """
        result = self.db.query(
            func.sum(ProductionEntry.run_time_hours).label('run_time'),
            func.sum(ProductionEntry.downtime_hours).label('downtime'),
            func.sum(ProductionEntry.setup_time_hours).label('setup_time')
        ).filter(
            ProductionEntry.client_id == client_id,
            ProductionEntry.production_date >= period_start,
            ProductionEntry.production_date <= period_end
        ).first()

        if result and result.run_time:
            run_time = Decimal(str(result.run_time or 0))
            downtime = Decimal(str(result.downtime or 0))
            setup_time = Decimal(str(result.setup_time or 0))
            total_time = run_time + downtime + setup_time

            if total_time > 0:
                return (run_time / total_time) * 100

        return None
