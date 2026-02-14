"""
Analytics Service
Orchestrates trend analysis and prediction calculations.

Phase 1.1: Service Orchestration Layer
Decouples routes from analytics calculations.
"""

from decimal import Decimal
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from backend.schemas.production_entry import ProductionEntry
from backend.schemas.quality_entry import QualityEntry
from backend.schemas.work_order import WorkOrder


@dataclass
class TrendPoint:
    """Single point in a trend line."""

    date: date
    value: float
    period_type: str = "daily"


@dataclass
class TrendAnalysis:
    """Result of trend analysis."""

    metric_name: str
    trend_direction: str  # "improving", "declining", "stable"
    trend_percentage: float
    data_points: List[TrendPoint]
    start_value: float
    end_value: float
    interpretation: str


@dataclass
class Prediction:
    """Result of a prediction."""

    metric_name: str
    predicted_value: float
    confidence_interval: Dict[str, float]
    prediction_date: date
    model_used: str
    factors_considered: List[str]


class AnalyticsService:
    """
    Service layer for analytics and predictions.

    Coordinates data aggregation and delegates to calculation functions.
    """

    def __init__(self, db: Session):
        """
        Initialize service with database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def analyze_efficiency_trend(
        self, start_date: date, end_date: date, client_id: Optional[str] = None, granularity: str = "daily"
    ) -> TrendAnalysis:
        """
        Analyze efficiency trend over a date range.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            client_id: Optional client filter
            granularity: "daily", "weekly", or "monthly"

        Returns:
            TrendAnalysis with direction and data points
        """
        from backend.calculations.trend_analysis import calculate_trend_direction, get_trend_interpretation

        # Fetch aggregated data
        data_points = self._fetch_efficiency_trend_data(start_date, end_date, client_id, granularity)

        if len(data_points) < 2:
            return TrendAnalysis(
                metric_name="efficiency",
                trend_direction="insufficient_data",
                trend_percentage=0.0,
                data_points=data_points,
                start_value=data_points[0].value if data_points else 0.0,
                end_value=data_points[-1].value if data_points else 0.0,
                interpretation="Insufficient data for trend analysis",
            )

        # Calculate trend
        values = [dp.value for dp in data_points]
        direction, percentage = calculate_trend_direction(values)
        interpretation = get_trend_interpretation("efficiency", direction, percentage)

        return TrendAnalysis(
            metric_name="efficiency",
            trend_direction=direction,
            trend_percentage=percentage,
            data_points=data_points,
            start_value=values[0],
            end_value=values[-1],
            interpretation=interpretation,
        )

    def analyze_quality_trend(
        self,
        start_date: date,
        end_date: date,
        metric: str = "ppm",
        client_id: Optional[str] = None,
        granularity: str = "daily",
    ) -> TrendAnalysis:
        """
        Analyze quality metric trend over a date range.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            metric: Quality metric to analyze ("ppm", "dpmo", "fpy", "rty")
            client_id: Optional client filter
            granularity: "daily", "weekly", or "monthly"

        Returns:
            TrendAnalysis with direction and data points
        """
        from backend.calculations.trend_analysis import calculate_trend_direction, get_trend_interpretation

        # Fetch aggregated data
        data_points = self._fetch_quality_trend_data(start_date, end_date, metric, client_id, granularity)

        if len(data_points) < 2:
            return TrendAnalysis(
                metric_name=metric,
                trend_direction="insufficient_data",
                trend_percentage=0.0,
                data_points=data_points,
                start_value=data_points[0].value if data_points else 0.0,
                end_value=data_points[-1].value if data_points else 0.0,
                interpretation="Insufficient data for trend analysis",
            )

        values = [dp.value for dp in data_points]
        direction, percentage = calculate_trend_direction(values)

        # For PPM and DPMO, lower is better (invert direction)
        if metric in ["ppm", "dpmo"]:
            if direction == "improving":
                direction = "declining"
            elif direction == "declining":
                direction = "improving"

        interpretation = get_trend_interpretation(metric, direction, percentage)

        return TrendAnalysis(
            metric_name=metric,
            trend_direction=direction,
            trend_percentage=percentage,
            data_points=data_points,
            start_value=values[0],
            end_value=values[-1],
            interpretation=interpretation,
        )

    def predict_efficiency(
        self, prediction_date: date, client_id: Optional[str] = None, lookback_days: int = 30
    ) -> Prediction:
        """
        Predict efficiency for a future date.

        Args:
            prediction_date: Date to predict for
            client_id: Optional client filter
            lookback_days: Number of historical days to use

        Returns:
            Prediction with confidence interval
        """
        from backend.calculations.predictions import predict_metric_value, calculate_confidence_interval

        # Get historical data
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)

        data_points = self._fetch_efficiency_trend_data(start_date, end_date, client_id, "daily")

        if len(data_points) < 7:
            return Prediction(
                metric_name="efficiency",
                predicted_value=0.0,
                confidence_interval={"lower": 0.0, "upper": 0.0},
                prediction_date=prediction_date,
                model_used="insufficient_data",
                factors_considered=[],
            )

        values = [dp.value for dp in data_points]
        dates = [dp.date for dp in data_points]

        # Calculate prediction
        days_ahead = (prediction_date - end_date).days
        predicted, model_type = predict_metric_value(values, dates, days_ahead)
        confidence = calculate_confidence_interval(values, predicted)

        return Prediction(
            metric_name="efficiency",
            predicted_value=predicted,
            confidence_interval=confidence,
            prediction_date=prediction_date,
            model_used=model_type,
            factors_considered=["historical_trend", "seasonality"],
        )

    def get_operations_health_dashboard(
        self, as_of_date: Optional[date] = None, client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive operations health dashboard data.

        Aggregates multiple metrics for dashboard display.
        Uses caching to improve performance for repeated requests.
        """
        from backend.cache import get_cache, build_cache_key

        if as_of_date is None:
            as_of_date = date.today()

        # Try to get from cache
        cache = get_cache()
        cache_key = build_cache_key("dashboard", client_id or "all", as_of_date.isoformat())

        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Calculate date ranges
        today_start = as_of_date
        week_start = as_of_date - timedelta(days=7)
        month_start = as_of_date - timedelta(days=30)

        # Get today's metrics
        today_metrics = self._get_daily_metrics(as_of_date, client_id)

        # Get trend data
        efficiency_trend = self.analyze_efficiency_trend(month_start, as_of_date, client_id, "daily")
        quality_trend = self.analyze_quality_trend(month_start, as_of_date, "ppm", client_id, "daily")

        # Get work order status summary
        wo_summary = self._get_work_order_summary(client_id)

        result = {
            "as_of": as_of_date.isoformat(),
            "today": today_metrics,
            "trends": {
                "efficiency": {
                    "direction": efficiency_trend.trend_direction,
                    "percentage": efficiency_trend.trend_percentage,
                    "interpretation": efficiency_trend.interpretation,
                },
                "quality": {
                    "direction": quality_trend.trend_direction,
                    "percentage": quality_trend.trend_percentage,
                    "interpretation": quality_trend.interpretation,
                },
            },
            "work_orders": wo_summary,
            "alerts": self._get_active_alerts(client_id),
        }

        # Cache for 5 minutes (dashboard data changes slowly)
        cache.set(cache_key, result, ttl_seconds=300)

        return result

    def compare_periods(
        self,
        period1_start: date,
        period1_end: date,
        period2_start: date,
        period2_end: date,
        metrics: List[str],
        client_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compare metrics between two time periods.

        Useful for period-over-period analysis.
        """
        results = {
            "period1": {"start": period1_start.isoformat(), "end": period1_end.isoformat(), "metrics": {}},
            "period2": {"start": period2_start.isoformat(), "end": period2_end.isoformat(), "metrics": {}},
            "comparison": {},
        }

        for metric in metrics:
            p1_value = self._get_metric_average(metric, period1_start, period1_end, client_id)
            p2_value = self._get_metric_average(metric, period2_start, period2_end, client_id)

            results["period1"]["metrics"][metric] = p1_value
            results["period2"]["metrics"][metric] = p2_value

            if p1_value > 0:
                change_pct = ((p2_value - p1_value) / p1_value) * 100
            else:
                change_pct = 0.0

            results["comparison"][metric] = {
                "change_absolute": p2_value - p1_value,
                "change_percentage": change_pct,
                "direction": "improving" if change_pct > 0 else "declining" if change_pct < 0 else "stable",
            }

        return results

    # ========================================================================
    # Private data fetching methods
    # ========================================================================

    def _fetch_efficiency_trend_data(
        self, start_date: date, end_date: date, client_id: Optional[str], granularity: str
    ) -> List[TrendPoint]:
        """Fetch efficiency data points for trend analysis."""
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        if granularity == "daily":
            date_trunc = func.date(ProductionEntry.production_date)
        elif granularity == "weekly":
            # SQLite doesn't have strftime week, use date
            date_trunc = func.date(ProductionEntry.production_date)
        else:  # monthly
            date_trunc = func.date(ProductionEntry.production_date)

        query = (
            self.db.query(
                date_trunc.label("period"), func.avg(ProductionEntry.efficiency_percentage).label("avg_value")
            )
            .filter(
                and_(
                    ProductionEntry.production_date >= start_datetime,
                    ProductionEntry.production_date <= end_datetime,
                    ProductionEntry.efficiency_percentage.isnot(None),
                )
            )
            .group_by(date_trunc)
            .order_by(date_trunc)
        )

        if client_id:
            query = query.filter(ProductionEntry.client_id == client_id)

        results = query.all()

        return [
            TrendPoint(
                date=(
                    result.period
                    if isinstance(result.period, date)
                    else datetime.strptime(str(result.period), "%Y-%m-%d").date()
                ),
                value=float(result.avg_value or 0),
                period_type=granularity,
            )
            for result in results
        ]

    def _fetch_quality_trend_data(
        self, start_date: date, end_date: date, metric: str, client_id: Optional[str], granularity: str
    ) -> List[TrendPoint]:
        """Fetch quality data points for trend analysis."""
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        date_trunc = func.date(QualityEntry.shift_date)

        # Select appropriate metric
        if metric == "ppm":
            metric_expr = (
                func.sum(QualityEntry.units_defective)
                * 1000000.0
                / func.nullif(func.sum(QualityEntry.units_inspected), 0)
            )
        elif metric == "dpmo":
            metric_expr = (
                func.sum(QualityEntry.total_defects_count)
                * 1000000.0
                / func.nullif(func.sum(QualityEntry.units_inspected) * 10, 0)  # Assume 10 opps
            )
        elif metric == "fpy":
            metric_expr = (
                func.sum(QualityEntry.units_passed) * 100.0 / func.nullif(func.sum(QualityEntry.units_inspected), 0)
            )
        else:
            # Default to inspection pass rate
            metric_expr = (
                func.sum(QualityEntry.units_passed) * 100.0 / func.nullif(func.sum(QualityEntry.units_inspected), 0)
            )

        query = (
            self.db.query(date_trunc.label("period"), metric_expr.label("metric_value"))
            .filter(and_(QualityEntry.shift_date >= start_datetime, QualityEntry.shift_date <= end_datetime))
            .group_by(date_trunc)
            .order_by(date_trunc)
        )

        if client_id:
            query = query.filter(QualityEntry.client_id == client_id)

        results = query.all()

        return [
            TrendPoint(
                date=(
                    result.period
                    if isinstance(result.period, date)
                    else datetime.strptime(str(result.period), "%Y-%m-%d").date()
                ),
                value=float(result.metric_value or 0),
                period_type=granularity,
            )
            for result in results
        ]

    def _get_daily_metrics(self, target_date: date, client_id: Optional[str]) -> Dict[str, Any]:
        """Get metrics for a single day."""
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())

        # Production metrics
        prod_query = self.db.query(
            func.sum(ProductionEntry.units_produced).label("total_units"),
            func.avg(ProductionEntry.efficiency_percentage).label("avg_efficiency"),
            func.avg(ProductionEntry.performance_percentage).label("avg_performance"),
        ).filter(
            and_(ProductionEntry.production_date >= start_datetime, ProductionEntry.production_date <= end_datetime)
        )

        if client_id:
            prod_query = prod_query.filter(ProductionEntry.client_id == client_id)

        prod_result = prod_query.first()

        # Quality metrics
        qual_query = self.db.query(
            func.sum(QualityEntry.units_inspected).label("total_inspected"),
            func.sum(QualityEntry.units_defective).label("total_defects"),
        ).filter(and_(QualityEntry.shift_date >= start_datetime, QualityEntry.shift_date <= end_datetime))

        if client_id:
            qual_query = qual_query.filter(QualityEntry.client_id == client_id)

        qual_result = qual_query.first()

        total_inspected = qual_result.total_inspected or 0
        total_defects = qual_result.total_defects or 0

        if total_inspected > 0:
            ppm = (total_defects / total_inspected) * 1000000
        else:
            ppm = 0

        return {
            "total_units_produced": prod_result.total_units or 0,
            "avg_efficiency": float(prod_result.avg_efficiency or 0),
            "avg_performance": float(prod_result.avg_performance or 0),
            "total_inspected": total_inspected,
            "total_defects": total_defects,
            "ppm": ppm,
        }

    def _get_work_order_summary(self, client_id: Optional[str]) -> Dict[str, int]:
        """Get work order status counts."""
        query = self.db.query(WorkOrder.status, func.count(WorkOrder.work_order_id).label("count")).group_by(
            WorkOrder.status
        )

        if client_id:
            query = query.filter(WorkOrder.client_id == client_id)

        results = query.all()

        summary = {r.status: r.count for r in results}
        summary["total"] = sum(summary.values())

        return summary

    def _get_active_alerts(self, client_id: Optional[str]) -> List[Dict[str, Any]]:
        """Get active alerts (placeholder for alerts system)."""
        # This would integrate with the alerts system
        # For now, return empty list
        return []

    def _get_metric_average(self, metric: str, start_date: date, end_date: date, client_id: Optional[str]) -> float:
        """Get average value for a metric over a period."""
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        if metric == "efficiency":
            query = self.db.query(func.avg(ProductionEntry.efficiency_percentage)).filter(
                and_(ProductionEntry.production_date >= start_datetime, ProductionEntry.production_date <= end_datetime)
            )
            if client_id:
                query = query.filter(ProductionEntry.client_id == client_id)
        elif metric == "performance":
            query = self.db.query(func.avg(ProductionEntry.performance_percentage)).filter(
                and_(ProductionEntry.production_date >= start_datetime, ProductionEntry.production_date <= end_datetime)
            )
            if client_id:
                query = query.filter(ProductionEntry.client_id == client_id)
        elif metric == "ppm":
            query = self.db.query(
                func.sum(QualityEntry.units_defective)
                * 1000000.0
                / func.nullif(func.sum(QualityEntry.units_inspected), 0)
            ).filter(and_(QualityEntry.shift_date >= start_datetime, QualityEntry.shift_date <= end_datetime))
            if client_id:
                query = query.filter(QualityEntry.client_id == client_id)
        else:
            return 0.0

        result = query.scalar()
        return float(result or 0)
