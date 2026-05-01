"""Phase 1 dual-view orchestrators: PPM, DPMO, Sigma Level."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.services.calculations.dpmo import (
    DPMOInputs,
    PPMInputs,
    SigmaLevelInputs,
    calculate_dpmo,
    calculate_ppm,
    calculate_sigma_level,
)


class TestPPM:
    def test_standard_mode_textbook(self):
        # 5 / 10000 × 1,000,000 = 500
        result = calculate_ppm(PPMInputs(total_inspected=10000, total_defects=5))
        assert result.metric_name == "ppm"
        assert result.value == Decimal("500.00")

    def test_zero_inspected_yields_zero(self):
        assert calculate_ppm(PPMInputs(total_inspected=0, total_defects=0)).value == Decimal("0")

    def test_site_adjusted_equals_standard_in_phase_1(self):
        inputs = PPMInputs(total_inspected=10000, total_defects=10)
        assert calculate_ppm(inputs, "standard").value == calculate_ppm(inputs, "site_adjusted").value


class TestDPMO:
    def test_standard_mode_textbook(self):
        # 5 defects in (1000 × 10) = 500 DPMO
        inputs = DPMOInputs(total_defects=5, total_units=1000, opportunities_per_unit=10)
        result = calculate_dpmo(inputs)
        assert result.metric_name == "dpmo"
        assert result.value.dpmo == Decimal("500.00")
        assert result.value.total_opportunities == 10000

    def test_zero_units_yields_zero(self):
        inputs = DPMOInputs(total_defects=0, total_units=0, opportunities_per_unit=10)
        assert calculate_dpmo(inputs).value.dpmo == Decimal("0")

    def test_zero_opportunities_per_unit_rejected(self):
        with pytest.raises(ValidationError):
            DPMOInputs(total_defects=0, total_units=1000, opportunities_per_unit=0)


class TestSigmaLevel:
    def test_six_sigma(self):
        # DPMO ≤ 3.4 → 6 sigma
        assert calculate_sigma_level(SigmaLevelInputs(dpmo=Decimal("3.4"))).value == Decimal("6.0")

    def test_three_sigma(self):
        # DPMO ≤ 66807 → 3 sigma
        assert calculate_sigma_level(SigmaLevelInputs(dpmo=Decimal("66000"))).value == Decimal("3.0")

    def test_below_one_sigma_yields_zero(self):
        assert calculate_sigma_level(SigmaLevelInputs(dpmo=Decimal("700000"))).value == Decimal("0")
