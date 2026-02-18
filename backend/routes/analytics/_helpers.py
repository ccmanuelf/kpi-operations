"""
Analytics - Shared Helper Functions

Utility functions shared across analytics sub-modules.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional, Tuple

from backend.utils.logging_utils import get_module_logger

logger = get_module_logger(__name__)


def parse_time_range(time_range: str, end_date: Optional[date] = None) -> Tuple[date, date]:
    """
    Parse time range string to start and end dates

    Args:
        time_range: Time range ('7d', '30d', '90d')
        end_date: Optional end date (defaults to today)

    Returns:
        Tuple of (start_date, end_date)
    """
    if end_date is None:
        end_date = date.today()

    if time_range == "7d":
        start_date = end_date - timedelta(days=7)
    elif time_range == "30d":
        start_date = end_date - timedelta(days=30)
    elif time_range == "90d":
        start_date = end_date - timedelta(days=90)
    else:
        raise ValueError(f"Invalid time range: {time_range}")

    return start_date, end_date


def get_performance_rating(value: Decimal, benchmark: Decimal) -> str:
    """
    Determine performance rating based on value and benchmark

    Args:
        value: KPI value
        benchmark: Benchmark value

    Returns:
        Performance rating string
    """
    ratio = float(value / benchmark) if benchmark > 0 else 0

    if ratio >= 1.1:
        return "Excellent"
    elif ratio >= 0.95:
        return "Good"
    elif ratio >= 0.85:
        return "Fair"
    else:
        return "Poor"


def get_heatmap_color_code(
    value: Optional[Decimal], benchmark: Decimal = Decimal("85.0")
) -> Tuple[str, str]:
    """
    Get performance level and color code for heatmap cell

    Args:
        value: KPI value (None if no data)
        benchmark: Benchmark for comparison

    Returns:
        Tuple of (performance_level, color_code)
    """
    if value is None:
        return ("No Data", "#94a3b8")

    if value >= benchmark * Decimal("1.1"):
        return ("Excellent", "#22c55e")
    elif value >= benchmark:
        return ("Good", "#84cc16")
    elif value >= benchmark * Decimal("0.9"):
        return ("Fair", "#eab308")
    else:
        return ("Poor", "#ef4444")
