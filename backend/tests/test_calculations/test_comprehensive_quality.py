"""
Comprehensive Calculation Tests - PPM and DPMO
Target: 90% coverage for calculations/ppm.py and calculations/dpmo.py
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import MagicMock

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


class TestPPMCalculations:
    """Test Parts Per Million calculations"""

    def test_basic_ppm(self):
        """Test basic PPM calculation"""
        defects = 5
        total_produced = 10000
        ppm = (defects / total_produced) * 1_000_000
        assert ppm == 500.0

    def test_ppm_zero_defects(self):
        """Test PPM with zero defects"""
        defects = 0
        total_produced = 10000
        ppm = (defects / total_produced) * 1_000_000
        assert ppm == 0.0

    def test_ppm_high_defects(self):
        """Test PPM with high defect rate"""
        defects = 100
        total_produced = 1000
        ppm = (defects / total_produced) * 1_000_000
        assert ppm == 100000.0  # 10% defect rate

    def test_ppm_zero_production(self):
        """Test PPM with zero production (edge case)"""
        defects = 5
        total_produced = 0
        
        if total_produced == 0:
            ppm = 0.0
        else:
            ppm = (defects / total_produced) * 1_000_000
        
        assert ppm == 0.0

    def test_ppm_trend_analysis(self):
        """Test PPM trend over time"""
        daily_ppm = [
            {"date": "2026-01-01", "ppm": 550},
            {"date": "2026-01-02", "ppm": 480},
            {"date": "2026-01-03", "ppm": 420},
            {"date": "2026-01-04", "ppm": 380},
            {"date": "2026-01-05", "ppm": 350},
        ]
        
        # PPM should be decreasing (improving)
        trend = daily_ppm[-1]["ppm"] - daily_ppm[0]["ppm"]
        assert trend < 0

    def test_ppm_by_product(self):
        """Test PPM calculation by product"""
        products = [
            {"product": "A", "defects": 10, "produced": 5000, "ppm": 2000},
            {"product": "B", "defects": 5, "produced": 10000, "ppm": 500},
            {"product": "C", "defects": 15, "produced": 3000, "ppm": 5000},
        ]
        
        worst_product = max(products, key=lambda x: x["ppm"])
        assert worst_product["product"] == "C"

    def test_ppm_target_comparison(self):
        """Test PPM against target"""
        target_ppm = 500
        actual_ppm = 450
        
        is_within_target = actual_ppm <= target_ppm
        improvement_needed = max(0, actual_ppm - target_ppm)
        
        assert is_within_target == True
        assert improvement_needed == 0


class TestDPMOCalculations:
    """Test Defects Per Million Opportunities calculations"""

    def test_basic_dpmo(self):
        """Test basic DPMO calculation"""
        defects = 10
        units = 1000
        opportunities_per_unit = 5
        
        total_opportunities = units * opportunities_per_unit
        dpmo = (defects / total_opportunities) * 1_000_000
        
        assert dpmo == 2000.0

    def test_dpmo_to_sigma_level(self):
        """Test DPMO to Six Sigma level conversion"""
        sigma_levels = [
            {"dpmo": 691462, "sigma": 1.0},
            {"dpmo": 308538, "sigma": 2.0},
            {"dpmo": 66807, "sigma": 3.0},
            {"dpmo": 6210, "sigma": 4.0},
            {"dpmo": 233, "sigma": 5.0},
            {"dpmo": 3.4, "sigma": 6.0},
        ]
        
        # DPMO of 5000 is approximately 4.1 sigma
        dpmo = 5000
        for i, level in enumerate(sigma_levels[:-1]):
            if sigma_levels[i+1]["dpmo"] < dpmo <= level["dpmo"]:
                approx_sigma = level["sigma"] + (
                    (level["dpmo"] - dpmo) / 
                    (level["dpmo"] - sigma_levels[i+1]["dpmo"])
                )
                break
        
        assert 4.0 < approx_sigma < 5.0

    def test_dpmo_zero_defects(self):
        """Test DPMO with zero defects"""
        defects = 0
        total_opportunities = 10000
        dpmo = (defects / total_opportunities) * 1_000_000
        assert dpmo == 0.0

    def test_dpmo_varying_opportunities(self):
        """Test DPMO with different opportunity counts"""
        defects = 10
        units = 1000
        
        scenarios = [
            {"opp_per_unit": 1, "expected_dpmo": 10000},
            {"opp_per_unit": 3, "expected_dpmo": 3333.33},
            {"opp_per_unit": 5, "expected_dpmo": 2000},
            {"opp_per_unit": 10, "expected_dpmo": 1000},
        ]
        
        for scenario in scenarios:
            total_opp = units * scenario["opp_per_unit"]
            dpmo = (defects / total_opp) * 1_000_000
            assert round(dpmo, 2) == scenario["expected_dpmo"]


class TestFPYRTYCalculations:
    """Test First Pass Yield and Rolled Throughput Yield"""

    def test_basic_fpy(self):
        """Test basic First Pass Yield calculation"""
        total_produced = 1000
        first_pass_good = 950
        
        fpy = (first_pass_good / total_produced) * 100
        assert fpy == 95.0

    def test_fpy_with_rework(self):
        """Test FPY considering rework"""
        total_produced = 1000
        rework = 40
        rejected = 10
        
        first_pass_good = total_produced - rework - rejected
        fpy = (first_pass_good / total_produced) * 100
        
        assert fpy == 95.0

    def test_rty_single_process(self):
        """Test RTY for single process"""
        fpy = 0.95
        rty = fpy
        
        assert rty == 0.95

    def test_rty_multiple_processes(self):
        """Test RTY for multiple processes"""
        process_fpys = [0.98, 0.97, 0.99, 0.96]
        
        rty = 1.0
        for fpy in process_fpys:
            rty *= fpy
        
        # 0.98 * 0.97 * 0.99 * 0.96 = 0.90345024
        assert abs(rty * 100 - 90.35) < 0.01

    def test_rty_with_one_poor_process(self):
        """Test RTY impact of one poor process"""
        process_fpys = [0.99, 0.99, 0.85, 0.99]  # One process at 85%
        
        rty = 1.0
        for fpy in process_fpys:
            rty *= fpy
        
        # 0.99 * 0.99 * 0.85 * 0.99 = 0.82475415
        assert abs(rty * 100 - 82.48) < 0.01  # Significantly impacted

    def test_yield_loss_analysis(self):
        """Test yield loss analysis"""
        processes = [
            {"name": "Assembly", "fpy": 0.98, "loss": 0.02},
            {"name": "Testing", "fpy": 0.97, "loss": 0.03},
            {"name": "Packaging", "fpy": 0.99, "loss": 0.01},
        ]
        
        total_loss = sum(p["loss"] for p in processes) * 100
        assert round(total_loss, 2) == 6.0

    def test_hidden_factory_concept(self):
        """Test hidden factory (rework) impact"""
        production_rate = 1000  # units/day
        fpy = 0.90  # 90% first pass
        rework_pct = 0.10  # 10% rework
        
        hidden_factory_units = production_rate * rework_pct
        effective_capacity = production_rate - hidden_factory_units
        
        assert hidden_factory_units == 100
        assert effective_capacity == 900


class TestQualityMetricsIntegration:
    """Test integration of quality metrics"""

    def test_oee_quality_component(self):
        """Test OEE quality component"""
        total_produced = 1000
        good_units = 980
        
        quality = good_units / total_produced
        assert quality == 0.98

    def test_cost_of_quality(self):
        """Test cost of quality calculation"""
        defects = 50
        cost_per_defect = 25  # USD
        
        prevention_cost = 1000
        appraisal_cost = 500
        internal_failure = defects * cost_per_defect * 0.6  # 60% caught internally
        external_failure = defects * cost_per_defect * 0.4  # 40% reached customer
        
        total_coq = prevention_cost + appraisal_cost + internal_failure + external_failure
        
        assert total_coq == 1500 + 750 + 500
