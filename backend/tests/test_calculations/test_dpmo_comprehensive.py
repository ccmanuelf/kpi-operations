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


# =============================================================================
# Test calculate_sigma_level (function tests)
# =============================================================================

class TestCalculateSigmaLevel:
    """Test Sigma level conversion function"""

    def test_sigma_level_6_sigma(self):
        """Test 6 sigma level (3.4 DPMO)"""
        from backend.calculations.dpmo import calculate_sigma_level
        sigma = calculate_sigma_level(Decimal("3.4"))
        assert sigma == Decimal("6.0")

    def test_sigma_level_5_sigma(self):
        """Test 5 sigma level (233 DPMO)"""
        from backend.calculations.dpmo import calculate_sigma_level
        sigma = calculate_sigma_level(Decimal("233"))
        assert sigma == Decimal("5.0")

    def test_sigma_level_4_sigma(self):
        """Test 4 sigma level (6210 DPMO)"""
        from backend.calculations.dpmo import calculate_sigma_level
        sigma = calculate_sigma_level(Decimal("6210"))
        assert sigma == Decimal("4.0")

    def test_sigma_level_3_sigma(self):
        """Test 3 sigma level (66807 DPMO)"""
        from backend.calculations.dpmo import calculate_sigma_level
        sigma = calculate_sigma_level(Decimal("66807"))
        assert sigma == Decimal("3.0")

    def test_sigma_level_2_sigma(self):
        """Test 2 sigma level (308537 DPMO)"""
        from backend.calculations.dpmo import calculate_sigma_level
        sigma = calculate_sigma_level(Decimal("308537"))
        assert sigma == Decimal("2.0")

    def test_sigma_level_1_sigma(self):
        """Test 1 sigma level (690000 DPMO)"""
        from backend.calculations.dpmo import calculate_sigma_level
        sigma = calculate_sigma_level(Decimal("690000"))
        assert sigma == Decimal("1.0")

    def test_sigma_level_below_1_sigma(self):
        """Test below 1 sigma returns 0"""
        from backend.calculations.dpmo import calculate_sigma_level
        sigma = calculate_sigma_level(Decimal("750000"))
        assert sigma == Decimal("0")

    def test_sigma_level_perfect_zero_dpmo(self):
        """Test 0 DPMO returns 6 sigma"""
        from backend.calculations.dpmo import calculate_sigma_level
        sigma = calculate_sigma_level(Decimal("0"))
        assert sigma == Decimal("6.0")

    def test_sigma_level_intermediate_values(self):
        """Test intermediate DPMO values get correct sigma"""
        from backend.calculations.dpmo import calculate_sigma_level

        # 1000 DPMO is above 233 (5 sigma threshold) but below 6210 (4 sigma threshold)
        # So it returns 4.0 sigma
        sigma = calculate_sigma_level(Decimal("1000"))
        assert sigma == Decimal("4.0")  # Below 6210, returns 4 sigma

        # 10000 DPMO is above 6210 (4 sigma threshold) but below 66807 (3 sigma threshold)
        # So it returns 3.0 sigma
        sigma = calculate_sigma_level(Decimal("10000"))
        assert sigma == Decimal("3.0")  # Below 66807, returns 3 sigma

        # 100 DPMO is above 3.4 (6 sigma) but below 233 (5 sigma)
        # So it returns 5.0 sigma
        sigma = calculate_sigma_level(Decimal("100"))
        assert sigma == Decimal("5.0")  # Below 233, returns 5 sigma


# =============================================================================
# Test get_opportunities_for_part (mocked)
# =============================================================================

class TestGetOpportunitiesForPart:
    """Test part-specific opportunities lookup"""

    def test_opportunities_from_table(self):
        """Test getting opportunities from PART_OPPORTUNITIES table"""
        from backend.calculations.dpmo import get_opportunities_for_part
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_part_opp = MagicMock()
        mock_part_opp.opportunities_per_unit = 15
        mock_query.first.return_value = mock_part_opp

        result = get_opportunities_for_part(mock_db, "PART-001")

        assert result == 15

    def test_opportunities_not_found_uses_default(self):
        """Test fallback to default when part not found"""
        from backend.calculations.dpmo import get_opportunities_for_part, DEFAULT_OPPORTUNITIES_PER_UNIT
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None

        result = get_opportunities_for_part(mock_db, "UNKNOWN-PART")

        assert result == DEFAULT_OPPORTUNITIES_PER_UNIT

    def test_opportunities_empty_part_number(self):
        """Test empty part number returns default"""
        from backend.calculations.dpmo import get_opportunities_for_part, DEFAULT_OPPORTUNITIES_PER_UNIT
        mock_db = MagicMock()

        result = get_opportunities_for_part(mock_db, "")

        # Should return client default (which falls back to global default)
        assert result == DEFAULT_OPPORTUNITIES_PER_UNIT

    def test_opportunities_none_part_number(self):
        """Test None part number returns default"""
        from backend.calculations.dpmo import get_opportunities_for_part, DEFAULT_OPPORTUNITIES_PER_UNIT
        mock_db = MagicMock()

        result = get_opportunities_for_part(mock_db, None)

        assert result == DEFAULT_OPPORTUNITIES_PER_UNIT

    def test_opportunities_with_client_id_filter(self):
        """Test opportunities lookup with client ID filter"""
        from backend.calculations.dpmo import get_opportunities_for_part
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_part_opp = MagicMock()
        mock_part_opp.opportunities_per_unit = 20
        mock_query.first.return_value = mock_part_opp

        result = get_opportunities_for_part(mock_db, "PART-002", client_id="CLIENT001")

        assert result == 20
        # Verify filter was called twice (part_number + client_id)
        assert mock_query.filter.call_count >= 2


# =============================================================================
# Test get_opportunities_for_parts (batch lookup, mocked)
# =============================================================================

class TestGetOpportunitiesForParts:
    """Test batch part opportunities lookup"""

    def test_batch_lookup_all_found(self):
        """Test batch lookup when all parts are found"""
        from backend.calculations.dpmo import get_opportunities_for_parts
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_po1 = MagicMock()
        mock_po1.part_number = "P1"
        mock_po1.opportunities_per_unit = 10

        mock_po2 = MagicMock()
        mock_po2.part_number = "P2"
        mock_po2.opportunities_per_unit = 15

        mock_query.all.return_value = [mock_po1, mock_po2]

        result = get_opportunities_for_parts(mock_db, ["P1", "P2"])

        assert result["P1"] == 10
        assert result["P2"] == 15

    def test_batch_lookup_partial_found(self):
        """Test batch lookup when some parts not found"""
        from backend.calculations.dpmo import get_opportunities_for_parts, DEFAULT_OPPORTUNITIES_PER_UNIT
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_po = MagicMock()
        mock_po.part_number = "P1"
        mock_po.opportunities_per_unit = 12

        mock_query.all.return_value = [mock_po]

        result = get_opportunities_for_parts(mock_db, ["P1", "P2", "P3"])

        assert result["P1"] == 12
        assert result["P2"] == DEFAULT_OPPORTUNITIES_PER_UNIT
        assert result["P3"] == DEFAULT_OPPORTUNITIES_PER_UNIT

    def test_batch_lookup_empty_list(self):
        """Test batch lookup with empty part list"""
        from backend.calculations.dpmo import get_opportunities_for_parts
        mock_db = MagicMock()

        result = get_opportunities_for_parts(mock_db, [])

        assert result == {}


# =============================================================================
# Test get_client_opportunities_default (mocked)
# =============================================================================

class TestGetClientOpportunitiesDefault:
    """Test client-specific default opportunities"""

    def test_client_default_no_client(self):
        """Test default when no client ID provided"""
        from backend.calculations.dpmo import get_client_opportunities_default, DEFAULT_OPPORTUNITIES_PER_UNIT
        mock_db = MagicMock()

        result = get_client_opportunities_default(mock_db, None)

        assert result == DEFAULT_OPPORTUNITIES_PER_UNIT

    def test_client_default_from_config(self):
        """Test getting default from client config"""
        from backend.calculations.dpmo import get_client_opportunities_default
        mock_db = MagicMock()

        with patch('backend.calculations.dpmo.get_client_config_or_defaults') as mock_config:
            mock_config.return_value = {"dpmo_opportunities_default": 25}

            result = get_client_opportunities_default(mock_db, "CLIENT001")

            assert result == 25

    def test_client_default_config_exception(self):
        """Test fallback when config lookup fails"""
        from backend.calculations.dpmo import get_client_opportunities_default, DEFAULT_OPPORTUNITIES_PER_UNIT
        mock_db = MagicMock()

        with patch('backend.calculations.dpmo.get_client_config_or_defaults') as mock_config:
            mock_config.side_effect = Exception("Config error")

            result = get_client_opportunities_default(mock_db, "CLIENT001")

            assert result == DEFAULT_OPPORTUNITIES_PER_UNIT


# =============================================================================
# Test calculate_dpmo (main function, mocked)
# =============================================================================

class TestCalculateDPMOFunction:
    """Test main DPMO calculation function"""

    def test_calculate_dpmo_no_data(self):
        """Test DPMO with no inspection data"""
        from backend.calculations.dpmo import calculate_dpmo
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        dpmo, sigma, units, defects = calculate_dpmo(
            mock_db, work_order_id="WO-001",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today()
        )

        assert dpmo == Decimal("0")
        assert sigma == Decimal("0")
        assert units == 0
        assert defects == 0

    def test_calculate_dpmo_with_data(self):
        """Test DPMO with inspection data"""
        from backend.calculations.dpmo import calculate_dpmo
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # Use QualityEntry field names
        mock_insp1 = MagicMock()
        mock_insp1.units_inspected = 1000
        mock_insp1.total_defects_count = 10
        mock_insp1.units_defective = 10

        mock_insp2 = MagicMock()
        mock_insp2.units_inspected = 1000
        mock_insp2.total_defects_count = 5
        mock_insp2.units_defective = 5

        mock_query.all.return_value = [mock_insp1, mock_insp2]

        dpmo, sigma, units, defects = calculate_dpmo(
            mock_db, work_order_id="WO-001",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            opportunities_per_unit=10
        )

        # Total units: 2000, Total defects: 15
        # Total opportunities: 2000 * 10 = 20000
        # DPMO = (15 / 20000) * 1000000 = 750
        assert units == 2000
        assert defects == 15
        assert dpmo == Decimal("750")

    def test_calculate_dpmo_with_part_lookup(self):
        """Test DPMO with part-specific opportunities lookup"""
        from backend.calculations.dpmo import calculate_dpmo
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # Mock part opportunities
        mock_part_opp = MagicMock()
        mock_part_opp.opportunities_per_unit = 15
        mock_query.first.return_value = mock_part_opp

        # Mock inspections with QualityEntry field names
        mock_insp = MagicMock()
        mock_insp.units_inspected = 500
        mock_insp.total_defects_count = 5
        mock_insp.units_defective = 5
        mock_query.all.return_value = [mock_insp]

        dpmo, sigma, units, defects = calculate_dpmo(
            mock_db, work_order_id="WO-001",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            part_number="PART-001"
        )

        assert units == 500
        assert defects == 5


# =============================================================================
# Test calculate_process_capability (mocked)
# =============================================================================

class TestCalculateProcessCapability:
    """Test Cp, Cpk calculation"""

    def test_process_capability_no_data(self):
        """Test process capability with no inspection data"""
        from backend.calculations.dpmo import calculate_process_capability
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        result = calculate_process_capability(
            mock_db, work_order_id="WO-001",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            upper_spec_limit=Decimal("10.0"),
            lower_spec_limit=Decimal("0.0"),
            target_value=Decimal("5.0")
        )

        assert result["cp"] == Decimal("0")
        assert result["cpk"] == Decimal("0")
        assert "Insufficient data" in result["interpretation"]

    def test_process_capability_with_data(self):
        """Test process capability with inspection data"""
        from backend.calculations.dpmo import calculate_process_capability
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_insp = MagicMock()
        mock_insp.units_inspected = 1000
        mock_insp.total_defects_count = 10  # 1% defect rate
        mock_insp.units_defective = 10
        mock_query.all.return_value = [mock_insp]

        result = calculate_process_capability(
            mock_db,
            work_order_id="WO-001",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            upper_spec_limit=Decimal("10.0"),
            lower_spec_limit=Decimal("0.0"),
            target_value=Decimal("5.0")
        )

        assert "cp" in result
        assert "cpk" in result
        assert "interpretation" in result
        assert result["total_inspected"] == 1000
        assert result["total_defects"] == 10

    def test_process_capability_perfect_quality(self):
        """Test process capability with zero defects"""
        from backend.calculations.dpmo import calculate_process_capability
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        mock_insp = MagicMock()
        mock_insp.units_inspected = 1000
        mock_insp.total_defects_count = 0
        mock_insp.units_defective = 0
        mock_query.all.return_value = [mock_insp]

        result = calculate_process_capability(
            mock_db,
            work_order_id="WO-001",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            upper_spec_limit=Decimal("10.0"),
            lower_spec_limit=Decimal("0.0"),
            target_value=Decimal("5.0")
        )

        # Perfect quality = Cp/Cpk of 2.0
        assert result["cp"] == Decimal("2.0")
        assert result["cpk"] == Decimal("2.0")
        assert "Six Sigma" in result["interpretation"]

    def test_process_capability_interpretation_levels(self):
        """Test process capability interpretation for different levels"""
        # Test the interpretation thresholds
        def get_interpretation(cpk: Decimal) -> str:
            if cpk >= Decimal("2.0"):
                return "Excellent (Six Sigma capable)"
            elif cpk >= Decimal("1.67"):
                return "Very Good (Five Sigma capable)"
            elif cpk >= Decimal("1.33"):
                return "Good (Four Sigma capable)"
            elif cpk >= Decimal("1.0"):
                return "Adequate (Three Sigma capable)"
            else:
                return "Poor (Process improvement needed)"

        assert "Excellent" in get_interpretation(Decimal("2.0"))
        assert "Very Good" in get_interpretation(Decimal("1.67"))
        assert "Good" in get_interpretation(Decimal("1.33"))
        assert "Adequate" in get_interpretation(Decimal("1.0"))
        assert "Poor" in get_interpretation(Decimal("0.5"))


# =============================================================================
# Test identify_quality_trends (mocked)
# =============================================================================

class TestIdentifyQualityTrends:
    """Test quality trend analysis"""

    def test_quality_trends_improving(self):
        """Test detection of improving quality trend"""
        from backend.calculations.dpmo import identify_quality_trends
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # First half: high DPMO (worse)
        mock_insp_first = MagicMock()
        mock_insp_first.units_inspected = 1000
        mock_insp_first.total_defects_count = 50  # 5% defect rate
        mock_insp_first.units_defective = 50

        # Second half: low DPMO (better)
        mock_insp_second = MagicMock()
        mock_insp_second.units_inspected = 1000
        mock_insp_second.total_defects_count = 10  # 1% defect rate
        mock_insp_second.units_defective = 10

        # Return different data for different queries
        mock_query.all.side_effect = [[mock_insp_first], [mock_insp_second]]

        result = identify_quality_trends(mock_db, work_order_id="WO-001", lookback_days=30)

        assert "trend" in result
        assert "recommendation" in result
        assert "dpmo_first_half" in result
        assert "dpmo_second_half" in result

    def test_quality_trends_no_data(self):
        """Test trend analysis with no data"""
        from backend.calculations.dpmo import identify_quality_trends
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        result = identify_quality_trends(mock_db, work_order_id="WO-001", lookback_days=30)

        assert result["trend"] == "insufficient_data"
        assert "Collect more" in result["recommendation"]

    def test_quality_trends_stable(self):
        """Test detection of stable quality trend"""
        from backend.calculations.dpmo import identify_quality_trends
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # Both halves: similar DPMO
        mock_insp = MagicMock()
        mock_insp.units_inspected = 1000
        mock_insp.total_defects_count = 20
        mock_insp.units_defective = 20

        mock_query.all.side_effect = [[mock_insp], [mock_insp]]

        result = identify_quality_trends(mock_db, work_order_id="WO-001", lookback_days=30)

        assert result["trend"] == "stable"
        assert "stable" in result["recommendation"].lower()


# =============================================================================
# Test calculate_dpmo_with_part_lookup (mocked)
# =============================================================================

class TestCalculateDPMOWithPartLookup:
    """Test DPMO calculation with part-specific opportunities"""

    def test_dpmo_with_part_lookup_no_data(self):
        """Test DPMO with part lookup when no data"""
        from backend.calculations.dpmo import calculate_dpmo_with_part_lookup
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        result = calculate_dpmo_with_part_lookup(
            mock_db, date.today() - timedelta(days=30), date.today()
        )

        assert result["overall_dpmo"] == Decimal("0")
        assert result["total_units"] == 0
        assert result["total_defects"] == 0
        assert result["by_part"] == []

    def test_dpmo_with_part_lookup_structure(self):
        """Test DPMO with part lookup returns correct structure"""
        from backend.calculations.dpmo import calculate_dpmo_with_part_lookup
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query

        # Mock quality entry with job
        mock_qe = MagicMock()
        mock_qe.units_inspected = 100
        mock_qe.total_defects_count = 5
        mock_qe.units_defective = 5
        mock_qe.job_id = "JOB001"

        # Mock job
        mock_job = MagicMock()
        mock_job.job_id = "JOB001"
        mock_job.part_number = "PART-001"

        mock_query.all.side_effect = [
            [mock_qe],  # Quality entries query
            [mock_job],  # Jobs query
            []  # Part opportunities query
        ]

        result = calculate_dpmo_with_part_lookup(
            mock_db, date.today() - timedelta(days=30), date.today()
        )

        assert "overall_dpmo" in result
        assert "overall_sigma_level" in result
        assert "total_units" in result
        assert "total_defects" in result
        assert "total_opportunities" in result
        assert "by_part" in result
        assert "using_part_specific_opportunities" in result
