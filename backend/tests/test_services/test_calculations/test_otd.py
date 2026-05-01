"""Phase 1 dual-view orchestrators: OTD, Delivery Variance."""

from decimal import Decimal

import pytest

from backend.services.calculations.otd import (
    DeliveryVarianceInputs,
    OTDInputs,
    calculate_delivery_variance,
    calculate_otd,
)


class TestOTD:
    def test_standard_mode_textbook(self):
        result = calculate_otd(OTDInputs(on_time_orders=85, total_orders=100))
        assert result.metric_name == "otd"
        assert result.value == Decimal("85.00")

    def test_zero_total_yields_zero(self):
        assert calculate_otd(OTDInputs(on_time_orders=0, total_orders=0)).value == Decimal("0")

    def test_on_time_exceeds_total_raises(self):
        with pytest.raises(ValueError, match="on_time_orders cannot exceed total_orders"):
            calculate_otd(OTDInputs(on_time_orders=110, total_orders=100))

    def test_site_adjusted_equals_standard_in_phase_1(self):
        inputs = OTDInputs(on_time_orders=85, total_orders=100)
        assert calculate_otd(inputs, "standard").value == calculate_otd(inputs, "site_adjusted").value


class TestDeliveryVariance:
    def test_standard_mode_textbook(self):
        inputs = DeliveryVarianceInputs(
            early_orders=20,
            on_time_orders=70,
            late_orders=10,
            total_variance_days=-30,  # net 30 days late
        )
        result = calculate_delivery_variance(inputs)
        assert result.value.early_pct == Decimal("20.00")
        assert result.value.on_time_pct == Decimal("70.00")
        assert result.value.late_pct == Decimal("10.00")
        assert result.value.average_variance_days == Decimal("-0.30")

    def test_empty_returns_zeros(self):
        inputs = DeliveryVarianceInputs(early_orders=0, on_time_orders=0, late_orders=0)
        result = calculate_delivery_variance(inputs)
        assert result.value.early_pct == Decimal("0")
        assert result.value.on_time_pct == Decimal("0")
        assert result.value.late_pct == Decimal("0")
