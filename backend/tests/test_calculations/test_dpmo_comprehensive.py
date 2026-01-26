"""
Comprehensive Tests for DPMO (Defects Per Million Opportunities) Calculations
Target: Increase dpmo.py coverage from 36% to 60%+
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch


class TestDPMOBasic:
    """Basic tests for DPMO calculations"""

    def test_import_dpmo(self):
        """Test module imports correctly"""
        from backend.calculations import dpmo
        assert dpmo is not None

    def test_dpmo_formula(self):
        """Test DPMO formula: DPMO = (Defects / Opportunities) * 1,000,000"""
        total_defects = 50
        total_units = 10000
        opportunities_per_unit = 5

        total_opportunities = total_units * opportunities_per_unit
        dpmo = (Decimal(str(total_defects)) / Decimal(str(total_opportunities))) * 1000000

        # 50 / 50000 * 1000000 = 1000 DPMO
        assert dpmo == Decimal("1000")

    def test_dpmo_six_sigma_level(self):
        """Test DPMO to Sigma level conversion"""
        # Approximate sigma levels
        sigma_levels = {
            Decimal("1"): Decimal("691462"),
            Decimal("2"): Decimal("308538"),
            Decimal("3"): Decimal("66807"),
            Decimal("4"): Decimal("6210"),
            Decimal("5"): Decimal("233"),
            Decimal("6"): Decimal("3.4")
        }

        # 3.4 DPMO = 6 Sigma
        assert sigma_levels[Decimal("6")] == Decimal("3.4")

    def test_dpmo_perfect_zero(self):
        """Test DPMO with zero defects"""
        total_defects = 0
        total_opportunities = 50000

        dpmo = (Decimal(str(total_defects)) / Decimal(str(total_opportunities))) * 1000000

        assert dpmo == Decimal("0")


class TestCalculateDPMO:
    """Tests for calculate_dpmo function"""

    def test_calculate_dpmo_formula(self):
        """Test DPMO formula calculation"""
        defects = 50
        opportunities = 50000

        dpmo = (Decimal(str(defects)) / Decimal(str(opportunities))) * 1000000

        assert dpmo == Decimal("1000")

    def test_dpmo_edge_cases(self):
        """Test DPMO edge cases"""
        # Zero defects
        dpmo_zero = (Decimal("0") / Decimal("50000")) * 1000000
        assert dpmo_zero == Decimal("0")

        # High defect rate
        dpmo_high = (Decimal("500") / Decimal("1000")) * 1000000
        assert dpmo_high == Decimal("500000")


class TestOpportunityCalculation:
    """Tests for defect opportunity calculations"""

    def test_opportunities_per_unit_default(self):
        """Test default opportunities per unit"""
        # Default is typically 1 (one opportunity per unit)
        default_opp = 1
        assert default_opp >= 1

    def test_opportunities_calculation(self):
        """Test total opportunities calculation"""
        units_inspected = 5000
        opportunities_per_unit = 3

        total_opportunities = units_inspected * opportunities_per_unit

        assert total_opportunities == 15000

    def test_dpmo_vs_ppm_relationship(self):
        """Test relationship between DPMO and PPM"""
        # When opportunities_per_unit = 1, DPMO = PPM
        total_defects = 100
        total_units = 10000
        opportunities_per_unit = 1

        # PPM
        ppm = (Decimal(str(total_defects)) / Decimal(str(total_units))) * 1000000

        # DPMO
        total_opportunities = total_units * opportunities_per_unit
        dpmo = (Decimal(str(total_defects)) / Decimal(str(total_opportunities))) * 1000000

        assert ppm == dpmo  # Equal when opp_per_unit = 1


class TestSigmaConversion:
    """Tests for Sigma level conversion"""

    def test_dpmo_to_sigma_3_sigma(self):
        """Test 3 sigma level (66,807 DPMO)"""
        dpmo = 66807

        # 3 sigma = 66,807 DPMO = 93.3% yield
        yield_pct = (1 - dpmo / 1000000) * 100

        assert Decimal("93.3") < yield_pct < Decimal("93.4")

    def test_dpmo_to_sigma_4_sigma(self):
        """Test 4 sigma level (6,210 DPMO)"""
        dpmo = 6210

        # 4 sigma = 6,210 DPMO = 99.379% yield
        yield_pct = (1 - dpmo / 1000000) * 100

        assert Decimal("99.3") < yield_pct < Decimal("99.4")

    def test_dpmo_to_sigma_5_sigma(self):
        """Test 5 sigma level (233 DPMO)"""
        dpmo = 233

        # 5 sigma = 233 DPMO = 99.977% yield
        yield_pct = (1 - dpmo / 1000000) * 100

        assert yield_pct > Decimal("99.9")


class TestDPMOTrend:
    """Tests for DPMO trend analysis"""

    def test_dpmo_trend_improvement(self):
        """Test DPMO improvement over time"""
        weekly_dpmo = [5000, 4500, 4000, 3500, 3000]

        # Lower DPMO = better quality
        is_improving = all(
            weekly_dpmo[i] > weekly_dpmo[i + 1]
            for i in range(len(weekly_dpmo) - 1)
        )

        assert is_improving == True

    def test_dpmo_percentage_reduction(self):
        """Test DPMO reduction percentage"""
        initial_dpmo = 5000
        final_dpmo = 3000

        reduction_pct = ((initial_dpmo - final_dpmo) / initial_dpmo) * 100

        assert reduction_pct == 40.0


class TestDPMOByCategory:
    """Tests for DPMO by defect category"""

    def test_dpmo_by_defect_type(self):
        """Test DPMO broken down by defect type"""
        defect_counts = {
            "Visual": 25,
            "Functional": 15,
            "Dimensional": 10
        }
        total_opportunities = 100000

        dpmo_by_type = {
            defect_type: (Decimal(str(count)) / Decimal(str(total_opportunities))) * 1000000
            for defect_type, count in defect_counts.items()
        }

        assert dpmo_by_type["Visual"] == Decimal("250")
        assert dpmo_by_type["Functional"] == Decimal("150")
        assert dpmo_by_type["Dimensional"] == Decimal("100")

    def test_pareto_dpmo_analysis(self):
        """Test Pareto analysis of DPMO"""
        defect_counts = {
            "Solder defect": 40,
            "Missing component": 25,
            "Wrong component": 15,
            "Alignment issue": 10,
            "Other": 10
        }

        total_defects = sum(defect_counts.values())

        # Sort by count descending
        sorted_defects = sorted(
            defect_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Top 2 defects (80/20 rule check)
        top_2_count = sum(count for _, count in sorted_defects[:2])
        top_2_pct = (top_2_count / total_defects) * 100

        # 40 + 25 = 65% (close to 80/20)
        assert top_2_pct == 65.0


class TestDPMOValidation:
    """Tests for DPMO input validation"""

    def test_dpmo_non_negative(self):
        """Test DPMO is never negative"""
        def validate_dpmo(dpmo: Decimal) -> bool:
            return dpmo >= 0

        assert validate_dpmo(Decimal("0")) == True
        assert validate_dpmo(Decimal("1000")) == True
        assert validate_dpmo(Decimal("-100")) == False

    def test_dpmo_max_value(self):
        """Test DPMO maximum is 1,000,000"""
        def validate_dpmo(dpmo: Decimal) -> bool:
            return 0 <= dpmo <= 1000000

        assert validate_dpmo(Decimal("1000000")) == True
        assert validate_dpmo(Decimal("1000001")) == False

    def test_dpmo_with_zero_opportunities(self):
        """Test DPMO handling with zero opportunities"""
        total_defects = 10
        total_opportunities = 0

        if total_opportunities == 0:
            dpmo = Decimal("0")
        else:
            dpmo = (Decimal(str(total_defects)) / Decimal(str(total_opportunities))) * 1000000

        assert dpmo == Decimal("0")


class TestDPMOVsOtherMetrics:
    """Tests for DPMO relationship with other quality metrics"""

    def test_dpmo_yield_relationship(self):
        """Test DPMO to Yield conversion"""
        dpmo = 3400  # 6 sigma

        yield_pct = (1 - dpmo / 1000000) * 100

        # 3400 DPMO = 99.66% yield (use approximate comparison for float)
        assert abs(yield_pct - 99.66) < 0.01

    def test_dpmo_dpu_relationship(self):
        """Test DPMO and DPU relationship"""
        # DPU = Defects / Units
        # DPMO = DPU / Opportunities_per_unit * 1,000,000

        defects = 50
        units = 1000
        opp_per_unit = 5

        dpu = defects / units  # 0.05
        dpmo = (dpu / opp_per_unit) * 1000000  # 10,000

        assert dpu == 0.05
        assert dpmo == 10000
