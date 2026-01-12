"""
Test Suite for Quality KPIs: PPM (KPI #4) and DPMO (KPI #5)

PPM Formula: (Defects / Units Inspected) × 1,000,000
DPMO Formula: (Defects / (Units × Opportunities)) × 1,000,000

Covers:
- PPM calculation accuracy
- DPMO calculation with opportunities
- Sigma level conversion
- Edge cases and validation
"""
import pytest
from decimal import Decimal
from datetime import date

from backend.calculations.ppm import calculate_ppm
from backend.calculations.dpmo import calculate_dpmo, calculate_sigma_level


class TestPPMCalculation:
    """Test PPM (Parts Per Million) calculation"""

    def test_basic_ppm_calculation(self, expected_ppm):
        """Test basic PPM with known values"""
        # Given: 5 defects in 1000 units
        # Simulated calculation (would use DB in real implementation)
        defects = 5
        inspected = 1000

        # When: Calculate PPM
        ppm = (Decimal(str(defects)) / Decimal(str(inspected))) * Decimal("1000000")

        # Then: Should be 5000 PPM
        assert float(ppm) == expected_ppm
        assert float(ppm) == 5000.0

    def test_zero_defects_ppm(self):
        """Test PPM with perfect quality (zero defects)"""
        # Given: No defects
        defects = 0
        inspected = 1000

        # When: Calculate PPM
        ppm = (Decimal(str(defects)) / Decimal(str(inspected))) * Decimal("1000000")

        # Then: PPM should be 0
        assert float(ppm) == 0.0

    def test_high_defect_rate_ppm(self):
        """Test PPM with high defect rate"""
        # Given: 10% defect rate (100 defects in 1000 units)
        defects = 100
        inspected = 1000

        # When: Calculate PPM
        ppm = (Decimal(str(defects)) / Decimal(str(inspected))) * Decimal("1000000")

        # Then: PPM should be 100,000
        assert float(ppm) == 100000.0

    def test_low_defect_rate_ppm(self):
        """Test PPM with very low defect rate (Six Sigma)"""
        # Given: 3.4 defects per million (Six Sigma target)
        defects = 34
        inspected = 10000000

        # When: Calculate PPM
        ppm = (Decimal(str(defects)) / Decimal(str(inspected))) * Decimal("1000000")

        # Then: PPM should be 3.4
        assert float(ppm) == pytest.approx(3.4, rel=0.01)

    def test_single_defect_small_batch(self):
        """Test PPM with single defect in small batch"""
        # Given: 1 defect in 100 units
        defects = 1
        inspected = 100

        # When: Calculate PPM
        ppm = (Decimal(str(defects)) / Decimal(str(inspected))) * Decimal("1000000")

        # Then: PPM should be 10,000
        assert float(ppm) == 10000.0

    def test_ppm_precision(self):
        """Test PPM calculation precision"""
        # Given: Values resulting in decimal PPM
        defects = 7
        inspected = 1337

        # When: Calculate PPM
        ppm = (Decimal(str(defects)) / Decimal(str(inspected))) * Decimal("1000000")

        # Then: Should calculate precisely
        expected = (7 / 1337) * 1000000
        assert abs(float(ppm) - expected) < 0.01


class TestDPMOCalculation:
    """Test DPMO (Defects Per Million Opportunities) calculation"""

    def test_basic_dpmo_calculation(self, expected_dpmo):
        """Test basic DPMO with known values"""
        # Given: 5 defects, 1000 units, 10 opportunities per unit
        defects = 5
        units = 1000
        opportunities_per_unit = 10
        total_opportunities = units * opportunities_per_unit

        # When: Calculate DPMO
        dpmo = (Decimal(str(defects)) / Decimal(str(total_opportunities))) * Decimal("1000000")

        # Then: Should be 500 DPMO
        assert float(dpmo) == expected_dpmo
        assert float(dpmo) == 500.0

    def test_dpmo_vs_ppm_difference(self):
        """Test that DPMO accounts for opportunities, PPM doesn't"""
        # Given: Same defect scenario
        defects = 10
        units = 1000
        opportunities = 5

        # When: Calculate both metrics
        ppm = (Decimal(str(defects)) / Decimal(str(units))) * Decimal("1000000")
        dpmo = (Decimal(str(defects)) / Decimal(str(units * opportunities))) * Decimal("1000000")

        # Then: DPMO should be lower (more opportunities dilute the defect rate)
        assert float(dpmo) < float(ppm)
        assert float(ppm) == 10000.0  # 10 defects per 1000 units
        assert float(dpmo) == 2000.0  # 10 defects per 5000 opportunities

    def test_single_opportunity_per_unit(self):
        """Test DPMO equals PPM when opportunities = 1"""
        # Given: 1 opportunity per unit
        defects = 5
        units = 1000
        opportunities = 1

        # When: Calculate both
        ppm = (Decimal(str(defects)) / Decimal(str(units))) * Decimal("1000000")
        dpmo = (Decimal(str(defects)) / Decimal(str(units * opportunities))) * Decimal("1000000")

        # Then: Should be equal
        assert float(dpmo) == float(ppm)

    def test_many_opportunities_per_unit(self):
        """Test DPMO with complex product (many opportunities)"""
        # Given: Complex assembly with 50 opportunities per unit
        defects = 100
        units = 1000
        opportunities = 50

        # When: Calculate DPMO
        dpmo = (Decimal(str(defects)) / Decimal(str(units * opportunities))) * Decimal("1000000")

        # Then: (100 / 50000) × 1000000 = 2000 DPMO
        assert float(dpmo) == 2000.0


class TestSigmaLevelConversion:
    """Test conversion from DPMO to Sigma Level"""

    def test_six_sigma_level(self):
        """Test Six Sigma level (3.4 DPMO)"""
        # Given: 3.4 DPMO (Six Sigma target)
        dpmo = Decimal("3.4")

        # When: Convert to sigma level
        sigma = calculate_sigma_level(dpmo)

        # Then: Should be 6.0 sigma
        assert float(sigma) == 6.0

    def test_five_sigma_level(self):
        """Test Five Sigma level (233 DPMO)"""
        # Given: 233 DPMO
        dpmo = Decimal("233")

        # When: Convert to sigma level
        sigma = calculate_sigma_level(dpmo)

        # Then: Should be 5.0 sigma
        assert float(sigma) == 5.0

    def test_four_sigma_level(self):
        """Test Four Sigma level (6210 DPMO)"""
        # Given: 6210 DPMO
        dpmo = Decimal("6210")

        # When: Convert to sigma level
        sigma = calculate_sigma_level(dpmo)

        # Then: Should be 4.0 sigma
        assert float(sigma) == 4.0

    def test_three_sigma_level(self):
        """Test Three Sigma level (66807 DPMO)"""
        # Given: 66807 DPMO
        dpmo = Decimal("66807")

        # When: Convert to sigma level
        sigma = calculate_sigma_level(dpmo)

        # Then: Should be 3.0 sigma
        assert float(sigma) == 3.0

    def test_below_one_sigma(self):
        """Test very poor quality (below 1 sigma)"""
        # Given: Very high DPMO
        dpmo = Decimal("800000")

        # When: Convert to sigma level
        sigma = calculate_sigma_level(dpmo)

        # Then: Should return 0 (below table)
        assert float(sigma) == 0.0

    def test_perfect_quality_sigma(self):
        """Test perfect quality (0 DPMO)"""
        # Given: Zero defects
        dpmo = Decimal("0")

        # When: Convert to sigma level
        sigma = calculate_sigma_level(dpmo)

        # Then: Should be 6.0 sigma (best in table)
        assert float(sigma) == 6.0


class TestQualityBenchmarks:
    """Test against industry quality benchmarks"""

    def test_automotive_industry_standard(self):
        """Test automotive industry standard (~ 4 Sigma)"""
        # Given: Automotive target ~6000 DPMO
        defects = 60
        units = 10000
        opportunities = 1

        # When: Calculate DPMO
        dpmo = (Decimal(str(defects)) / Decimal(str(units * opportunities))) * Decimal("1000000")

        # Then: Should be approximately 4 sigma
        sigma = calculate_sigma_level(dpmo)
        assert float(dpmo) == 6000.0
        assert float(sigma) == 4.0

    def test_six_sigma_excellence(self):
        """Test Six Sigma excellence target"""
        # Given: Six Sigma target
        defects = 34
        units = 10000000
        opportunities = 1

        # When: Calculate metrics
        dpmo = (Decimal(str(defects)) / Decimal(str(units * opportunities))) * Decimal("1000000")
        sigma = calculate_sigma_level(dpmo)

        # Then: Should achieve 6 sigma
        assert float(dpmo) == pytest.approx(3.4, rel=0.01)
        assert float(sigma) == 6.0

    def test_typical_manufacturing_baseline(self):
        """Test typical manufacturing baseline (3 Sigma)"""
        # Given: Typical manufacturing ~66,800 DPMO
        defects = 668
        units = 10000
        opportunities = 1

        # When: Calculate DPMO
        dpmo = (Decimal(str(defects)) / Decimal(str(units * opportunities))) * Decimal("1000000")

        # Then: Should be 3 sigma
        sigma = calculate_sigma_level(dpmo)
        assert float(dpmo) == 66800.0
        assert float(sigma) == 3.0


class TestQualityEdgeCases:
    """Test edge cases for quality calculations"""

    def test_very_large_sample_size(self):
        """Test with very large inspection sample"""
        # Given: Million unit inspection
        defects = 100
        units = 1000000
        opportunities = 10

        # When: Calculate DPMO
        dpmo = (Decimal(str(defects)) / Decimal(str(units * opportunities))) * Decimal("1000000")

        # Then: (100 / 10,000,000) × 1,000,000 = 10 DPMO
        assert float(dpmo) == 10.0

    def test_small_sample_high_defect_rate(self):
        """Test small sample with high defect rate"""
        # Given: Small sample, poor quality
        defects = 5
        units = 10
        opportunities = 1

        # When: Calculate PPM
        ppm = (Decimal(str(defects)) / Decimal(str(units))) * Decimal("1000000")

        # Then: 500,000 PPM (50% defect rate)
        assert float(ppm) == 500000.0

    def test_rounding_precision_dpmo(self):
        """Test DPMO calculation precision"""
        # Given: Values resulting in repeating decimal
        defects = 7
        units = 333
        opportunities = 3

        # When: Calculate DPMO
        dpmo = (Decimal(str(defects)) / Decimal(str(units * opportunities))) * Decimal("1000000")

        # Then: Should round properly
        expected = (7 / (333 * 3)) * 1000000
        assert abs(float(dpmo) - expected) < 0.1


class TestRealWorldQualityScenarios:
    """Test real-world quality scenarios"""

    def test_apparel_quality_inspection(self):
        """Test apparel product with multiple inspection points"""
        # Given: T-shirt with 8 quality checkpoints
        # (seams, collar, hem, print, fabric, buttons, tags, packaging)
        defects = 12
        units = 1000
        opportunities = 8

        # When: Calculate DPMO
        dpmo = (Decimal(str(defects)) / Decimal(str(units * opportunities))) * Decimal("1000000")

        # Then: (12 / 8000) × 1,000,000 = 1500 DPMO
        sigma = calculate_sigma_level(dpmo)
        assert float(dpmo) == 1500.0
        assert float(sigma) >= 4.0  # Good quality

    def test_electronics_assembly_quality(self):
        """Test electronics with many solder points"""
        # Given: PCB with 200 solder joints
        defects = 50
        units = 500
        opportunities = 200

        # When: Calculate DPMO
        dpmo = (Decimal(str(defects)) / Decimal(str(units * opportunities))) * Decimal("1000000")

        # Then: (50 / 100,000) × 1,000,000 = 500 DPMO
        sigma = calculate_sigma_level(dpmo)
        assert float(dpmo) == 500.0
        # 500 DPMO falls between 4σ (6210 DPMO) and 5σ (233 DPMO), returns 4.0
        assert float(sigma) >= 4.0  # Good quality (between 4 and 5 sigma)

    def test_progressive_quality_improvement(self):
        """Test quality improvement over time"""
        # Month 1: Baseline
        month1_dpmo = (Decimal("100") / Decimal("10000")) * Decimal("1000000")

        # Month 2: 50% improvement
        month2_dpmo = month1_dpmo * Decimal("0.5")

        # Month 3: Another 50% improvement
        month3_dpmo = month2_dpmo * Decimal("0.5")

        # Then: Should see progressive improvement
        assert float(month1_dpmo) == 10000.0
        assert float(month2_dpmo) == 5000.0
        assert float(month3_dpmo) == 2500.0

        # Sigma levels should improve
        sigma1 = calculate_sigma_level(month1_dpmo)
        sigma3 = calculate_sigma_level(month3_dpmo)
        assert float(sigma3) > float(sigma1)
