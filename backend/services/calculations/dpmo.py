"""
PPM, DPMO, and Sigma Level orchestrators.

Wraps pure helpers from backend.calculations.{ppm,dpmo}.

Phase 3 site assumption candidates:
  - dpmo_opportunities_default (Tier-1 candidate per audit Tier list — currently
    DEFAULT_OPPORTUNITIES_PER_UNIT = 10 but already overridable via ClientConfig)
"""

from decimal import Decimal

from pydantic import BaseModel, Field

from backend.calculations.dpmo import calculate_dpmo_pure, calculate_sigma_level_pure
from backend.calculations.ppm import calculate_ppm_pure
from backend.services.calculations.result import (
    CalculationMode,
    CalculationResult,
)


class PPMInputs(BaseModel):
    total_inspected: int = Field(ge=0)
    total_defects: int = Field(ge=0)


class DPMOInputs(BaseModel):
    total_defects: int = Field(ge=0)
    total_units: int = Field(ge=0)
    opportunities_per_unit: int = Field(gt=0)


class DPMOValue(BaseModel):
    dpmo: Decimal
    total_opportunities: int


class SigmaLevelInputs(BaseModel):
    dpmo: Decimal = Field(ge=Decimal("0"))


def calculate_ppm(
    inputs: PPMInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """PPM = (total_defects / total_inspected) × 1,000,000."""

    value = calculate_ppm_pure(inputs.total_inspected, inputs.total_defects)

    return CalculationResult[Decimal](
        metric_name="ppm",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_dpmo(
    inputs: DPMOInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[DPMOValue]:
    """DPMO = (total_defects / (total_units × opportunities_per_unit)) × 1,000,000."""

    dpmo, total_opps = calculate_dpmo_pure(
        total_defects=inputs.total_defects,
        total_units=inputs.total_units,
        opportunities_per_unit=inputs.opportunities_per_unit,
    )

    return CalculationResult[DPMOValue](
        metric_name="dpmo",
        value=DPMOValue(dpmo=dpmo, total_opportunities=total_opps),
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_sigma_level(
    inputs: SigmaLevelInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """Sigma Level — lookup from DPMO_TO_SIGMA table (industry-standard mapping)."""

    value = calculate_sigma_level_pure(inputs.dpmo)

    return CalculationResult[Decimal](
        metric_name="sigma_level",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )
