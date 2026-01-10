"""
Phase 5 Sample Data Generator
Generates realistic demo data for predictive analytics demonstration

This module provides:
- Historical KPI data generation with realistic patterns
- Trend simulation (upward, downward, stable, volatile)
- Weekly seasonality and random noise
- Demo data seeding for all 10 KPIs

KPI Types Supported:
1. Efficiency - Production efficiency percentage
2. Performance - Production performance percentage
3. Availability - Equipment availability percentage
4. OEE - Overall Equipment Effectiveness
5. PPM - Parts Per Million defects
6. DPMO - Defects Per Million Opportunities
7. FPY - First Pass Yield percentage
8. RTY - Rolled Throughput Yield percentage
9. Absenteeism - Absenteeism rate percentage
10. OTD - On-Time Delivery percentage
"""
from typing import List, Dict, Optional, Tuple
from datetime import date, timedelta
from decimal import Decimal
import random
import math
from dataclasses import dataclass
from enum import Enum


class KPITypePhase5(str, Enum):
    """All 10 KPI types for Phase 5 analytics"""
    EFFICIENCY = "efficiency"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    OEE = "oee"
    PPM = "ppm"
    DPMO = "dpmo"
    FPY = "fpy"
    RTY = "rty"
    ABSENTEEISM = "absenteeism"
    OTD = "otd"


@dataclass
class KPIConfig:
    """Configuration for KPI data generation"""
    base_value: float
    min_value: float
    max_value: float
    trend_bias: float  # Positive = improving, negative = declining
    volatility: float  # Higher = more random variation
    weekly_amplitude: float  # Strength of weekly seasonality
    is_inverse: bool  # True for KPIs where lower is better (PPM, DPMO, Absenteeism)


# KPI-specific configuration for realistic data generation
KPI_CONFIGS: Dict[str, KPIConfig] = {
    KPITypePhase5.EFFICIENCY: KPIConfig(
        base_value=82.0, min_value=65.0, max_value=98.0,
        trend_bias=0.02, volatility=2.5, weekly_amplitude=2.0, is_inverse=False
    ),
    KPITypePhase5.PERFORMANCE: KPIConfig(
        base_value=88.0, min_value=70.0, max_value=99.0,
        trend_bias=0.015, volatility=2.0, weekly_amplitude=1.5, is_inverse=False
    ),
    KPITypePhase5.AVAILABILITY: KPIConfig(
        base_value=91.0, min_value=75.0, max_value=99.5,
        trend_bias=0.01, volatility=1.8, weekly_amplitude=1.2, is_inverse=False
    ),
    KPITypePhase5.OEE: KPIConfig(
        base_value=65.0, min_value=45.0, max_value=95.0,
        trend_bias=0.025, volatility=3.0, weekly_amplitude=2.5, is_inverse=False
    ),
    KPITypePhase5.PPM: KPIConfig(
        base_value=4500.0, min_value=500.0, max_value=15000.0,
        trend_bias=-15.0, volatility=300.0, weekly_amplitude=200.0, is_inverse=True
    ),
    KPITypePhase5.DPMO: KPIConfig(
        base_value=450.0, min_value=50.0, max_value=2000.0,
        trend_bias=-2.0, volatility=40.0, weekly_amplitude=25.0, is_inverse=True
    ),
    KPITypePhase5.FPY: KPIConfig(
        base_value=96.5, min_value=85.0, max_value=99.8,
        trend_bias=0.008, volatility=0.8, weekly_amplitude=0.5, is_inverse=False
    ),
    KPITypePhase5.RTY: KPIConfig(
        base_value=92.0, min_value=80.0, max_value=99.5,
        trend_bias=0.012, volatility=1.2, weekly_amplitude=0.8, is_inverse=False
    ),
    KPITypePhase5.ABSENTEEISM: KPIConfig(
        base_value=5.2, min_value=1.0, max_value=15.0,
        trend_bias=-0.008, volatility=0.8, weekly_amplitude=0.5, is_inverse=True
    ),
    KPITypePhase5.OTD: KPIConfig(
        base_value=94.0, min_value=75.0, max_value=99.9,
        trend_bias=0.02, volatility=1.5, weekly_amplitude=1.0, is_inverse=False
    ),
}


class KPIHistoryGenerator:
    """
    Generates realistic KPI historical data with patterns suitable for
    predictive analytics demonstration
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize generator with optional random seed for reproducibility

        Args:
            seed: Random seed for reproducible data generation
        """
        if seed is not None:
            random.seed(seed)
        self.seed = seed

    def generate_single_kpi(
        self,
        kpi_type: str,
        days: int = 90,
        end_date: Optional[date] = None,
        client_id: Optional[str] = None,
        trend_override: Optional[str] = None
    ) -> List[Dict]:
        """
        Generate historical KPI data with realistic patterns

        Args:
            kpi_type: Type of KPI to generate
            days: Number of historical days (default 90)
            end_date: End date for data (default: today)
            client_id: Optional client ID for the data
            trend_override: Override trend ('improving', 'declining', 'stable', 'volatile')

        Returns:
            List of dictionaries with date, value, and metadata

        Example:
            >>> generator = KPIHistoryGenerator(seed=42)
            >>> history = generator.generate_single_kpi('efficiency', days=30)
            >>> print(history[0])
            {'date': date(2024, 1, 1), 'value': 82.5, 'kpi_type': 'efficiency', ...}
        """
        if end_date is None:
            end_date = date.today()

        # Get KPI configuration
        config = KPI_CONFIGS.get(kpi_type)
        if config is None:
            raise ValueError(f"Unknown KPI type: {kpi_type}")

        # Determine trend
        if trend_override:
            trend = self._get_trend_modifier(trend_override, config)
        else:
            trend = config.trend_bias

        data = []
        current_value = config.base_value

        for i in range(days):
            day_date = end_date - timedelta(days=days - 1 - i)

            # Calculate components
            # 1. Trend component (linear progression)
            trend_effect = trend * i

            # 2. Weekly seasonality (sine wave with 7-day period)
            day_of_week = day_date.weekday()
            weekly_effect = config.weekly_amplitude * math.sin(2 * math.pi * day_of_week / 7)

            # 3. Random noise (Gaussian)
            noise = random.gauss(0, config.volatility)

            # 4. Occasional anomalies (5% chance)
            anomaly = 0
            is_anomaly = False
            if random.random() < 0.05:
                anomaly_direction = 1 if random.random() > 0.5 else -1
                if config.is_inverse:
                    anomaly_direction *= -1
                anomaly = anomaly_direction * config.volatility * 2.5
                is_anomaly = True

            # Combine all components
            value = config.base_value + trend_effect + weekly_effect + noise + anomaly

            # Apply bounds
            value = max(config.min_value, min(config.max_value, value))

            # Round appropriately
            if kpi_type in [KPITypePhase5.PPM, KPITypePhase5.DPMO]:
                value = round(value, 0)
            else:
                value = round(value, 2)

            data.append({
                "date": day_date,
                "value": value,
                "kpi_type": kpi_type,
                "client_id": client_id,
                "is_anomaly": is_anomaly,
                "day_of_week": day_date.strftime("%A"),
                "week_number": day_date.isocalendar()[1]
            })

        return data

    def _get_trend_modifier(self, trend_type: str, config: KPIConfig) -> float:
        """Get trend modifier based on trend type"""
        base_trend = abs(config.trend_bias) if config.trend_bias != 0 else 0.01

        if trend_type == "improving":
            return base_trend if not config.is_inverse else -base_trend
        elif trend_type == "declining":
            return -base_trend if not config.is_inverse else base_trend
        elif trend_type == "stable":
            return 0.0
        elif trend_type == "volatile":
            # Random direction with doubled magnitude
            return random.choice([-1, 1]) * base_trend * 2
        else:
            return config.trend_bias


def generate_kpi_history(
    kpi_type: str,
    days: int = 90,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    seed: Optional[int] = None
) -> List[Dict]:
    """
    Convenience function to generate historical KPI data with realistic patterns

    Args:
        kpi_type: Type of KPI to generate (efficiency, performance, etc.)
        days: Number of historical days (default 90)
        end_date: End date for data (default: today)
        client_id: Optional client ID for the data
        seed: Random seed for reproducibility

    Returns:
        List of dictionaries with date, value, and metadata

    Example:
        >>> history = generate_kpi_history('efficiency', days=30)
        >>> len(history)
        30
    """
    generator = KPIHistoryGenerator(seed=seed)
    return generator.generate_single_kpi(
        kpi_type=kpi_type,
        days=days,
        end_date=end_date,
        client_id=client_id
    )


def generate_all_kpi_histories(
    days: int = 90,
    end_date: Optional[date] = None,
    client_id: Optional[str] = None,
    seed: Optional[int] = None
) -> Dict[str, List[Dict]]:
    """
    Generate historical data for all 10 KPIs

    Args:
        days: Number of historical days
        end_date: End date for data
        client_id: Optional client ID
        seed: Random seed for reproducibility

    Returns:
        Dictionary mapping KPI type to list of historical data points

    Example:
        >>> all_data = generate_all_kpi_histories(days=30)
        >>> list(all_data.keys())
        ['efficiency', 'performance', 'availability', ...]
    """
    generator = KPIHistoryGenerator(seed=seed)
    all_data = {}

    for kpi_type in KPITypePhase5:
        all_data[kpi_type.value] = generator.generate_single_kpi(
            kpi_type=kpi_type.value,
            days=days,
            end_date=end_date,
            client_id=client_id
        )

    return all_data


def seed_demo_predictions(db, client_ids: Optional[List[str]] = None, days: int = 90):
    """
    Seed database with demo KPI history data for prediction demonstration

    This function populates the kpi_history table with realistic historical
    data that can be used for forecasting demonstrations.

    Args:
        db: SQLAlchemy database session
        client_ids: List of client IDs to seed data for (optional)
        days: Number of historical days to generate

    Returns:
        Dictionary with seeding statistics

    Example:
        >>> from backend.database import SessionLocal
        >>> db = SessionLocal()
        >>> result = seed_demo_predictions(db, client_ids=['BOOT-LINE-A'])
        >>> print(result)
        {'total_records': 900, 'clients': 1, 'kpis': 10}
    """
    from sqlalchemy import text

    # Default client IDs if not provided
    if client_ids is None:
        # Try to get existing clients from database
        result = db.execute(text("SELECT client_id FROM client WHERE is_active = 1 LIMIT 5"))
        client_ids = [row[0] for row in result.fetchall()]

        if not client_ids:
            client_ids = ['DEMO-CLIENT-001']

    generator = KPIHistoryGenerator(seed=42)  # Fixed seed for reproducibility
    total_records = 0

    for client_id in client_ids:
        for kpi_type in KPITypePhase5:
            history = generator.generate_single_kpi(
                kpi_type=kpi_type.value,
                days=days,
                client_id=client_id
            )

            for record in history:
                try:
                    db.execute(
                        text("""
                            INSERT INTO kpi_history
                            (client_id, kpi_type, record_date, value, is_anomaly, metadata)
                            VALUES (:client_id, :kpi_type, :record_date, :value, :is_anomaly, :metadata)
                            ON CONFLICT DO NOTHING
                        """),
                        {
                            'client_id': client_id,
                            'kpi_type': kpi_type.value,
                            'record_date': record['date'],
                            'value': record['value'],
                            'is_anomaly': 1 if record['is_anomaly'] else 0,
                            'metadata': f'{{"day_of_week": "{record["day_of_week"]}", "week": {record["week_number"]}}}'
                        }
                    )
                    total_records += 1
                except Exception as e:
                    # Skip duplicate records
                    pass

    db.commit()

    return {
        'total_records': total_records,
        'clients': len(client_ids),
        'kpis': len(KPITypePhase5),
        'days_per_kpi': days
    }


def get_kpi_benchmarks() -> Dict[str, Dict]:
    """
    Get industry benchmark values for all 10 KPIs

    Returns:
        Dictionary with benchmark data for each KPI type
    """
    return {
        KPITypePhase5.EFFICIENCY.value: {
            "target": 85.0,
            "excellent": 92.0,
            "good": 85.0,
            "fair": 75.0,
            "unit": "%",
            "description": "Production efficiency - actual vs. expected output"
        },
        KPITypePhase5.PERFORMANCE.value: {
            "target": 90.0,
            "excellent": 95.0,
            "good": 90.0,
            "fair": 80.0,
            "unit": "%",
            "description": "Production performance against standard cycle time"
        },
        KPITypePhase5.AVAILABILITY.value: {
            "target": 92.0,
            "excellent": 96.0,
            "good": 92.0,
            "fair": 85.0,
            "unit": "%",
            "description": "Equipment availability - uptime vs. scheduled time"
        },
        KPITypePhase5.OEE.value: {
            "target": 70.0,
            "excellent": 85.0,
            "good": 70.0,
            "fair": 55.0,
            "unit": "%",
            "description": "Overall Equipment Effectiveness (Availability x Performance x Quality)"
        },
        KPITypePhase5.PPM.value: {
            "target": 3000.0,
            "excellent": 1000.0,
            "good": 3000.0,
            "fair": 6000.0,
            "unit": "PPM",
            "description": "Parts Per Million defective"
        },
        KPITypePhase5.DPMO.value: {
            "target": 300.0,
            "excellent": 100.0,
            "good": 300.0,
            "fair": 700.0,
            "unit": "DPMO",
            "description": "Defects Per Million Opportunities"
        },
        KPITypePhase5.FPY.value: {
            "target": 97.0,
            "excellent": 99.0,
            "good": 97.0,
            "fair": 93.0,
            "unit": "%",
            "description": "First Pass Yield - passed first inspection"
        },
        KPITypePhase5.RTY.value: {
            "target": 93.0,
            "excellent": 97.0,
            "good": 93.0,
            "fair": 88.0,
            "unit": "%",
            "description": "Rolled Throughput Yield - cumulative yield"
        },
        KPITypePhase5.ABSENTEEISM.value: {
            "target": 4.0,
            "excellent": 2.0,
            "good": 4.0,
            "fair": 7.0,
            "unit": "%",
            "description": "Workforce absenteeism rate"
        },
        KPITypePhase5.OTD.value: {
            "target": 95.0,
            "excellent": 98.0,
            "good": 95.0,
            "fair": 90.0,
            "unit": "%",
            "description": "On-Time Delivery rate"
        },
    }


def calculate_kpi_health_score(
    current_value: float,
    predicted_value: float,
    kpi_type: str
) -> Dict:
    """
    Calculate health score and recommendations based on current and predicted values

    Args:
        current_value: Current KPI value
        predicted_value: Predicted future value
        kpi_type: Type of KPI

    Returns:
        Dictionary with health score, trend, and recommendations
    """
    benchmarks = get_kpi_benchmarks()
    config = KPI_CONFIGS.get(kpi_type)
    benchmark = benchmarks.get(kpi_type, {})

    if not config or not benchmark:
        return {"health_score": 50, "trend": "unknown", "recommendations": []}

    target = benchmark.get("target", config.base_value)
    excellent = benchmark.get("excellent", target * 1.1)

    # Calculate health score (0-100)
    if config.is_inverse:
        # For inverse KPIs (lower is better)
        if current_value <= excellent:
            health_score = 100
        elif current_value <= target:
            health_score = 80 + 20 * (target - current_value) / (target - excellent)
        else:
            health_score = max(0, 80 * (1 - (current_value - target) / target))
    else:
        # For regular KPIs (higher is better)
        if current_value >= excellent:
            health_score = 100
        elif current_value >= target:
            health_score = 80 + 20 * (current_value - target) / (excellent - target)
        else:
            health_score = max(0, 80 * current_value / target)

    # Determine trend
    diff = predicted_value - current_value
    if config.is_inverse:
        diff = -diff  # Reverse for inverse KPIs

    if abs(diff) < 0.5:
        trend = "stable"
    elif diff > 0:
        trend = "improving"
    else:
        trend = "declining"

    # Generate recommendations
    recommendations = []
    if health_score < 60:
        recommendations.append(f"Critical: {kpi_type} requires immediate attention")
        recommendations.append("Schedule root cause analysis meeting")
    elif health_score < 80:
        recommendations.append(f"Warning: {kpi_type} is below target")
        recommendations.append("Review recent process changes")

    if trend == "declining":
        recommendations.append("Investigate declining trend factors")

    return {
        "health_score": round(health_score, 1),
        "trend": trend,
        "current_vs_target": round(current_value - target, 2) if not config.is_inverse else round(target - current_value, 2),
        "recommendations": recommendations
    }
