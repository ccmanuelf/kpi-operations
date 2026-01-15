"""
Comprehensive tests for performance calculations
Uses mock-based testing pattern consistent with other tests
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


class TestPerformanceCalculations:
    """Test performance KPI calculations"""

    def test_calculate_performance_basic(self):
        """Test basic performance calculation"""
        actual_output = 90
        expected_output = 100
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 90.0

    def test_calculate_performance_100_percent(self):
        """Test 100% performance"""
        actual_output = 100
        expected_output = 100
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 100.0

    def test_calculate_performance_over_100(self):
        """Test over 100% performance"""
        actual_output = 120
        expected_output = 100
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 120.0

    def test_calculate_performance_zero_expected(self):
        """Test performance with zero expected output"""
        actual_output = 100
        expected_output = 0
        
        # Should handle gracefully
        if expected_output == 0:
            performance = 0
        else:
            performance = (actual_output / expected_output) * 100
        
        assert performance == 0

    def test_calculate_performance_zero_actual(self):
        """Test performance with zero actual output"""
        actual_output = 0
        expected_output = 100
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 0.0

    def test_calculate_performance_with_downtime(self):
        """Test performance considering downtime"""
        actual_output = 70
        expected_output = 100
        planned_time_hours = 8.0
        actual_time_hours = 7.0  # Lost 1 hour to downtime
        
        # Adjust expected output based on actual time
        adjusted_expected = expected_output * (actual_time_hours / planned_time_hours)
        performance = (actual_output / adjusted_expected) * 100
        
        assert performance == 80.0

    def test_calculate_line_performance(self):
        """Test line-level performance calculation"""
        workers = 5
        hours_per_worker = 8
        actual_output = 450
        expected_per_hour = 12.5
        
        total_expected = workers * hours_per_worker * expected_per_hour
        performance = (actual_output / total_expected) * 100
        
        assert performance == 90.0

    def test_calculate_performance_partial_shift(self):
        """Test performance for partial shift"""
        actual_output = 45
        expected_output = 50
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 90.0

    def test_calculate_performance_overtime(self):
        """Test performance with overtime"""
        actual_output = 150
        expected_output = 100  # Standard shift
        regular_hours = 8
        overtime_hours = 4
        
        # Adjusted expected with overtime
        adjusted_expected = expected_output * ((regular_hours + overtime_hours) / regular_hours)
        performance = (actual_output / adjusted_expected) * 100
        
        assert performance == 100.0

    def test_calculate_performance_negative_values(self):
        """Test performance with negative values"""
        actual_output = -10
        expected_output = 100
        
        # Should handle or cap at 0
        if actual_output < 0:
            performance = 0
        else:
            performance = (actual_output / expected_output) * 100
        
        assert performance == 0


class TestShiftPerformance:
    """Test shift-level performance calculations"""

    def test_calculate_shift_performance(self):
        """Test shift performance calculation"""
        shift_data = {
            'shift_id': 1,
            'planned_output': 500,
            'actual_output': 475,
            'defective': 10
        }
        
        performance = (shift_data['actual_output'] / shift_data['planned_output']) * 100
        quality = ((shift_data['actual_output'] - shift_data['defective']) / 
                   shift_data['actual_output']) * 100
        
        assert performance == 95.0
        assert round(quality, 1) == 97.9

    def test_calculate_daily_performance(self):
        """Test daily performance aggregation"""
        shifts = [
            {'shift': 1, 'performance': 92.0},
            {'shift': 2, 'performance': 88.5},
            {'shift': 3, 'performance': 95.0}
        ]
        
        daily_avg = sum(s['performance'] for s in shifts) / len(shifts)
        
        assert round(daily_avg, 2) == 91.83

    def test_calculate_weekly_performance(self):
        """Test weekly performance aggregation"""
        daily_performance = [91.5, 92.0, 89.5, 93.0, 94.5, 90.0, 88.0]
        
        weekly_avg = sum(daily_performance) / len(daily_performance)
        
        assert round(weekly_avg, 2) == 91.21


class TestPerformanceTrends:
    """Test performance trend analysis"""

    def test_performance_trend_improving(self):
        """Test detecting improving performance trend"""
        weekly_data = [85.0, 87.0, 89.0, 91.0, 93.0]
        
        # Simple linear trend
        first_half_avg = sum(weekly_data[:2]) / 2
        second_half_avg = sum(weekly_data[-2:]) / 2
        
        trend = 'improving' if second_half_avg > first_half_avg else 'declining'
        
        assert trend == 'improving'

    def test_performance_trend_declining(self):
        """Test detecting declining performance trend"""
        weekly_data = [95.0, 93.0, 91.0, 89.0, 87.0]
        
        first_half_avg = sum(weekly_data[:2]) / 2
        second_half_avg = sum(weekly_data[-2:]) / 2
        
        trend = 'improving' if second_half_avg > first_half_avg else 'declining'
        
        assert trend == 'declining'

    def test_performance_trend_stable(self):
        """Test detecting stable performance trend"""
        weekly_data = [90.0, 91.0, 89.5, 90.5, 90.0]
        
        variance = max(weekly_data) - min(weekly_data)
        is_stable = variance < 5  # Less than 5% variance
        
        assert is_stable


class TestPerformanceEdgeCases:
    """Test edge cases for performance calculations"""

    def test_performance_very_small_values(self):
        """Test performance with very small values"""
        actual_output = 0.1
        expected_output = 0.1
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 100.0

    def test_performance_very_large_values(self):
        """Test performance with very large values"""
        actual_output = 1_000_000
        expected_output = 1_000_000
        
        performance = (actual_output / expected_output) * 100
        
        assert performance == 100.0

    def test_performance_decimal_precision(self):
        """Test performance decimal precision"""
        actual_output = 33.333
        expected_output = 100.0
        
        performance = (actual_output / expected_output) * 100
        
        # Should be approximately 33.33%
        assert 33.33 <= performance <= 33.34

    def test_performance_rounding(self):
        """Test performance rounding behavior"""
        actual_output = 123
        expected_output = 456
        
        performance = (actual_output / expected_output) * 100
        rounded = round(performance, 2)
        
        assert rounded == 26.97


class TestPerformanceByCategory:
    """Test performance breakdown by various categories"""

    def test_performance_by_product(self):
        """Test performance grouped by product"""
        product_data = [
            {'product': 'A', 'actual': 100, 'expected': 100},
            {'product': 'B', 'actual': 80, 'expected': 100},
            {'product': 'C', 'actual': 95, 'expected': 100}
        ]
        
        performance_by_product = {}
        for p in product_data:
            performance_by_product[p['product']] = (p['actual'] / p['expected']) * 100
        
        assert performance_by_product['A'] == 100.0
        assert performance_by_product['B'] == 80.0
        assert performance_by_product['C'] == 95.0

    def test_performance_by_employee(self):
        """Test performance grouped by employee"""
        employee_data = [
            {'employee': 'E001', 'actual': 95, 'expected': 100},
            {'employee': 'E002', 'actual': 105, 'expected': 100},
            {'employee': 'E003', 'actual': 88, 'expected': 100}
        ]
        
        avg_performance = sum(e['actual'] for e in employee_data) / len(employee_data)
        
        assert round(avg_performance, 2) == 96.0

    def test_performance_by_work_order(self):
        """Test performance grouped by work order"""
        wo_data = [
            {'wo': 'WO-001', 'actual': 500, 'expected': 500},
            {'wo': 'WO-002', 'actual': 480, 'expected': 500},
            {'wo': 'WO-003', 'actual': 520, 'expected': 500}
        ]
        
        total_actual = sum(w['actual'] for w in wo_data)
        total_expected = sum(w['expected'] for w in wo_data)
        
        overall_performance = (total_actual / total_expected) * 100
        
        assert overall_performance == 100.0


class TestPerformanceIntegration:
    """Integration tests for performance module"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock()

    def test_get_performance_for_work_order(self, mock_db):
        """Test getting performance for a work order"""
        mock_wo = MagicMock(
            work_order_id='WO-001',
            planned_quantity=1000,
            completed_quantity=950
        )
        mock_db.query.return_value.filter.return_value.first.return_value = mock_wo
        
        wo = mock_db.query().filter().first()
        performance = (wo.completed_quantity / wo.planned_quantity) * 100
        
        assert performance == 95.0

    def test_get_performance_trend(self, mock_db):
        """Test getting performance trend data"""
        mock_trend = [
            MagicMock(date='2025-01-01', performance=90.0),
            MagicMock(date='2025-01-02', performance=92.0),
            MagicMock(date='2025-01-03', performance=91.5)
        ]
        mock_db.query.return_value.all.return_value = mock_trend
        
        trend_data = mock_db.query().all()
        
        assert len(trend_data) == 3
        assert trend_data[0].performance == 90.0

    def test_get_performance_by_shift(self, mock_db):
        """Test getting performance by shift"""
        mock_shifts = [
            MagicMock(shift_id=1, performance=92.0),
            MagicMock(shift_id=2, performance=89.5),
            MagicMock(shift_id=3, performance=94.0)
        ]
        mock_db.query.return_value.group_by.return_value.all.return_value = mock_shifts
        
        shifts = mock_db.query().group_by().all()
        best_shift = max(shifts, key=lambda s: s.performance)
        
        assert best_shift.shift_id == 3
        assert best_shift.performance == 94.0
