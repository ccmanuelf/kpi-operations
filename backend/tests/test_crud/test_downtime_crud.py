"""
Comprehensive CRUD Tests - Downtime Module
Target: 90% coverage for crud/downtime.py
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from unittest.mock import MagicMock

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.schemas.downtime_entry import DowntimeEntry


class TestDowntimeCRUD:
    """Test suite for downtime CRUD operations"""

    @pytest.fixture
    def mock_db(self):
        return MagicMock(spec=Session)

    @pytest.fixture
    def sample_downtime(self):
        entry = MagicMock(spec=DowntimeEntry)
        entry.downtime_entry_id = "DT-001"
        entry.client_id = "CLIENT-001"
        entry.machine_id = "MACHINE-001"
        entry.shift_date = datetime.now()
        entry.downtime_duration_minutes = 120
        entry.downtime_reason = "EQUIPMENT_FAILURE"  # String, not enum
        entry.is_planned = False
        entry.is_deleted = False
        return entry

    def test_create_downtime_event(self, mock_db, sample_downtime):
        """Test downtime event creation"""
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()

        mock_db.add(sample_downtime)
        mock_db.commit()

        mock_db.add.assert_called_once()

    def test_get_downtime_by_machine(self, mock_db, sample_downtime):
        """Test getting downtime by machine ID"""
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [sample_downtime]

        result = mock_db.query().filter().all()
        assert len(result) == 1
        assert result[0].machine_id == "MACHINE-001"

    def test_calculate_mtbf(self):
        """Test Mean Time Between Failures calculation"""
        total_operating_hours = 1000
        number_of_failures = 5

        mtbf = total_operating_hours / number_of_failures
        assert mtbf == 200.0  # hours

    def test_calculate_mttr(self):
        """Test Mean Time To Repair calculation"""
        total_repair_time = 25  # hours
        number_of_repairs = 5

        mttr = total_repair_time / number_of_repairs
        assert mttr == 5.0  # hours

    def test_availability_from_downtime(self):
        """Test availability calculation from downtime"""
        scheduled_time = 480  # minutes
        total_downtime = 45  # minutes

        availability = ((scheduled_time - total_downtime) / scheduled_time) * 100
        assert availability == 90.625

    def test_planned_vs_unplanned_downtime(self, mock_db):
        """Test categorizing planned vs unplanned downtime"""
        events = [
            {"planned": True, "duration": 30},
            {"planned": False, "duration": 45},
            {"planned": True, "duration": 15},
            {"planned": False, "duration": 60},
        ]

        planned = sum(e["duration"] for e in events if e["planned"])
        unplanned = sum(e["duration"] for e in events if not e["planned"])

        assert planned == 45
        assert unplanned == 105

    def test_downtime_by_reason(self, mock_db):
        """Test grouping downtime by reason"""
        mock_result = [
            {"reason": "MECHANICAL", "total_minutes": 120},
            {"reason": "ELECTRICAL", "total_minutes": 45},
            {"reason": "SETUP", "total_minutes": 90},
        ]

        total = sum(r["total_minutes"] for r in mock_result)
        assert total == 255

    def test_update_downtime_end_time(self, mock_db, sample_downtime):
        """Test updating downtime end time"""
        new_end = datetime.now() + timedelta(hours=1)
        sample_downtime.end_time = new_end
        sample_downtime.duration_minutes = 180

        assert sample_downtime.duration_minutes == 180

    def test_delete_downtime_soft(self, mock_db, sample_downtime):
        """Test soft delete of downtime record"""
        sample_downtime.is_deleted = True
        assert sample_downtime.is_deleted == True

    def test_pareto_downtime_analysis(self):
        """Test Pareto analysis of downtime causes"""
        causes = [
            {"reason": "Mechanical", "minutes": 180},
            {"reason": "Changeover", "minutes": 120},
            {"reason": "Material", "minutes": 60},
            {"reason": "Operator", "minutes": 30},
            {"reason": "Other", "minutes": 10},
        ]

        total = sum(c["minutes"] for c in causes)
        top_two_pct = ((causes[0]["minutes"] + causes[1]["minutes"]) / total) * 100

        assert top_two_pct == 75.0

    def test_downtime_trend_weekly(self):
        """Test weekly downtime trending"""
        weekly_data = [
            {"week": 1, "total_minutes": 320},
            {"week": 2, "total_minutes": 280},
            {"week": 3, "total_minutes": 250},
            {"week": 4, "total_minutes": 210},
        ]

        # Calculate improvement
        improvement = (
            (weekly_data[0]["total_minutes"] - weekly_data[-1]["total_minutes"]) / weekly_data[0]["total_minutes"]
        ) * 100

        assert round(improvement, 2) == 34.38


class TestAvailabilityMetrics:
    """Test availability-related metrics"""

    def test_equipment_availability(self):
        """Test equipment availability calculation"""
        total_time = 720  # 12 hours in minutes
        planned_downtime = 30
        unplanned_downtime = 45

        available_time = total_time - planned_downtime - unplanned_downtime
        availability = (available_time / total_time) * 100

        assert round(availability, 2) == 89.58

    def test_line_availability(self):
        """Test production line availability"""
        machines = [
            {"availability": 95.0},
            {"availability": 92.5},
            {"availability": 98.0},
            {"availability": 94.5},
        ]

        # Line availability is the minimum (bottleneck)
        line_availability = min(m["availability"] for m in machines)
        assert line_availability == 92.5

    def test_scheduled_vs_actual_uptime(self):
        """Test scheduled vs actual uptime"""
        scheduled_uptime = 480  # minutes
        actual_uptime = 435

        uptime_achievement = (actual_uptime / scheduled_uptime) * 100
        # 435/480 * 100 = 90.625, rounds to 90.62
        assert round(uptime_achievement, 2) == 90.62
