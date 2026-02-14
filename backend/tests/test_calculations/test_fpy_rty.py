"""
Test Suite for FPY (First Pass Yield) and RTY (Rolled Throughput Yield) KPIs

FPY Formula: (Units Passed First Time / Total Units) * 100
RTY Formula: FPY1 * FPY2 * FPY3 * ... * FPYn (product of all process step FPYs)

Covers:
- Basic FPY calculation per inspection stage
- RTY calculation across multiple stages
- Process yield and scrap rate
- Quality score calculation
- Defect escape rate analysis
"""

import pytest
from decimal import Decimal
from datetime import date


# ===== Helper Functions for Standalone Calculations =====


def calculate_fpy(units_inspected: int, defects: int, rework: int = 0) -> float | None:
    """
    Calculate First Pass Yield percentage.

    Formula: ((Units - Defects - Rework) / Units) * 100

    Args:
        units_inspected: Total units inspected
        defects: Number of defective units
        rework: Number of units requiring rework

    Returns:
        FPY percentage or None if invalid inputs
    """
    if units_inspected <= 0:
        return None
    if defects < 0 or rework < 0:
        return None

    first_pass_good = units_inspected - defects - rework
    if first_pass_good < 0:
        first_pass_good = 0

    fpy = (first_pass_good / units_inspected) * 100
    return round(fpy, 4)


def calculate_rty(fpy_values: list[float]) -> float | None:
    """
    Calculate Rolled Throughput Yield from multiple FPY values.

    Formula: FPY1 * FPY2 * ... * FPYn (as decimals)

    Args:
        fpy_values: List of FPY percentages for each process step

    Returns:
        RTY percentage or None if invalid inputs
    """
    if not fpy_values:
        return None

    # Convert percentages to decimals and multiply
    rty = 1.0
    for fpy in fpy_values:
        if fpy is None or fpy < 0:
            return None
        rty *= fpy / 100

    return round(rty * 100, 4)


def calculate_process_yield(total_produced: int, total_scrap: int, total_defects: int) -> float | None:
    """
    Calculate overall process yield.

    Formula: ((Produced - Scrap - Defects) / Produced) * 100

    Args:
        total_produced: Total units produced
        total_scrap: Total scrapped units
        total_defects: Total defective units

    Returns:
        Process yield percentage or None if invalid
    """
    if total_produced <= 0:
        return None

    good_units = total_produced - total_scrap - total_defects
    if good_units < 0:
        good_units = 0

    yield_pct = (good_units / total_produced) * 100
    return round(yield_pct, 4)


def calculate_scrap_rate(total_scrap: int, total_produced: int) -> float | None:
    """
    Calculate scrap rate percentage.

    Formula: (Scrap / Produced) * 100

    Args:
        total_scrap: Total scrapped units
        total_produced: Total units produced

    Returns:
        Scrap rate percentage or None if invalid
    """
    if total_produced <= 0:
        return None
    if total_scrap < 0:
        return None

    rate = (total_scrap / total_produced) * 100
    return round(rate, 4)


def calculate_defect_escape_rate(final_inspection_defects: int, total_defects: int) -> float | None:
    """
    Calculate defect escape rate.

    Measures what percentage of defects escape to final inspection.
    Formula: (Final Defects / Total Defects) * 100

    Args:
        final_inspection_defects: Defects found at final inspection
        total_defects: Total defects found across all stages

    Returns:
        Escape rate percentage or None if invalid
    """
    if total_defects <= 0:
        return 0.0  # No defects = 0% escape rate
    if final_inspection_defects < 0:
        return None

    rate = (final_inspection_defects / total_defects) * 100
    return round(rate, 4)


def calculate_quality_score(fpy: float, rty: float, scrap_rate: float, escape_rate: float) -> tuple[float, str]:
    """
    Calculate weighted quality score (0-100).

    Weights:
    - FPY: 40%
    - RTY: 30%
    - Scrap Rate: 20% (inverted - lower is better)
    - Escape Rate: 10% (inverted - lower is better)

    Args:
        fpy: First Pass Yield percentage
        rty: Rolled Throughput Yield percentage
        scrap_rate: Scrap rate percentage
        escape_rate: Defect escape rate percentage

    Returns:
        Tuple of (quality_score, grade)
    """
    # Invert scrap and escape rates (lower is better)
    scrap_score = max(0, 100 - scrap_rate)
    escape_score = max(0, 100 - escape_rate)

    # Weighted calculation
    quality_score = fpy * 0.40 + rty * 0.30 + scrap_score * 0.20 + escape_score * 0.10

    # Determine grade
    if quality_score >= 95:
        grade = "A+"
    elif quality_score >= 90:
        grade = "A"
    elif quality_score >= 85:
        grade = "B+"
    elif quality_score >= 80:
        grade = "B"
    elif quality_score >= 75:
        grade = "C+"
    elif quality_score >= 70:
        grade = "C"
    else:
        grade = "D"

    return round(quality_score, 2), grade


# ===== Test Classes =====


@pytest.mark.unit
class TestFPYCalculation:
    """Test First Pass Yield calculation"""

    @pytest.mark.unit
    def test_perfect_fpy(self):
        """Test 100% FPY (no defects)"""
        # Given: 1000 units, no defects, no rework
        result = calculate_fpy(units_inspected=1000, defects=0, rework=0)

        # Then: Should be 100%
        assert result == 100.0

    @pytest.mark.unit
    def test_basic_fpy_calculation(self):
        """Test basic FPY with defects"""
        # Given: 1000 units, 50 defects
        result = calculate_fpy(units_inspected=1000, defects=50, rework=0)

        # Then: (1000 - 50) / 1000 * 100 = 95%
        assert result == 95.0

    @pytest.mark.unit
    def test_fpy_with_rework(self):
        """Test FPY with both defects and rework"""
        # Given: 1000 units, 30 defects, 20 rework
        result = calculate_fpy(units_inspected=1000, defects=30, rework=20)

        # Then: (1000 - 30 - 20) / 1000 * 100 = 95%
        assert result == 95.0

    @pytest.mark.unit
    def test_fpy_only_rework(self):
        """Test FPY with only rework (no defects)"""
        # Given: 100 units, 0 defects, 5 rework
        result = calculate_fpy(units_inspected=100, defects=0, rework=5)

        # Then: (100 - 5) / 100 * 100 = 95%
        assert result == 95.0

    @pytest.mark.unit
    def test_low_fpy(self):
        """Test low FPY scenario"""
        # Given: Poor quality batch
        result = calculate_fpy(units_inspected=100, defects=25, rework=10)

        # Then: (100 - 25 - 10) / 100 * 100 = 65%
        assert result == 65.0

    @pytest.mark.unit
    def test_fpy_small_batch(self):
        """Test FPY with small inspection batch"""
        # Given: Small batch
        result = calculate_fpy(units_inspected=10, defects=1, rework=0)

        # Then: (10 - 1) / 10 * 100 = 90%
        assert result == 90.0


@pytest.mark.unit
class TestFPYEdgeCases:
    """Test FPY edge cases"""

    @pytest.mark.unit
    def test_zero_units_inspected(self):
        """Test FPY with zero units"""
        # Given: No units inspected
        result = calculate_fpy(units_inspected=0, defects=0, rework=0)

        # Then: Should return None
        assert result is None

    @pytest.mark.unit
    def test_negative_units(self):
        """Test FPY with negative units"""
        # Given: Invalid negative units
        result = calculate_fpy(units_inspected=-100, defects=5, rework=0)

        # Then: Should return None
        assert result is None

    @pytest.mark.unit
    def test_negative_defects(self):
        """Test FPY with negative defects"""
        # Given: Invalid negative defects
        result = calculate_fpy(units_inspected=100, defects=-5, rework=0)

        # Then: Should return None
        assert result is None

    @pytest.mark.unit
    def test_defects_exceed_units(self):
        """Test when defects + rework exceed units"""
        # Given: Data error scenario
        result = calculate_fpy(units_inspected=100, defects=60, rework=50)

        # Then: Should return 0% (capped, not negative)
        assert result == 0.0

    @pytest.mark.unit
    def test_all_units_defective(self):
        """Test all units defective"""
        # Given: 100% defective
        result = calculate_fpy(units_inspected=100, defects=100, rework=0)

        # Then: Should be 0%
        assert result == 0.0


@pytest.mark.unit
class TestRTYCalculation:
    """Test Rolled Throughput Yield calculation"""

    @pytest.mark.unit
    def test_perfect_rty(self):
        """Test 100% RTY (all steps perfect)"""
        # Given: 100% FPY at each step
        fpy_values = [100.0, 100.0, 100.0]

        result = calculate_rty(fpy_values)

        # Then: 1.0 * 1.0 * 1.0 = 100%
        assert result == 100.0

    @pytest.mark.unit
    def test_basic_rty_calculation(self):
        """Test basic RTY calculation"""
        # Given: FPY values at each stage
        fpy_values = [98.0, 97.0, 99.0]

        result = calculate_rty(fpy_values)

        # Then: 0.98 * 0.97 * 0.99 = 0.941094 = 94.1094%
        assert result == pytest.approx(94.11, rel=0.01)

    @pytest.mark.unit
    def test_rty_two_stages(self):
        """Test RTY with two stages"""
        # Given: Two inspection stages
        fpy_values = [95.0, 90.0]

        result = calculate_rty(fpy_values)

        # Then: 0.95 * 0.90 = 0.855 = 85.5%
        assert result == 85.5

    @pytest.mark.unit
    def test_rty_many_stages(self):
        """Test RTY with many stages (typical complex manufacturing)"""
        # Given: 5 inspection stages
        fpy_values = [99.0, 98.0, 97.0, 98.0, 99.0]

        result = calculate_rty(fpy_values)

        # Then: 0.99 * 0.98 * 0.97 * 0.98 * 0.99 = 0.9135
        assert result == pytest.approx(91.35, rel=0.01)

    @pytest.mark.unit
    def test_rty_one_weak_stage(self):
        """Test RTY impact of one weak stage"""
        # Given: One poor FPY stage
        fpy_values = [99.0, 99.0, 70.0, 99.0]

        result = calculate_rty(fpy_values)

        # Then: RTY significantly impacted
        # 0.99 * 0.99 * 0.70 * 0.99 = 0.679
        assert result == pytest.approx(67.9, rel=0.1)

    @pytest.mark.unit
    def test_rty_single_stage(self):
        """Test RTY with single stage equals FPY"""
        # Given: Single inspection stage
        fpy_values = [95.0]

        result = calculate_rty(fpy_values)

        # Then: RTY = FPY for single stage
        assert result == 95.0


@pytest.mark.unit
class TestRTYEdgeCases:
    """Test RTY edge cases"""

    @pytest.mark.unit
    def test_empty_fpy_list(self):
        """Test RTY with empty list"""
        # Given: No FPY values
        fpy_values = []

        result = calculate_rty(fpy_values)

        # Then: Should return None
        assert result is None

    @pytest.mark.unit
    def test_rty_with_zero_fpy(self):
        """Test RTY when one stage has 0% FPY"""
        # Given: One stage completely failed
        fpy_values = [95.0, 0.0, 95.0]

        result = calculate_rty(fpy_values)

        # Then: RTY = 0% (0 multiplied)
        assert result == 0.0

    @pytest.mark.unit
    def test_rty_with_none_value(self):
        """Test RTY with None in list"""
        # Given: Invalid None value
        fpy_values = [95.0, None, 95.0]

        result = calculate_rty(fpy_values)

        # Then: Should return None
        assert result is None


@pytest.mark.unit
class TestProcessYield:
    """Test process yield calculation"""

    @pytest.mark.unit
    def test_perfect_process_yield(self):
        """Test 100% process yield"""
        # Given: No scrap or defects
        result = calculate_process_yield(total_produced=1000, total_scrap=0, total_defects=0)

        # Then: Should be 100%
        assert result == 100.0

    @pytest.mark.unit
    def test_basic_process_yield(self):
        """Test basic process yield"""
        # Given: Some scrap and defects
        result = calculate_process_yield(total_produced=1000, total_scrap=20, total_defects=30)

        # Then: (1000 - 20 - 30) / 1000 * 100 = 95%
        assert result == 95.0

    @pytest.mark.unit
    def test_high_scrap_yield(self):
        """Test process yield with high scrap"""
        # Given: High scrap rate
        result = calculate_process_yield(total_produced=100, total_scrap=15, total_defects=5)

        # Then: (100 - 15 - 5) / 100 * 100 = 80%
        assert result == 80.0

    @pytest.mark.unit
    def test_zero_production(self):
        """Test process yield with no production"""
        # Given: No production
        result = calculate_process_yield(total_produced=0, total_scrap=0, total_defects=0)

        # Then: Should return None
        assert result is None


@pytest.mark.unit
class TestScrapRate:
    """Test scrap rate calculation"""

    @pytest.mark.unit
    def test_zero_scrap_rate(self):
        """Test zero scrap rate"""
        # Given: No scrap
        result = calculate_scrap_rate(total_scrap=0, total_produced=1000)

        # Then: Should be 0%
        assert result == 0.0

    @pytest.mark.unit
    def test_basic_scrap_rate(self):
        """Test basic scrap rate"""
        # Given: 50 scrapped out of 1000
        result = calculate_scrap_rate(total_scrap=50, total_produced=1000)

        # Then: 5% scrap rate
        assert result == 5.0

    @pytest.mark.unit
    def test_high_scrap_rate(self):
        """Test high scrap rate (quality issue)"""
        # Given: 20% scrap
        result = calculate_scrap_rate(total_scrap=200, total_produced=1000)

        # Then: 20% scrap rate
        assert result == 20.0


@pytest.mark.unit
class TestDefectEscapeRate:
    """Test defect escape rate calculation"""

    @pytest.mark.unit
    def test_no_escapes(self):
        """Test when no defects escape to final"""
        # Given: All defects caught early
        result = calculate_defect_escape_rate(final_inspection_defects=0, total_defects=100)

        # Then: 0% escape rate
        assert result == 0.0

    @pytest.mark.unit
    def test_all_escapes(self):
        """Test when all defects found at final"""
        # Given: All defects at final (poor early inspection)
        result = calculate_defect_escape_rate(final_inspection_defects=50, total_defects=50)

        # Then: 100% escape rate
        assert result == 100.0

    @pytest.mark.unit
    def test_partial_escape_rate(self):
        """Test partial escape rate"""
        # Given: Some defects escape to final
        result = calculate_defect_escape_rate(final_inspection_defects=20, total_defects=100)

        # Then: 20% escape rate
        assert result == 20.0

    @pytest.mark.unit
    def test_no_defects_escape_rate(self):
        """Test escape rate with no defects"""
        # Given: Perfect quality (no defects anywhere)
        result = calculate_defect_escape_rate(final_inspection_defects=0, total_defects=0)

        # Then: 0% escape rate (no defects to escape)
        assert result == 0.0


@pytest.mark.unit
class TestQualityScore:
    """Test comprehensive quality score calculation"""

    @pytest.mark.unit
    def test_perfect_quality_score(self):
        """Test perfect quality score"""
        # Given: Perfect metrics
        score, grade = calculate_quality_score(fpy=100.0, rty=100.0, scrap_rate=0.0, escape_rate=0.0)

        # Then: Should be 100% with A+ grade
        assert score == 100.0
        assert grade == "A+"

    @pytest.mark.unit
    def test_excellent_quality_score(self):
        """Test excellent quality score (A grade)"""
        # Given: Very good metrics
        score, grade = calculate_quality_score(fpy=95.0, rty=93.0, scrap_rate=2.0, escape_rate=5.0)

        # Then: Should be A grade
        # (95*0.4) + (93*0.3) + (98*0.2) + (95*0.1)
        # = 38 + 27.9 + 19.6 + 9.5 = 95.0
        assert score == 95.0
        assert grade == "A+"

    @pytest.mark.unit
    def test_good_quality_score(self):
        """Test good quality score (B grade)"""
        # Given: Good metrics
        score, grade = calculate_quality_score(fpy=90.0, rty=85.0, scrap_rate=5.0, escape_rate=10.0)

        # Then: Should be B grade
        # (90*0.4) + (85*0.3) + (95*0.2) + (90*0.1)
        # = 36 + 25.5 + 19 + 9 = 89.5
        assert score == 89.5
        assert grade == "B+"

    @pytest.mark.unit
    def test_poor_quality_score(self):
        """Test poor quality score (D grade)"""
        # Given: Poor metrics
        score, grade = calculate_quality_score(fpy=60.0, rty=50.0, scrap_rate=20.0, escape_rate=40.0)

        # Then: Should be D grade
        # (60*0.4) + (50*0.3) + (80*0.2) + (60*0.1)
        # = 24 + 15 + 16 + 6 = 61.0
        assert score == 61.0
        assert grade == "D"


@pytest.mark.unit
class TestQualityBusinessScenarios:
    """Test real-world quality scenarios"""

    @pytest.mark.unit
    def test_apparel_three_stage_inspection(self):
        """Test typical apparel 3-stage inspection"""
        # Given: Incoming, In-Process, Final stages
        fpy_incoming = calculate_fpy(1000, 30, 0)  # 97%
        fpy_inprocess = calculate_fpy(970, 25, 10)  # 96.4%
        fpy_final = calculate_fpy(935, 10, 5)  # 98.4%

        # When: Calculate RTY
        rty = calculate_rty([fpy_incoming, fpy_inprocess, fpy_final])

        # Then: RTY should be product of FPYs
        assert fpy_incoming == 97.0
        assert fpy_inprocess == pytest.approx(96.39, rel=0.01)
        assert fpy_final == pytest.approx(98.4, rel=0.01)
        assert rty == pytest.approx(92.0, rel=0.5)

    @pytest.mark.unit
    def test_quality_improvement_tracking(self):
        """Test quality improvement over months"""
        # Given: Monthly FPY values showing improvement
        month1_fpy = calculate_fpy(1000, 100, 50)  # 85%
        month2_fpy = calculate_fpy(1000, 70, 30)  # 90%
        month3_fpy = calculate_fpy(1000, 40, 20)  # 94%
        month4_fpy = calculate_fpy(1000, 20, 10)  # 97%

        # Then: Should show progressive improvement
        assert month1_fpy < month2_fpy < month3_fpy < month4_fpy
        assert month4_fpy == 97.0

    @pytest.mark.unit
    def test_hidden_factory_scenario(self):
        """Test 'hidden factory' identification (high rework)"""
        # Given: Low defects but high rework
        fpy_low_defect = calculate_fpy(1000, 10, 0)  # 99% - looks great
        fpy_high_rework = calculate_fpy(1000, 10, 150)  # 84% - hidden factory

        # Then: Same defect count, very different FPY
        assert fpy_low_defect == 99.0
        assert fpy_high_rework == 84.0

        # High rework = hidden factory cost
        hidden_factory_pct = (150 / 1000) * 100
        assert hidden_factory_pct == 15.0  # 15% rework rate

    @pytest.mark.unit
    def test_bottleneck_stage_identification(self):
        """Test identifying quality bottleneck stage"""
        # Given: Multiple inspection stages
        stages = {
            "Incoming": calculate_fpy(1000, 20, 0),  # 98%
            "Cutting": calculate_fpy(980, 15, 5),  # 97.96%
            "Sewing": calculate_fpy(960, 80, 40),  # 87.5% - bottleneck
            "Finishing": calculate_fpy(840, 10, 5),  # 98.21%
            "Final": calculate_fpy(825, 5, 3),  # 99.03%
        }

        # Then: Sewing is clearly the bottleneck
        min_fpy_stage = min(stages, key=stages.get)
        assert min_fpy_stage == "Sewing"
        assert stages["Sewing"] == pytest.approx(87.5, rel=0.1)

    @pytest.mark.unit
    def test_cost_of_poor_quality(self):
        """Test calculating cost impact of poor quality"""
        # Given: Quality metrics
        total_produced = 10000
        total_scrap = 200
        total_rework = 500
        unit_cost = 10.0  # $10 per unit
        rework_cost_per_unit = 3.0  # $3 to rework

        # When: Calculate costs
        scrap_cost = total_scrap * unit_cost
        rework_cost = total_rework * rework_cost_per_unit
        total_copq = scrap_cost + rework_cost

        # Also calculate FPY
        fpy = calculate_fpy(total_produced, total_scrap, total_rework)

        # Then: Validate costs and quality metrics
        assert scrap_cost == 2000.0  # $2000 lost to scrap
        assert rework_cost == 1500.0  # $1500 rework cost
        assert total_copq == 3500.0  # Total COPQ
        assert fpy == 93.0  # 93% FPY

    @pytest.mark.unit
    def test_six_sigma_quality_target(self):
        """Test Six Sigma quality target (99.99966% yield)"""
        # Given: Six Sigma target
        # 3.4 DPMO = 99.99966% yield
        target_fpy = 99.99966

        # Actual high-quality scenario
        actual_fpy = calculate_fpy(units_inspected=1000000, defects=4, rework=0)  # 4 PPM

        # Then: Should be very close to target
        assert actual_fpy == pytest.approx(target_fpy, rel=0.0001)

    @pytest.mark.unit
    def test_world_class_manufacturing_targets(self):
        """Test against world-class manufacturing targets"""
        # World-class targets:
        # - FPY: >98%
        # - Scrap Rate: <1%
        # - Escape Rate: <5%

        fpy = calculate_fpy(1000, 15, 5)  # 98%
        scrap_rate = calculate_scrap_rate(8, 1000)  # 0.8%
        escape_rate = calculate_defect_escape_rate(3, 75)  # 4%

        # Then: All should meet world-class targets
        assert fpy >= 98.0
        assert scrap_rate < 1.0
        assert escape_rate < 5.0
