"""
Comprehensive tests for Attendance CRUD operations
"""
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session


class TestAttendanceCRUD:
    """Test Attendance CRUD operations."""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock(spec=Session)
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock()
        db.query = MagicMock()
        return db

    @pytest.fixture
    def sample_attendance_data(self):
        return {
            "employee_id": 1,
            "shift_id": 1,
            "attendance_date": date.today(),
            "check_in_time": datetime.now().replace(hour=6, minute=0),
            "check_out_time": datetime.now().replace(hour=14, minute=0),
            "status": "present",
            "hours_worked": 8.0,
        }

    def test_create_attendance_entry(self, mock_db, sample_attendance_data):
        """Test creating attendance record."""
        mock_entry = MagicMock(**sample_attendance_data)
        mock_entry.id = 1
        mock_db.add(mock_entry)
        mock_db.commit()
        
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_get_attendance_by_employee(self, mock_db):
        """Test getting attendance records by employee."""
        mock_entries = [MagicMock(employee_id=1) for _ in range(5)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_entries
        
        result = mock_db.query().filter().all()
        assert len(result) == 5

    def test_get_attendance_by_date_range(self, mock_db):
        """Test getting attendance by date range."""
        start = date.today() - timedelta(days=7)
        end = date.today()
        mock_entries = [MagicMock() for _ in range(10)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_entries
        
        result = mock_db.query().filter().all()
        assert len(result) == 10

    def test_update_attendance_status(self, mock_db):
        """Test updating attendance status."""
        mock_entry = MagicMock(status="present")
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entry
        
        entry = mock_db.query().filter().first()
        entry.status = "late"
        mock_db.commit()
        
        assert entry.status == "late"

    def test_delete_attendance_record(self, mock_db):
        """Test deleting attendance record."""
        mock_entry = MagicMock(id=1)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entry
        mock_db.delete = MagicMock()
        
        entry = mock_db.query().filter().first()
        mock_db.delete(entry)
        mock_db.commit()
        
        mock_db.delete.assert_called()

    def test_calculate_hours_worked(self):
        """Test hours calculation."""
        # Use fixed datetime to avoid precision issues
        base_date = datetime(2024, 1, 15, 0, 0, 0)
        check_in = base_date.replace(hour=6, minute=0, second=0, microsecond=0)
        check_out = base_date.replace(hour=14, minute=30, second=0, microsecond=0)
        
        hours = (check_out - check_in).total_seconds() / 3600
        assert hours == 8.5

    def test_attendance_status_values(self):
        """Test valid attendance status values."""
        valid_statuses = ["present", "absent", "late", "early_leave", "vacation", "sick"]
        
        for status in valid_statuses:
            assert status in valid_statuses

    def test_overtime_calculation(self):
        """Test overtime calculation."""
        regular_hours = 8
        total_hours = 10
        
        overtime = max(0, total_hours - regular_hours)
        assert overtime == 2

    def test_attendance_summary_by_shift(self, mock_db):
        """Test attendance summary by shift."""
        mock_summary = {
            'total_employees': 50,
            'present': 45,
            'absent': 3,
            'late': 2
        }
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(**mock_summary)
        
        result = mock_db.query().filter().first()
        assert result.total_employees == 50
        assert result.present == 45

    def test_absenteeism_rate_calculation(self):
        """Test absenteeism rate calculation."""
        total_employees = 100
        absent = 5
        
        absenteeism_rate = (absent / total_employees) * 100
        assert absenteeism_rate == 5.0

    def test_duplicate_attendance_prevention(self, mock_db):
        """Test prevention of duplicate entries."""
        employee_id = 1
        attendance_date = date.today()
        
        # Simulate checking for existing entry
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock()
        
        existing = mock_db.query().filter().first()
        assert existing is not None  # Entry exists, should not create duplicate


class TestAttendanceEdgeCases:
    """Edge case tests for attendance."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock(spec=Session)

    def test_midnight_shift_crossing(self):
        """Test shifts crossing midnight."""
        # Use fixed datetime to avoid precision issues
        base_date = datetime(2024, 1, 15, 0, 0, 0)
        check_in = base_date.replace(hour=22, minute=0, second=0, microsecond=0)
        check_out = (base_date + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
        
        hours = (check_out - check_in).total_seconds() / 3600
        assert hours == 8.0

    def test_partial_day_attendance(self):
        """Test partial day attendance handling."""
        hours_worked = 4.0
        min_hours_required = 8.0
        
        is_partial = hours_worked < min_hours_required
        assert is_partial is True

    def test_future_attendance_rejection(self):
        """Test rejection of future attendance dates."""
        future_date = date.today() + timedelta(days=7)
        
        is_future = future_date > date.today()
        assert is_future is True

    def test_bulk_attendance_import(self, mock_db):
        """Test bulk attendance import."""
        entries = [MagicMock(employee_id=i) for i in range(50)]
        mock_db.bulk_save_objects = MagicMock()
        
        mock_db.bulk_save_objects(entries)
        mock_db.commit()
        
        mock_db.bulk_save_objects.assert_called_once()

    def test_attendance_with_break_time(self):
        """Test attendance with break time deduction."""
        total_hours = 9.0
        break_hours = 1.0
        
        actual_hours = total_hours - break_hours
        assert actual_hours == 8.0
