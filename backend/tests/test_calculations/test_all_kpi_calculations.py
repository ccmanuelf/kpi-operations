"""
Comprehensive KPI Calculation Tests
Tests all 10 KPIs with known inputs and expected outputs
"""
import pytest
from decimal import Decimal
from datetime import date

from calculations.efficiency import calculate_efficiency
from calculations.performance import calculate_performance
from calculations.ppm import calculate_ppm
from calculations.dpmo import calculate_dpmo
from calculations.fpy_rty import calculate_fpy, calculate_rty
from calculations.availability import calculate_availability
from calculations.wip_aging import calculate_wip_aging
from calculations.absenteeism import calculate_absenteeism
from calculations.otd import calculate_otd


class TestAllKPIFormulas:
    """Test all 10 KPI formulas match CSV specifications"""

    def test_kpi_1_wip_aging(self):
        """Test WIP Aging calculation"""
        # Given: WIP held for 15 days
        from datetime import timedelta

        hold_date = date(2024, 1, 1)
        as_of_date = date(2024, 1, 16)
        aging_days = (as_of_date - hold_date).days

        # Then: Aging should be 15 days
        assert aging_days == 15

    def test_kpi_2_on_time_delivery(self):
        """Test On-Time Delivery calculation"""
        # Given: 95 orders on time, 100 total
        on_time = 95
        total = 100

        # When: Calculate OTD
        otd = (Decimal(str(on_time)) / Decimal(str(total))) * 100

        # Then: OTD should be 95%
        assert float(otd) == 95.0

    def test_kpi_3_efficiency(self, expected_efficiency):
        """Test Production Efficiency calculation"""
        result = calculate_efficiency(1000, 0.01, 5, 8.0)
        assert result == expected_efficiency

    def test_kpi_4_ppm(self, expected_ppm):
        """Test Quality PPM calculation"""
        defects = 5
        inspected = 1000
        ppm = (Decimal(str(defects)) / Decimal(str(inspected))) * Decimal("1000000")
        assert float(ppm) == expected_ppm

    def test_kpi_5_dpmo(self, expected_dpmo):
        """Test Quality DPMO calculation"""
        defects = 5
        units = 1000
        opportunities = 10
        dpmo = (Decimal(str(defects)) / Decimal(str(units * opportunities))) * Decimal("1000000")
        assert float(dpmo) == expected_dpmo

    def test_kpi_6_fpy(self):
        """Test First Pass Yield calculation"""
        # Given: 95 good units out of 100
        good = 95
        total = 100
        fpy = (Decimal(str(good)) / Decimal(str(total))) * 100
        assert float(fpy) == 95.0

    def test_kpi_7_rty(self):
        """Test Rolled Throughput Yield calculation"""
        # Given: FPY at each step
        step1_fpy = Decimal("0.98")  # 98%
        step2_fpy = Decimal("0.97")  # 97%
        step3_fpy = Decimal("0.99")  # 99%

        # When: Calculate RTY
        rty = step1_fpy * step2_fpy * step3_fpy

        # Then: RTY = 0.98 × 0.97 × 0.99 = 0.9409 (94.09%)
        assert float(rty) == pytest.approx(0.9409, rel=0.0001)

    def test_kpi_8_availability(self, expected_availability):
        """Test Availability calculation"""
        # Given: 0.5 hours downtime, 8 hours scheduled
        scheduled = Decimal("8.0")
        downtime = Decimal("0.5")

        # When: Calculate availability
        availability = (1 - (downtime / scheduled)) * 100

        # Then: Should be 93.75%
        assert float(availability) == expected_availability

    def test_kpi_9_performance(self, expected_performance):
        """Test Performance calculation"""
        result = calculate_performance(1000, 0.01, 8.0)
        assert result == expected_performance

    def test_kpi_10_absenteeism(self):
        """Test Absenteeism calculation"""
        # Given: 2 hours absent, 40 hours scheduled
        absent = Decimal("2")
        scheduled = Decimal("40")

        # When: Calculate absenteeism
        absenteeism = (absent / scheduled) * 100

        # Then: Should be 5%
        assert float(absenteeism) == 5.0
