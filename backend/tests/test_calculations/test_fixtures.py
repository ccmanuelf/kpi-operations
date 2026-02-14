"""
Additional Test Fixtures
Shared fixtures for all test modules
"""

import pytest
from datetime import date, timedelta


@pytest.fixture
def sample_date_range():
    """Sample date range for testing"""
    start = date(2024, 1, 1)
    end = date(2024, 1, 31)
    return (start, end)


@pytest.fixture
def sample_kpi_targets():
    """Industry standard KPI targets"""
    return {
        "efficiency": 85.0,  # 85% target
        "performance": 95.0,  # 95% target
        "availability": 90.0,  # 90% target
        "otd": 95.0,  # 95% on-time delivery
        "ppm": 5000.0,  # 5000 PPM target
        "fpy": 95.0,  # 95% first pass yield
        "absenteeism": 5.0,  # 5% or less
    }
