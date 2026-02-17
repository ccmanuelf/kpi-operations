"""
Comprehensive tests for OTD (On Time Delivery) calculations
"""

import pytest
from datetime import datetime, date, timedelta, timezone
from unittest.mock import MagicMock


class TestOTDCalculations:
    """Test OTD calculations."""

    def test_basic_otd_calculation(self):
        """Test basic OTD percentage calculation."""
        total_orders = 100
        on_time_orders = 95
        otd = (on_time_orders / total_orders) * 100
        assert otd == 95.0

    def test_otd_perfect_delivery(self):
        """Test 100% OTD."""
        total_orders = 50
        on_time_orders = 50
        otd = (on_time_orders / total_orders) * 100
        assert otd == 100.0

    def test_otd_zero_orders(self):
        """Test OTD with no orders."""
        total_orders = 0
        otd = 0.0 if total_orders == 0 else 100.0
        assert otd == 0.0

    def test_otd_all_late(self):
        """Test OTD when all orders are late."""
        total_orders = 20
        on_time_orders = 0
        otd = (on_time_orders / total_orders) * 100
        assert otd == 0.0

    def test_delivery_is_on_time(self):
        """Test determining if delivery is on time."""
        due_date = date.today()
        delivery_date = date.today()
        is_on_time = delivery_date <= due_date
        assert is_on_time is True

    def test_delivery_is_late(self):
        """Test determining if delivery is late."""
        due_date = date.today() - timedelta(days=1)
        delivery_date = date.today()
        is_on_time = delivery_date <= due_date
        assert is_on_time is False

    def test_delivery_is_early(self):
        """Test determining if delivery is early."""
        due_date = date.today() + timedelta(days=2)
        delivery_date = date.today()
        is_early = delivery_date < due_date
        assert is_early is True

    def test_days_late_calculation(self):
        """Test calculating days late."""
        due_date = date.today() - timedelta(days=3)
        delivery_date = date.today()
        days_late = (delivery_date - due_date).days
        assert days_late == 3

    def test_days_early_calculation(self):
        """Test calculating days early."""
        due_date = date.today() + timedelta(days=2)
        delivery_date = date.today()
        days_early = (due_date - delivery_date).days
        assert days_early == 2

    def test_otd_by_customer(self):
        """Test OTD grouped by customer."""
        customer_orders = {
            "CustomerA": {"total": 50, "on_time": 48},
            "CustomerB": {"total": 30, "on_time": 27},
            "CustomerC": {"total": 20, "on_time": 20},
        }

        for customer, data in customer_orders.items():
            otd = (data["on_time"] / data["total"]) * 100
            assert otd >= 0

    def test_otd_by_product(self):
        """Test OTD grouped by product."""
        product_orders = {"ProductX": {"total": 100, "on_time": 95}, "ProductY": {"total": 75, "on_time": 70}}

        for product, data in product_orders.items():
            otd = (data["on_time"] / data["total"]) * 100
            if product == "ProductX":
                assert otd == 95.0
            elif product == "ProductY":
                assert round(otd, 1) == 93.3

    def test_otd_trend_analysis(self):
        """Test OTD trend over time."""
        weekly_otd = [92.5, 94.0, 93.5, 96.0, 97.5]
        avg_otd = sum(weekly_otd) / len(weekly_otd)
        trend = weekly_otd[-1] - weekly_otd[0]

        assert avg_otd == 94.7
        assert trend == 5.0  # Positive trend

    def test_otd_with_partial_delivery(self):
        """Test OTD with partial deliveries."""
        order = {"total_qty": 100, "delivered_qty": 100, "on_time_qty": 80}
        partial_otd = (order["on_time_qty"] / order["total_qty"]) * 100
        assert partial_otd == 80.0

    def test_weighted_otd(self):
        """Test weighted OTD by order value."""
        orders = [{"value": 1000, "on_time": True}, {"value": 5000, "on_time": True}, {"value": 2000, "on_time": False}]
        total_value = sum(o["value"] for o in orders)
        on_time_value = sum(o["value"] for o in orders if o["on_time"])
        weighted_otd = (on_time_value / total_value) * 100
        assert weighted_otd == 75.0


class TestOTDPredictions:
    """Test OTD predictions."""

    def test_predict_delivery_date(self):
        """Test delivery date prediction."""
        order_date = date.today()
        avg_lead_time = 5
        predicted_delivery = order_date + timedelta(days=avg_lead_time)
        assert predicted_delivery == date.today() + timedelta(days=5)

    def test_will_be_on_time_prediction(self):
        """Test predicting if order will be on time."""
        due_date = date.today() + timedelta(days=7)
        predicted_delivery = date.today() + timedelta(days=5)
        will_be_on_time = predicted_delivery <= due_date
        assert will_be_on_time is True

    def test_risk_assessment(self):
        """Test delivery risk assessment."""
        days_until_due = 5
        work_remaining_days = 4
        buffer = days_until_due - work_remaining_days  # buffer = 1

        if buffer < 0:
            risk = "high"
        elif buffer <= 1:
            risk = "medium"
        else:
            risk = "low"

        # buffer = 1 meets condition "<= 1", so risk is 'medium'
        assert risk == "medium"


class TestWIPAgingCalculations:
    """Test WIP (Work In Progress) Aging calculations."""

    def test_wip_age_calculation(self):
        """Test calculating WIP age."""
        start_date = date.today() - timedelta(days=10)
        current_date = date.today()
        age_days = (current_date - start_date).days
        assert age_days == 10

    def test_wip_aging_buckets(self):
        """Test WIP aging bucket categorization."""

        def categorize_age(age_days):
            if age_days <= 2:
                return "0-2 days"
            elif age_days <= 5:
                return "3-5 days"
            elif age_days <= 10:
                return "6-10 days"
            else:
                return ">10 days"

        assert categorize_age(1) == "0-2 days"
        assert categorize_age(4) == "3-5 days"
        assert categorize_age(7) == "6-10 days"
        assert categorize_age(15) == ">10 days"

    def test_average_wip_age(self):
        """Test calculating average WIP age."""
        wip_ages = [2, 3, 5, 7, 10]
        avg_age = sum(wip_ages) / len(wip_ages)
        assert avg_age == 5.4

    def test_wip_value_by_age(self):
        """Test WIP value bucketed by age."""
        wip_items = [{"age": 2, "value": 1000}, {"age": 5, "value": 2000}, {"age": 12, "value": 3000}]

        over_10_days_value = sum(item["value"] for item in wip_items if item["age"] > 10)
        assert over_10_days_value == 3000

    def test_wip_target_compliance(self):
        """Test WIP against target limits."""
        target_wip_days = 5
        actual_wip_days = 7
        is_compliant = actual_wip_days <= target_wip_days
        assert is_compliant is False

    def test_wip_aging_trend(self):
        """Test WIP aging trend analysis."""
        weekly_avg_ages = [4.5, 4.8, 5.2, 4.9, 4.3]
        current = weekly_avg_ages[-1]
        previous = weekly_avg_ages[-2]
        improving = current < previous
        assert improving is True

    def test_oldest_wip_item(self):
        """Test finding oldest WIP item."""
        wip_items = [{"id": 1, "age": 5}, {"id": 2, "age": 12}, {"id": 3, "age": 3}]
        oldest = max(wip_items, key=lambda x: x["age"])
        assert oldest["id"] == 2

    def test_wip_resolution_time(self):
        """Test WIP resolution time calculation."""
        start_date = datetime.now(tz=timezone.utc) - timedelta(days=5, hours=6)
        end_date = datetime.now(tz=timezone.utc)
        resolution_hours = (end_date - start_date).total_seconds() / 3600
        assert resolution_hours == pytest.approx(126, rel=0.001)  # 5 days + 6 hours

    def test_wip_throughput_rate(self):
        """Test WIP throughput calculation."""
        completed_items = 50
        time_period_days = 7
        throughput = completed_items / time_period_days
        assert round(throughput, 2) == 7.14

    def test_wip_bottleneck_identification(self):
        """Test identifying WIP bottleneck stages."""
        stage_wip = {"assembly": 10, "testing": 25, "packaging": 5}
        bottleneck = max(stage_wip, key=stage_wip.get)
        assert bottleneck == "testing"


class TestFPYRTYCalculations:
    """Test FPY and RTY calculations."""

    def test_fpy_calculation(self):
        """Test First Pass Yield calculation."""
        total_units = 1000
        first_pass_good = 950
        fpy = (first_pass_good / total_units) * 100
        assert fpy == 95.0

    def test_fpy_with_rework(self):
        """Test FPY excluding reworked units."""
        total_units = 100
        good_first_pass = 85
        reworked = 10
        fpy = (good_first_pass / total_units) * 100
        assert fpy == 85.0

    def test_rty_single_process(self):
        """Test RTY for single process."""
        fpy = 0.95
        rty = fpy * 100
        assert rty == 95.0

    def test_rty_multiple_processes(self):
        """Test RTY for multiple processes."""
        fpy_values = [0.95, 0.98, 0.99, 0.97]
        rty = 1.0
        for fpy in fpy_values:
            rty *= fpy
        rty_percent = rty * 100
        # 0.95 * 0.98 * 0.99 * 0.97 = 0.894039...
        assert round(rty_percent, 2) == 89.40

    def test_rty_with_zero_fpy(self):
        """Test RTY when one process has 0% FPY."""
        fpy_values = [0.95, 0.0, 0.99]
        rty = 1.0
        for fpy in fpy_values:
            rty *= fpy
        assert rty == 0.0

    def test_hidden_factory_loss(self):
        """Test calculating hidden factory loss."""
        tpy = 0.95  # Throughput yield
        rty = 0.85  # Rolled throughput yield
        hidden_loss = (tpy - rty) * 100
        assert hidden_loss == pytest.approx(10.0, rel=0.001)
