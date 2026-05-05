"""Phase 1 dual-view orchestrators: FPY, RTY, Job Yield, Recovery,
Scrap, Defect Escape, Quality Score, Rework/Repair Impact."""

from decimal import Decimal

from backend.services.calculations.quality import (
    DefectEscapeRateInputs,
    FPYInputs,
    ImpactInputs,
    JobYieldInputs,
    QualityScoreInputs,
    RTYInputs,
    RecoveryRateInputs,
    ScrapRateInputs,
    calculate_defect_escape_rate,
    calculate_fpy,
    calculate_job_yield,
    calculate_quality_score,
    calculate_recovery_rate,
    calculate_repair_impact,
    calculate_rework_impact,
    calculate_rty,
    calculate_scrap_rate,
)


class TestFPY:
    def test_standard_mode_textbook(self):
        result = calculate_fpy(FPYInputs(total_passed=95, total_inspected=100))
        assert result.metric_name == "fpy"
        assert result.value == Decimal("95.00")

    def test_zero_inspected_yields_zero(self):
        assert calculate_fpy(FPYInputs(total_passed=0, total_inspected=0)).value == Decimal("0")

    def test_site_adjusted_equals_standard_in_phase_1(self):
        inputs = FPYInputs(total_passed=85, total_inspected=100)
        assert calculate_fpy(inputs, "standard").value == calculate_fpy(inputs, "site_adjusted").value


class TestRTY:
    def test_standard_mode_textbook(self):
        # 0.95 × 0.90 × 0.98 × 100 = 83.79%
        inputs = RTYInputs(step_fpys_pct=[Decimal("95"), Decimal("90"), Decimal("98")])
        assert calculate_rty(inputs).value == Decimal("83.79")

    def test_single_perfect_step(self):
        assert calculate_rty(RTYInputs(step_fpys_pct=[Decimal("100")])).value == Decimal("100.00")


class TestJobYield:
    def test_standard_mode_textbook(self):
        result = calculate_job_yield(JobYieldInputs(completed_quantity=100, quantity_scrapped=5))
        assert result.value == Decimal("95.00")

    def test_zero_completed_yields_zero(self):
        assert calculate_job_yield(JobYieldInputs(completed_quantity=0, quantity_scrapped=0)).value == Decimal("0")


class TestRecoveryRate:
    def test_standard_mode_textbook(self):
        # (10 + 5) / 20 = 75%
        inputs = RecoveryRateInputs(units_reworked=10, units_repaired=5, units_scrapped=5)
        assert calculate_recovery_rate(inputs).value == Decimal("75.00")

    def test_no_failures_yields_100(self):
        inputs = RecoveryRateInputs(units_reworked=0, units_repaired=0, units_scrapped=0)
        assert calculate_recovery_rate(inputs).value == Decimal("100")


class TestScrapRate:
    def test_standard_mode_textbook(self):
        result = calculate_scrap_rate(ScrapRateInputs(units_scrapped=5, total_produced=100))
        assert result.value == Decimal("5.00")

    def test_zero_total_yields_zero(self):
        assert calculate_scrap_rate(ScrapRateInputs(units_scrapped=0, total_produced=0)).value == Decimal("0")


class TestDefectEscapeRate:
    def test_standard_mode_textbook(self):
        result = calculate_defect_escape_rate(DefectEscapeRateInputs(final_stage_defects=2, total_defects=10))
        assert result.value == Decimal("20.00")

    def test_zero_defects_yields_zero(self):
        assert calculate_defect_escape_rate(
            DefectEscapeRateInputs(final_stage_defects=0, total_defects=0)
        ).value == Decimal("0")


class TestRepairAndReworkImpact:
    def test_rework_impact(self):
        result = calculate_rework_impact(ImpactInputs(affected_units=8, total_inspected=100))
        assert result.metric_name == "rework_impact"
        assert result.value == Decimal("8.00")

    def test_repair_impact(self):
        result = calculate_repair_impact(ImpactInputs(affected_units=3, total_inspected=100))
        assert result.metric_name == "repair_impact"
        assert result.value == Decimal("3.00")


class TestQualityScore:
    def test_standard_mode_textbook(self):
        # FPY 95 × .40 + RTY 90 × .30 + (100 - 2) × .20 + (100 - 5) × .10
        # = 38 + 27 + 19.6 + 9.5 = 94.1
        inputs = QualityScoreInputs(
            fpy_pct=Decimal("95"),
            rty_pct=Decimal("90"),
            scrap_rate_pct=Decimal("2"),
            defect_escape_rate_pct=Decimal("5"),
        )
        assert calculate_quality_score(inputs).value == Decimal("94.10")

    def test_perfect_quality(self):
        inputs = QualityScoreInputs(
            fpy_pct=Decimal("100"),
            rty_pct=Decimal("100"),
            scrap_rate_pct=Decimal("0"),
            defect_escape_rate_pct=Decimal("0"),
        )
        assert calculate_quality_score(inputs).value == Decimal("100.00")
