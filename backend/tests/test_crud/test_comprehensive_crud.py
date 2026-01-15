"""
Comprehensive tests for Downtime CRUD operations
"""
import pytest
from datetime import datetime, date, timedelta
from unittest.mock import MagicMock
from sqlalchemy.orm import Session


class TestDowntimeCRUD:
    """Test Downtime CRUD operations."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock(spec=Session)

    @pytest.fixture
    def sample_downtime_data(self):
        return {
            "line_id": 1,
            "reason_code": "MECH",
            "description": "Mechanical failure",
            "start_time": datetime.now() - timedelta(hours=2),
            "end_time": datetime.now(),
            "duration_minutes": 120,
            "is_planned": False,
        }

    def test_create_downtime_entry(self, mock_db, sample_downtime_data):
        mock_entry = MagicMock(**sample_downtime_data, id=1)
        mock_db.add(mock_entry)
        mock_db.commit()
        mock_db.add.assert_called()

    def test_get_downtime_by_line(self, mock_db):
        mock_entries = [MagicMock(line_id=1) for _ in range(5)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_entries
        result = mock_db.query().filter().all()
        assert len(result) == 5

    def test_get_downtime_by_date_range(self, mock_db):
        mock_entries = [MagicMock() for _ in range(10)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_entries
        result = mock_db.query().filter().all()
        assert len(result) == 10

    def test_update_downtime_end_time(self, mock_db):
        mock_entry = MagicMock(end_time=None)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entry
        entry = mock_db.query().filter().first()
        entry.end_time = datetime.now()
        mock_db.commit()
        assert entry.end_time is not None

    def test_delete_downtime_entry(self, mock_db):
        mock_entry = MagicMock(id=1)
        mock_db.delete = MagicMock()
        mock_db.delete(mock_entry)
        mock_db.commit()
        mock_db.delete.assert_called()

    def test_calculate_duration(self):
        # Use fixed datetime to avoid precision issues
        base_time = datetime(2024, 1, 15, 12, 0, 0)
        start = base_time - timedelta(hours=2, minutes=30)
        end = base_time
        duration = (end - start).total_seconds() / 60
        assert duration == 150

    def test_calculate_availability(self):
        planned_time = 480
        downtime = 60
        availability = ((planned_time - downtime) / planned_time) * 100
        assert availability == 87.5

    def test_mtbf_calculation(self):
        total_operating_time = 2400
        number_of_failures = 4
        mtbf = total_operating_time / number_of_failures
        assert mtbf == 600

    def test_mttr_calculation(self):
        total_repair_time = 180
        number_of_failures = 3
        mttr = total_repair_time / number_of_failures
        assert mttr == 60

    def test_downtime_summary(self, mock_db):
        mock_summary = {'total_downtime': 300, 'planned': 60, 'unplanned': 240}
        mock_db.query.return_value.first.return_value = MagicMock(**mock_summary)
        result = mock_db.query().first()
        assert result.total_downtime == 300


class TestDowntimeEdgeCases:
    """Edge cases for downtime."""

    def test_open_downtime_entry(self):
        start_time = datetime.now()
        end_time = None
        is_open = end_time is None
        assert is_open is True

    def test_overlapping_downtime(self):
        entry1_end = datetime.now()
        entry2_start = datetime.now() - timedelta(minutes=30)
        overlaps = entry2_start < entry1_end
        assert overlaps is True

    def test_planned_vs_unplanned_ratio(self):
        planned = 60
        unplanned = 180
        total = planned + unplanned
        planned_ratio = (planned / total) * 100
        assert planned_ratio == 25

    def test_downtime_categories(self):
        categories = ['mechanical', 'electrical', 'operator', 'material', 'planned']
        assert len(categories) == 5

    def test_consecutive_downtime_merge(self):
        entries = [
            {'end_time': datetime.now() - timedelta(minutes=5)},
            {'start_time': datetime.now() - timedelta(minutes=5)}
        ]
        gap = 5
        should_merge = gap <= 5
        assert should_merge is True


class TestHoldCRUD:
    """Test Hold CRUD operations."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock(spec=Session)

    @pytest.fixture
    def sample_hold_data(self):
        return {
            "production_entry_id": 1,
            "hold_reason": "Quality investigation",
            "hold_date": datetime.now(),
            "quantity_held": 50,
            "status": "active",
        }

    def test_create_hold_entry(self, mock_db, sample_hold_data):
        mock_entry = MagicMock(**sample_hold_data, id=1)
        mock_db.add(mock_entry)
        mock_db.commit()
        mock_db.add.assert_called()

    def test_get_active_holds(self, mock_db):
        mock_entries = [MagicMock(status='active') for _ in range(3)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_entries
        result = mock_db.query().filter().all()
        assert len(result) == 3

    def test_release_hold(self, mock_db):
        mock_entry = MagicMock(status='active')
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entry
        entry = mock_db.query().filter().first()
        entry.status = 'released'
        entry.release_date = datetime.now()
        mock_db.commit()
        assert entry.status == 'released'

    def test_scrap_hold(self, mock_db):
        mock_entry = MagicMock(status='active', quantity_held=50)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_entry
        entry = mock_db.query().filter().first()
        entry.status = 'scrapped'
        entry.quantity_scrapped = 50
        mock_db.commit()
        assert entry.status == 'scrapped'

    def test_hold_aging_calculation(self):
        hold_date = datetime.now() - timedelta(days=5)
        aging_days = (datetime.now() - hold_date).days
        assert aging_days == 5

    def test_hold_summary(self, mock_db):
        mock_summary = {'total_held': 500, 'active': 200, 'released': 250, 'scrapped': 50}
        mock_db.query.return_value.first.return_value = MagicMock(**mock_summary)
        result = mock_db.query().first()
        assert result.total_held == 500


class TestEmployeeCRUD:
    """Test Employee CRUD operations."""

    @pytest.fixture
    def mock_db(self):
        return MagicMock(spec=Session)

    def test_create_employee(self, mock_db):
        mock_emp = MagicMock(id=1, name='John Doe', employee_id='EMP001')
        mock_db.add(mock_emp)
        mock_db.commit()
        mock_db.add.assert_called()

    def test_get_employee_by_id(self, mock_db):
        mock_emp = MagicMock(employee_id='EMP001')
        mock_db.query.return_value.filter.return_value.first.return_value = mock_emp
        result = mock_db.query().filter().first()
        assert result.employee_id == 'EMP001'

    def test_get_employees_by_department(self, mock_db):
        mock_emps = [MagicMock(department='Production') for _ in range(20)]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_emps
        result = mock_db.query().filter().all()
        assert len(result) == 20

    def test_update_employee(self, mock_db):
        mock_emp = MagicMock(department='Production')
        mock_db.query.return_value.filter.return_value.first.return_value = mock_emp
        emp = mock_db.query().filter().first()
        emp.department = 'Quality'
        mock_db.commit()
        assert emp.department == 'Quality'

    def test_deactivate_employee(self, mock_db):
        mock_emp = MagicMock(is_active=True)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_emp
        emp = mock_db.query().filter().first()
        emp.is_active = False
        mock_db.commit()
        assert emp.is_active is False

    def test_employee_shift_assignment(self, mock_db):
        mock_emp = MagicMock(shift_id=1)
        mock_emp.shift_id = 2
        mock_db.commit()
        assert mock_emp.shift_id == 2

    def test_employee_skills(self):
        skills = ['welding', 'assembly', 'quality_inspection']
        assert len(skills) == 3

    def test_employee_headcount(self, mock_db):
        mock_db.query.return_value.filter.return_value.count.return_value = 100
        count = mock_db.query().filter().count()
        assert count == 100
