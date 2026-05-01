"""
Quality orchestrators: FPY, RTY, Job Yield, Recovery Rate, Scrap Rate,
Defect Escape Rate, Quality Score, Rework Impact, Repair Impact.

Pure helpers in backend.calculations.fpy_rty back FPY/RTY/Job Yield/Recovery.
The remaining metrics are inline compositions.

Phase 3 site assumption candidates:
  - scrap_classification_rule (rework counted as good / partial / bad)
  - yield_baseline_source (theoretical / demonstrated / contractual — affects
    the target a quality_score is graded against; not the raw value)
"""

from decimal import Decimal

from pydantic import BaseModel, Field

from backend.calculations.fpy_rty import (
    calculate_fpy_pure,
    calculate_job_yield_pure,
    calculate_recovery_rate_pure,
    calculate_rty_pure,
)
from backend.services.calculations.result import (
    CalculationMode,
    CalculationResult,
)


class FPYInputs(BaseModel):
    total_passed: int = Field(ge=0)
    total_inspected: int = Field(ge=0)


class RTYInputs(BaseModel):
    step_fpys_pct: list[Decimal] = Field(min_length=1)


class JobYieldInputs(BaseModel):
    completed_quantity: int = Field(ge=0)
    quantity_scrapped: int = Field(ge=0)


class RecoveryRateInputs(BaseModel):
    units_reworked: int = Field(ge=0)
    units_repaired: int = Field(ge=0)
    units_scrapped: int = Field(ge=0)


class ScrapRateInputs(BaseModel):
    units_scrapped: int = Field(ge=0)
    total_produced: int = Field(ge=0)


class DefectEscapeRateInputs(BaseModel):
    final_stage_defects: int = Field(ge=0)
    total_defects: int = Field(ge=0)


class ImpactInputs(BaseModel):
    """Used by both rework_impact and repair_impact."""

    affected_units: int = Field(ge=0)
    total_inspected: int = Field(ge=0)


class QualityScoreInputs(BaseModel):
    fpy_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    rty_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    scrap_rate_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    defect_escape_rate_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))


def calculate_fpy(
    inputs: FPYInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """FPY % = total_passed / total_inspected × 100. total_passed must already exclude rework + repair."""

    value = calculate_fpy_pure(inputs.total_passed, inputs.total_inspected)

    return CalculationResult[Decimal](
        metric_name="fpy",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_rty(
    inputs: RTYInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """RTY % = ∏(FPY_step / 100) × 100."""

    value = calculate_rty_pure(inputs.step_fpys_pct)

    return CalculationResult[Decimal](
        metric_name="rty",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_job_yield(
    inputs: JobYieldInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Job Yield % = (completed - scrapped) / completed × 100."""

    value = calculate_job_yield_pure(inputs.completed_quantity, inputs.quantity_scrapped)

    return CalculationResult[Decimal](
        metric_name="job_yield",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_recovery_rate(
    inputs: RecoveryRateInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Recovery Rate % = (rework + repair) / (rework + repair + scrap) × 100. 100% if nothing failed."""

    value = calculate_recovery_rate_pure(
        units_reworked=inputs.units_reworked,
        units_repaired=inputs.units_repaired,
        units_scrapped=inputs.units_scrapped,
    )

    return CalculationResult[Decimal](
        metric_name="recovery_rate",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_scrap_rate(
    inputs: ScrapRateInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Scrap Rate % = units_scrapped / total_produced × 100."""

    if inputs.total_produced == 0:
        value = Decimal("0")
    else:
        value = (
            Decimal(str(inputs.units_scrapped))
            / Decimal(str(inputs.total_produced))
            * Decimal("100")
        ).quantize(Decimal("0.01"))

    return CalculationResult[Decimal](
        metric_name="scrap_rate",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_defect_escape_rate(
    inputs: DefectEscapeRateInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Defect Escape Rate % = final_stage_defects / total_defects × 100."""

    if inputs.total_defects == 0:
        value = Decimal("0")
    else:
        value = (
            Decimal(str(inputs.final_stage_defects))
            / Decimal(str(inputs.total_defects))
            * Decimal("100")
        ).quantize(Decimal("0.01"))

    return CalculationResult[Decimal](
        metric_name="defect_escape_rate",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_rework_impact(
    inputs: ImpactInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Rework Impact % = units_reworked / total_inspected × 100."""

    if inputs.total_inspected == 0:
        value = Decimal("0")
    else:
        value = (
            Decimal(str(inputs.affected_units))
            / Decimal(str(inputs.total_inspected))
            * Decimal("100")
        ).quantize(Decimal("0.01"))

    return CalculationResult[Decimal](
        metric_name="rework_impact",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_repair_impact(
    inputs: ImpactInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Repair Impact % = units_repaired / total_inspected × 100."""

    if inputs.total_inspected == 0:
        value = Decimal("0")
    else:
        value = (
            Decimal(str(inputs.affected_units))
            / Decimal(str(inputs.total_inspected))
            * Decimal("100")
        ).quantize(Decimal("0.01"))

    return CalculationResult[Decimal](
        metric_name="repair_impact",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_quality_score(
    inputs: QualityScoreInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """
    Quality Score (0–100) = weighted FPY (40%) + RTY (30%) + scrap_score (20%) + escape_score (10%).

    scrap_score = 100 - scrap_rate; escape_score = 100 - defect_escape_rate.
    """

    scrap_score = max(Decimal("0"), Decimal("100") - inputs.scrap_rate_pct)
    escape_score = max(Decimal("0"), Decimal("100") - inputs.defect_escape_rate_pct)

    score = (
        inputs.fpy_pct * Decimal("0.40")
        + inputs.rty_pct * Decimal("0.30")
        + scrap_score * Decimal("0.20")
        + escape_score * Decimal("0.10")
    )

    return CalculationResult[Decimal](
        metric_name="quality_score",
        value=score.quantize(Decimal("0.01")),
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )
