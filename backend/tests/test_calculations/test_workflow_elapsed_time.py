"""
Tests for Workflow Elapsed Time Calculations
Phase 10.3: Workflow Foundation - Elapsed Time Calculations

Tests cover:
- calculate_elapsed_hours/days functions
- calculate_business_hours function
- WorkOrderElapsedTime class properties
- calculate_client_average_times function
- get_transition_elapsed_times function
- calculate_stage_duration_summary function
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch


class TestElapsedHoursCalculation:
    """Test suite for calculate_elapsed_hours function"""

    def test_calculate_elapsed_hours_basic(self):
        """Test basic elapsed hours calculation"""
        from backend.calculations.elapsed_time import calculate_elapsed_hours

        from_dt = datetime(2025, 1, 1, 10, 0, 0)
        to_dt = datetime(2025, 1, 1, 15, 0, 0)

        result = calculate_elapsed_hours(from_dt, to_dt)
        assert result == 5

    def test_calculate_elapsed_hours_across_days(self):
        """Test elapsed hours across multiple days"""
        from backend.calculations.elapsed_time import calculate_elapsed_hours

        from_dt = datetime(2025, 1, 1, 10, 0, 0)
        to_dt = datetime(2025, 1, 3, 10, 0, 0)  # 48 hours later

        result = calculate_elapsed_hours(from_dt, to_dt)
        assert result == 48

    def test_calculate_elapsed_hours_none_from(self):
        """Test returns None when from_datetime is None"""
        from backend.calculations.elapsed_time import calculate_elapsed_hours

        result = calculate_elapsed_hours(None, datetime.now())
        assert result is None

    def test_calculate_elapsed_hours_none_to_uses_now(self):
        """Test uses current time when to_datetime is None"""
        from backend.calculations.elapsed_time import calculate_elapsed_hours

        from_dt = datetime.utcnow() - timedelta(hours=2)
        result = calculate_elapsed_hours(from_dt, None)

        # Should be approximately 2 hours
        assert result == 2

    def test_calculate_elapsed_hours_partial_hours(self):
        """Test partial hours are truncated to integer"""
        from backend.calculations.elapsed_time import calculate_elapsed_hours

        from_dt = datetime(2025, 1, 1, 10, 0, 0)
        to_dt = datetime(2025, 1, 1, 12, 30, 0)  # 2.5 hours

        result = calculate_elapsed_hours(from_dt, to_dt)
        assert result == 2  # Truncated to integer


class TestElapsedDaysCalculation:
    """Test suite for calculate_elapsed_days function"""

    def test_calculate_elapsed_days_basic(self):
        """Test basic elapsed days calculation"""
        from backend.calculations.elapsed_time import calculate_elapsed_days

        from_dt = datetime(2025, 1, 1, 0, 0, 0)
        to_dt = datetime(2025, 1, 4, 0, 0, 0)  # 3 days

        result = calculate_elapsed_days(from_dt, to_dt)
        assert result == 3.0

    def test_calculate_elapsed_days_partial(self):
        """Test partial days with 2 decimal precision"""
        from backend.calculations.elapsed_time import calculate_elapsed_days

        from_dt = datetime(2025, 1, 1, 0, 0, 0)
        to_dt = datetime(2025, 1, 2, 12, 0, 0)  # 1.5 days

        result = calculate_elapsed_days(from_dt, to_dt)
        assert result == 1.5

    def test_calculate_elapsed_days_none_from(self):
        """Test returns None when from_datetime is None"""
        from backend.calculations.elapsed_time import calculate_elapsed_days

        result = calculate_elapsed_days(None, datetime.now())
        assert result is None

    def test_calculate_elapsed_days_none_to_uses_now(self):
        """Test uses current time when to_datetime is None"""
        from backend.calculations.elapsed_time import calculate_elapsed_days

        from_dt = datetime.utcnow() - timedelta(days=2)
        result = calculate_elapsed_days(from_dt, None)

        # Should be approximately 2 days
        assert result >= 1.99 and result <= 2.01


class TestBusinessHoursCalculation:
    """Test suite for calculate_business_hours function"""

    def test_business_hours_weekday_only(self):
        """Test business hours for weekday span"""
        from backend.calculations.elapsed_time import calculate_business_hours

        # Monday to Friday (5 days)
        from_dt = datetime(2025, 1, 6, 0, 0, 0)  # Monday
        to_dt = datetime(2025, 1, 10, 0, 0, 0)   # Friday

        result = calculate_business_hours(from_dt, to_dt, hours_per_day=8)
        assert result == 5 * 8  # 40 hours

    def test_business_hours_with_weekend(self):
        """Test business hours spanning weekend"""
        from backend.calculations.elapsed_time import calculate_business_hours

        # Monday to next Monday (8 days, 5 working)
        from_dt = datetime(2025, 1, 6, 0, 0, 0)  # Monday
        to_dt = datetime(2025, 1, 13, 0, 0, 0)   # Next Monday

        result = calculate_business_hours(from_dt, to_dt, hours_per_day=8)
        assert result == 6 * 8  # 6 working days (Mon-Fri + Mon)

    def test_business_hours_none_from(self):
        """Test returns None when from_datetime is None"""
        from backend.calculations.elapsed_time import calculate_business_hours

        result = calculate_business_hours(None, datetime.now())
        assert result is None

    def test_business_hours_custom_working_days(self):
        """Test with custom working days (Mon-Sat)"""
        from backend.calculations.elapsed_time import calculate_business_hours

        from_dt = datetime(2025, 1, 6, 0, 0, 0)  # Monday
        to_dt = datetime(2025, 1, 13, 0, 0, 0)   # Next Monday

        result = calculate_business_hours(
            from_dt, to_dt,
            hours_per_day=8,
            working_days=[0, 1, 2, 3, 4, 5]  # Mon-Sat
        )
        assert result == 7 * 8  # 7 working days


class TestWorkOrderElapsedTime:
    """Test suite for WorkOrderElapsedTime class"""

    def _create_mock_work_order(
        self,
        received_date=None,
        dispatch_date=None,
        closure_date=None,
        shipped_date=None,
        expected_date=None,
        status="IN_PROGRESS",
        actual_delivery_date=None,
        updated_at=None
    ):
        """Create a mock work order for testing"""
        wo = Mock()
        wo.work_order_id = "WO-TEST-001"
        wo.status = status
        wo.received_date = received_date
        wo.dispatch_date = dispatch_date
        wo.closure_date = closure_date
        wo.shipped_date = shipped_date
        wo.expected_date = expected_date
        wo.actual_delivery_date = actual_delivery_date
        wo.updated_at = updated_at or datetime.utcnow()
        return wo

    def test_total_lifecycle_hours_closed(self):
        """Test total lifecycle hours for closed work order"""
        from backend.calculations.elapsed_time import WorkOrderElapsedTime

        received = datetime(2025, 1, 1, 10, 0, 0)
        closed = datetime(2025, 1, 3, 10, 0, 0)  # 48 hours

        wo = self._create_mock_work_order(
            received_date=received,
            closure_date=closed
        )

        calc = WorkOrderElapsedTime(wo)
        assert calc.total_lifecycle_hours == 48

    def test_total_lifecycle_hours_open(self):
        """Test total lifecycle hours for open work order"""
        from backend.calculations.elapsed_time import WorkOrderElapsedTime

        received = datetime.utcnow() - timedelta(hours=24)

        wo = self._create_mock_work_order(received_date=received)
        calc = WorkOrderElapsedTime(wo)

        assert calc.total_lifecycle_hours == 24

    def test_lead_time_hours(self):
        """Test lead time (received → dispatch)"""
        from backend.calculations.elapsed_time import WorkOrderElapsedTime

        received = datetime(2025, 1, 1, 10, 0, 0)
        dispatch = datetime(2025, 1, 1, 14, 0, 0)  # 4 hours

        wo = self._create_mock_work_order(
            received_date=received,
            dispatch_date=dispatch
        )

        calc = WorkOrderElapsedTime(wo)
        assert calc.lead_time_hours == 4

    def test_processing_time_hours(self):
        """Test processing time (dispatch → closure)"""
        from backend.calculations.elapsed_time import WorkOrderElapsedTime

        dispatch = datetime(2025, 1, 1, 14, 0, 0)
        closed = datetime(2025, 1, 2, 14, 0, 0)  # 24 hours

        wo = self._create_mock_work_order(
            dispatch_date=dispatch,
            closure_date=closed
        )

        calc = WorkOrderElapsedTime(wo)
        assert calc.processing_time_hours == 24

    def test_is_overdue_true(self):
        """Test is_overdue when past expected date"""
        from backend.calculations.elapsed_time import WorkOrderElapsedTime

        expected = datetime.utcnow() - timedelta(days=1)  # Yesterday

        wo = self._create_mock_work_order(expected_date=expected)
        calc = WorkOrderElapsedTime(wo)

        assert calc.is_overdue is True

    def test_is_overdue_false_not_past(self):
        """Test is_overdue when not past expected date"""
        from backend.calculations.elapsed_time import WorkOrderElapsedTime

        expected = datetime.utcnow() + timedelta(days=1)  # Tomorrow

        wo = self._create_mock_work_order(expected_date=expected)
        calc = WorkOrderElapsedTime(wo)

        assert calc.is_overdue is False

    def test_is_overdue_false_closed(self):
        """Test closed orders aren't overdue"""
        from backend.calculations.elapsed_time import WorkOrderElapsedTime

        expected = datetime.utcnow() - timedelta(days=1)  # Yesterday
        closed = datetime.utcnow()

        wo = self._create_mock_work_order(
            expected_date=expected,
            closure_date=closed
        )
        calc = WorkOrderElapsedTime(wo)

        assert calc.is_overdue is False

    def test_is_overdue_false_no_expected(self):
        """Test no expected date means not overdue"""
        from backend.calculations.elapsed_time import WorkOrderElapsedTime

        wo = self._create_mock_work_order(expected_date=None)
        calc = WorkOrderElapsedTime(wo)

        assert calc.is_overdue is False

    def test_days_early_or_late_early(self):
        """Test days_early_or_late when early"""
        from backend.calculations.elapsed_time import WorkOrderElapsedTime

        expected = datetime.utcnow() + timedelta(days=3)

        wo = self._create_mock_work_order(expected_date=expected)
        calc = WorkOrderElapsedTime(wo)

        # Positive = early
        assert calc.days_early_or_late >= 2

    def test_days_early_or_late_late(self):
        """Test days_early_or_late when late"""
        from backend.calculations.elapsed_time import WorkOrderElapsedTime

        expected = datetime.utcnow() - timedelta(days=2)

        wo = self._create_mock_work_order(expected_date=expected)
        calc = WorkOrderElapsedTime(wo)

        # Negative = late
        assert calc.days_early_or_late <= -2

    def test_get_all_metrics(self):
        """Test get_all_metrics returns complete dictionary"""
        from backend.calculations.elapsed_time import WorkOrderElapsedTime

        received = datetime.utcnow() - timedelta(hours=48)
        dispatch = datetime.utcnow() - timedelta(hours=24)
        expected = datetime.utcnow() + timedelta(days=1)

        wo = self._create_mock_work_order(
            received_date=received,
            dispatch_date=dispatch,
            expected_date=expected
        )

        calc = WorkOrderElapsedTime(wo)
        metrics = calc.get_all_metrics()

        assert "work_order_id" in metrics
        assert "status" in metrics
        assert "lifecycle" in metrics
        assert "stages" in metrics
        assert "forecast" in metrics
        assert "dates" in metrics

        assert metrics["lifecycle"]["is_overdue"] is False
        assert metrics["lifecycle"]["total_hours"] >= 48


class TestCalculateWorkOrderElapsedTimes:
    """Test convenience function for getting all metrics"""

    def test_calculate_work_order_elapsed_times(self):
        """Test calculate_work_order_elapsed_times function"""
        from backend.calculations.elapsed_time import calculate_work_order_elapsed_times

        wo = Mock()
        wo.work_order_id = "WO-001"
        wo.status = "IN_PROGRESS"
        wo.received_date = datetime.utcnow() - timedelta(hours=24)
        wo.dispatch_date = datetime.utcnow() - timedelta(hours=12)
        wo.closure_date = None
        wo.shipped_date = None
        wo.expected_date = datetime.utcnow() + timedelta(days=2)
        wo.actual_delivery_date = None
        wo.updated_at = datetime.utcnow()

        result = calculate_work_order_elapsed_times(wo)

        assert result["work_order_id"] == "WO-001"
        assert "lifecycle" in result
        assert "stages" in result


class TestCalculateClientAverageTimes:
    """Test calculate_client_average_times function"""

    def test_client_average_times_empty(self):
        """Test with no work orders"""
        from backend.calculations.elapsed_time import calculate_client_average_times

        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []

        result = calculate_client_average_times(mock_db, "CLIENT-001")

        assert result["client_id"] == "CLIENT-001"
        assert result["count"] == 0
        assert result["averages"] is None

    def test_client_average_times_with_data(self):
        """Test with work orders"""
        from backend.calculations.elapsed_time import calculate_client_average_times

        # Create mock work orders
        wo1 = Mock()
        wo1.received_date = datetime.utcnow() - timedelta(hours=48)
        wo1.dispatch_date = datetime.utcnow() - timedelta(hours=40)
        wo1.closure_date = datetime.utcnow() - timedelta(hours=24)
        wo1.shipped_date = None
        wo1.expected_date = datetime.utcnow()
        wo1.actual_delivery_date = None
        wo1.updated_at = datetime.utcnow()

        wo2 = Mock()
        wo2.received_date = datetime.utcnow() - timedelta(hours=72)
        wo2.dispatch_date = datetime.utcnow() - timedelta(hours=60)
        wo2.closure_date = datetime.utcnow() - timedelta(hours=48)
        wo2.shipped_date = None
        wo2.expected_date = datetime.utcnow() - timedelta(days=1)  # Overdue
        wo2.actual_delivery_date = None
        wo2.updated_at = datetime.utcnow()

        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [wo1, wo2]

        result = calculate_client_average_times(mock_db, "CLIENT-001")

        assert result["client_id"] == "CLIENT-001"
        assert result["count"] == 2
        assert result["averages"] is not None
        assert "lifecycle_hours" in result["averages"]


class TestGetTransitionElapsedTimes:
    """Test get_transition_elapsed_times function"""

    def test_transition_elapsed_times(self):
        """Test getting elapsed times between transitions"""
        from backend.calculations.elapsed_time import get_transition_elapsed_times

        # Create mock transitions
        t1 = Mock()
        t1.transition_id = 1
        t1.from_status = None
        t1.to_status = "RECEIVED"
        t1.transitioned_at = datetime(2025, 1, 1, 10, 0, 0)
        t1.elapsed_from_received_hours = 0
        t1.trigger_source = "manual"
        t1.notes = "Initial"

        t2 = Mock()
        t2.transition_id = 2
        t2.from_status = "RECEIVED"
        t2.to_status = "RELEASED"
        t2.transitioned_at = datetime(2025, 1, 1, 14, 0, 0)  # 4 hours later
        t2.elapsed_from_received_hours = 4
        t2.trigger_source = "manual"
        t2.notes = None

        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = [t1, t2]

        result = get_transition_elapsed_times(mock_db, "WO-001", "CLIENT-001")

        assert len(result) == 2
        assert result[0]["from_status"] is None
        assert result[0]["to_status"] == "RECEIVED"
        assert result[1]["from_status"] == "RECEIVED"
        assert result[1]["to_status"] == "RELEASED"
        assert result[1]["elapsed_from_previous_hours"] == 4


class TestCalculateStageDurationSummary:
    """Test calculate_stage_duration_summary function"""

    def test_stage_duration_summary(self):
        """Test stage duration summary calculation"""
        from backend.calculations.elapsed_time import calculate_stage_duration_summary

        # Create mock query result
        mock_result = Mock()
        mock_result.from_status = "RECEIVED"
        mock_result.to_status = "RELEASED"
        mock_result.avg_hours = 4.5
        mock_result.min_hours = 2
        mock_result.max_hours = 8
        mock_result.count = 10

        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [mock_result]

        result = calculate_stage_duration_summary(mock_db, "CLIENT-001")

        assert result["client_id"] == "CLIENT-001"
        assert len(result["stage_durations"]) == 1
        assert result["stage_durations"][0]["from_status"] == "RECEIVED"
        assert result["stage_durations"][0]["to_status"] == "RELEASED"
        assert result["stage_durations"][0]["avg_hours"] == 4.5
        assert result["stage_durations"][0]["avg_days"] == 0.19  # 4.5/24 rounded
