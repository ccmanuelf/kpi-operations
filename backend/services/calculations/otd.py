"""
On-Time Delivery (OTD) orchestrators.

Phase 3 site assumption candidates:
  - otd_carrier_buffer_pct (site-configured percentage buffer added to the
    planned delivery date before judging "on time")
"""

from decimal import Decimal

from pydantic import BaseModel, Field

from backend.services.calculations.result import (
    CalculationMode,
    CalculationResult,
)


class OTDInputs(BaseModel):
    """Pre-aggregated counts. on_time_orders ≤ total_orders."""

    on_time_orders: int = Field(ge=0)
    total_orders: int = Field(ge=0)


class DeliveryVarianceInputs(BaseModel):
    """Per-order delivery variance counts.

    Sum of the three buckets need not equal total_orders if some
    orders have no actual_delivery_date yet.
    """

    early_orders: int = Field(ge=0)
    on_time_orders: int = Field(ge=0)
    late_orders: int = Field(ge=0)
    total_variance_days: int = 0


class DeliveryVarianceValue(BaseModel):
    early_pct: Decimal
    on_time_pct: Decimal
    late_pct: Decimal
    average_variance_days: Decimal


def calculate_otd(
    inputs: OTDInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[Decimal]:
    """OTD % = on_time_orders / total_orders × 100."""

    if inputs.total_orders == 0:
        value = Decimal("0")
    else:
        if inputs.on_time_orders > inputs.total_orders:
            raise ValueError("on_time_orders cannot exceed total_orders")
        value = (Decimal(str(inputs.on_time_orders)) / Decimal(str(inputs.total_orders)) * Decimal("100")).quantize(
            Decimal("0.01")
        )

    return CalculationResult[Decimal](
        metric_name="otd",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )


def calculate_delivery_variance(
    inputs: DeliveryVarianceInputs,
    mode: CalculationMode = "standard",
) -> CalculationResult[DeliveryVarianceValue]:
    """Breakdown of orders into early / on-time / late buckets and average variance days."""

    total = inputs.early_orders + inputs.on_time_orders + inputs.late_orders

    if total == 0:
        zero = Decimal("0")
        value = DeliveryVarianceValue(early_pct=zero, on_time_pct=zero, late_pct=zero, average_variance_days=zero)
    else:
        total_dec = Decimal(str(total))
        value = DeliveryVarianceValue(
            early_pct=(Decimal(str(inputs.early_orders)) / total_dec * Decimal("100")).quantize(Decimal("0.01")),
            on_time_pct=(Decimal(str(inputs.on_time_orders)) / total_dec * Decimal("100")).quantize(Decimal("0.01")),
            late_pct=(Decimal(str(inputs.late_orders)) / total_dec * Decimal("100")).quantize(Decimal("0.01")),
            average_variance_days=(Decimal(str(inputs.total_variance_days)) / total_dec).quantize(Decimal("0.01")),
        )

    return CalculationResult[DeliveryVarianceValue](
        metric_name="delivery_variance",
        value=value,
        mode=mode,
        inputs_consumed=inputs.model_dump(mode="json"),
        assumptions_applied=[],
    )
