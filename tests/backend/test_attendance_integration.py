"""
Integration Tests for Attendance API Endpoints
Tests all 8 attendance endpoints, role-based access control, and Bradford Factor calculation
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.schemas.attendance import AttendanceEntry
from backend.schemas.employee import Employee
from backend.schemas.shift import Shift
from backend.schemas.user import User
from backend.crud.attendance import (
    create_attendance_record,
    get_attendance_record,
    get_attendance_records,
    update_attendance_record,
    delete_attendance_record
)
from backend.calculations.absenteeism import calculate_absenteeism, calculate_bradford_factor


@pytest.fixture
def test_employees(test_db: Session):
    """Create test employees"""
    employees = []
    for i in range(3):
        emp = Employee(
            employee_code=f"EMP-TEST-{i:03d}",
            employee_name=f"Test Employee {i}",
            is_floating_pool=0,
            client_id_fk="TEST-CLIENT"
        )
        test_db.add(emp)
        test_db.flush()
        employees.append(emp)
    test_db.commit()
    return employees


@pytest.fixture
def test_shift(test_db: Session):
    """Create test shift"""
    shift = Shift(
        shift_name="Test Shift",
        start_time="08:00",
        end_time="16:00",
        is_active=True
    )
    test_db.add(shift)
    test_db.commit()
    return shift


@pytest.fixture
def test_user(test_db: Session):
    """Create test user"""
    user = User(
        username="test_supervisor",
        email="supervisor@test.com",
        password_hash="hashed_password",
        full_name="Test Supervisor",
        role="SUPERVISOR",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


class TestAttendanceCreate:
    """Test POST /api/attendance - Create attendance record"""

    def test_create_present_attendance(self, test_db, test_employees, test_shift, test_user):
        """Should create attendance record for present employee"""
        from backend.models.attendance import AttendanceRecordCreate

        attendance_data = AttendanceRecordCreate(
            employee_id=test_employees[0].employee_id,
            shift_id=test_shift.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )

        result = create_attendance_record(test_db, attendance_data, test_user)

        assert result is not None
        assert result.employee_id == test_employees[0].employee_id
        assert result.status == "PRESENT"
        assert result.actual_hours == Decimal("8.0")

    def test_create_absent_attendance(self, test_db, test_employees, test_shift, test_user):
        """Should create attendance record for absent employee"""
        from backend.models.attendance import AttendanceRecordCreate

        attendance_data = AttendanceRecordCreate(
            employee_id=test_employees[0].employee_id,
            shift_id=test_shift.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("0.0"),
            status="ABSENT",
            absence_reason="SICK_LEAVE"
        )

        result = create_attendance_record(test_db, attendance_data, test_user)

        assert result is not None
        assert result.status == "ABSENT"
        assert result.actual_hours == Decimal("0.0")
        assert result.absence_reason == "SICK_LEAVE"

    def test_create_partial_attendance(self, test_db, test_employees, test_shift, test_user):
        """Should create attendance record for partial attendance"""
        from backend.models.attendance import AttendanceRecordCreate

        attendance_data = AttendanceRecordCreate(
            employee_id=test_employees[0].employee_id,
            shift_id=test_shift.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("4.0"),
            status="PARTIAL",
            absence_reason="PERSONAL_LEAVE"
        )

        result = create_attendance_record(test_db, attendance_data, test_user)

        assert result is not None
        assert result.status == "PARTIAL"
        assert result.actual_hours == Decimal("4.0")


class TestAttendanceRead:
    """Test GET /api/attendance - List attendance records"""

    def test_list_all_attendance(self, test_db, test_employees, test_shift, test_user):
        """Should list all attendance records for user's client"""
        from backend.models.attendance import AttendanceRecordCreate

        # Create multiple records
        for emp in test_employees:
            attendance_data = AttendanceRecordCreate(
                employee_id=emp.employee_id,
                shift_id=test_shift.shift_id,
                attendance_date=date.today(),
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                status="PRESENT"
            )
            create_attendance_record(test_db, attendance_data, test_user)

        result = get_attendance_records(test_db, test_user)

        assert len(result) == 3
        assert all(r.status == "PRESENT" for r in result)

    def test_filter_by_date_range(self, test_db, test_employees, test_shift, test_user):
        """Should filter attendance by date range"""
        from backend.models.attendance import AttendanceRecordCreate

        # Create records for different dates
        dates = [date.today() - timedelta(days=i) for i in range(5)]
        for d in dates:
            attendance_data = AttendanceRecordCreate(
                employee_id=test_employees[0].employee_id,
                shift_id=test_shift.shift_id,
                attendance_date=d,
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                status="PRESENT"
            )
            create_attendance_record(test_db, attendance_data, test_user)

        start_date = date.today() - timedelta(days=2)
        end_date = date.today()

        result = get_attendance_records(
            test_db, test_user,
            start_date=start_date,
            end_date=end_date
        )

        assert len(result) == 3  # Today, yesterday, day before

    def test_filter_by_employee(self, test_db, test_employees, test_shift, test_user):
        """Should filter attendance by employee"""
        from backend.models.attendance import AttendanceRecordCreate

        # Create records for different employees
        for emp in test_employees:
            attendance_data = AttendanceRecordCreate(
                employee_id=emp.employee_id,
                shift_id=test_shift.shift_id,
                attendance_date=date.today(),
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                status="PRESENT"
            )
            create_attendance_record(test_db, attendance_data, test_user)

        result = get_attendance_records(
            test_db, test_user,
            employee_id=test_employees[0].employee_id
        )

        assert len(result) == 1
        assert result[0].employee_id == test_employees[0].employee_id

    def test_filter_by_status(self, test_db, test_employees, test_shift, test_user):
        """Should filter attendance by status"""
        from backend.models.attendance import AttendanceRecordCreate

        # Create records with different statuses
        statuses = ["PRESENT", "ABSENT", "PARTIAL"]
        for i, status in enumerate(statuses):
            attendance_data = AttendanceRecordCreate(
                employee_id=test_employees[i].employee_id,
                shift_id=test_shift.shift_id,
                attendance_date=date.today(),
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0" if status == "PRESENT" else "0.0"),
                status=status
            )
            create_attendance_record(test_db, attendance_data, test_user)

        result = get_attendance_records(test_db, test_user, status="ABSENT")

        assert len(result) == 1
        assert result[0].status == "ABSENT"


class TestAttendanceGetById:
    """Test GET /api/attendance/{attendance_id} - Get attendance by ID"""

    def test_get_existing_attendance(self, test_db, test_employees, test_shift, test_user):
        """Should get attendance record by ID"""
        from backend.models.attendance import AttendanceRecordCreate

        attendance_data = AttendanceRecordCreate(
            employee_id=test_employees[0].employee_id,
            shift_id=test_shift.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )

        created = create_attendance_record(test_db, attendance_data, test_user)
        result = get_attendance_record(test_db, created.attendance_id, test_user)

        assert result is not None
        assert result.attendance_id == created.attendance_id

    def test_get_nonexistent_attendance(self, test_db, test_user):
        """Should return None for nonexistent attendance"""
        result = get_attendance_record(test_db, 99999, test_user)
        assert result is None


class TestAttendanceUpdate:
    """Test PUT /api/attendance/{attendance_id} - Update attendance"""

    def test_update_attendance_status(self, test_db, test_employees, test_shift, test_user):
        """Should update attendance status"""
        from backend.models.attendance import AttendanceRecordCreate, AttendanceRecordUpdate

        # Create
        attendance_data = AttendanceRecordCreate(
            employee_id=test_employees[0].employee_id,
            shift_id=test_shift.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )
        created = create_attendance_record(test_db, attendance_data, test_user)

        # Update
        update_data = AttendanceRecordUpdate(
            status="ABSENT",
            actual_hours=Decimal("0.0"),
            absence_reason="SICK_LEAVE"
        )

        updated = update_attendance_record(
            test_db, created.attendance_id, update_data, test_user
        )

        assert updated.status == "ABSENT"
        assert updated.actual_hours == Decimal("0.0")
        assert updated.absence_reason == "SICK_LEAVE"

    def test_update_actual_hours(self, test_db, test_employees, test_shift, test_user):
        """Should update actual hours"""
        from backend.models.attendance import AttendanceRecordCreate, AttendanceRecordUpdate

        attendance_data = AttendanceRecordCreate(
            employee_id=test_employees[0].employee_id,
            shift_id=test_shift.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )
        created = create_attendance_record(test_db, attendance_data, test_user)

        update_data = AttendanceRecordUpdate(actual_hours=Decimal("7.5"))
        updated = update_attendance_record(
            test_db, created.attendance_id, update_data, test_user
        )

        assert updated.actual_hours == Decimal("7.5")


class TestAttendanceDelete:
    """Test DELETE /api/attendance/{attendance_id} - Delete attendance (supervisor only)"""

    def test_delete_attendance_as_supervisor(self, test_db, test_employees, test_shift, test_user):
        """Should delete attendance record as supervisor"""
        from backend.models.attendance import AttendanceRecordCreate

        attendance_data = AttendanceRecordCreate(
            employee_id=test_employees[0].employee_id,
            shift_id=test_shift.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )
        created = create_attendance_record(test_db, attendance_data, test_user)

        success = delete_attendance_record(test_db, created.attendance_id, test_user)

        assert success is True

        # Verify deleted
        result = get_attendance_record(test_db, created.attendance_id, test_user)
        assert result is None


class TestAbsenteeismCalculation:
    """Test GET /api/kpi/absenteeism - Calculate absenteeism rate"""

    def test_calculate_absenteeism_zero_percent(self, test_db, test_employees, test_shift, test_user):
        """Should calculate 0% absenteeism when all present"""
        from backend.models.attendance import AttendanceRecordCreate

        # All employees present for 5 days
        for day in range(5):
            attendance_date = date.today() - timedelta(days=day)
            for emp in test_employees:
                attendance_data = AttendanceRecordCreate(
                    employee_id=emp.employee_id,
                    shift_id=test_shift.shift_id,
                    attendance_date=attendance_date,
                    scheduled_hours=Decimal("8.0"),
                    actual_hours=Decimal("8.0"),
                    status="PRESENT"
                )
                create_attendance_record(test_db, attendance_data, test_user)

        rate, scheduled, absent, emp_count, absence_count = calculate_absenteeism(
            test_db,
            test_shift.shift_id,
            date.today() - timedelta(days=4),
            date.today()
        )

        assert rate == Decimal("0.0")
        assert emp_count == 3
        assert absence_count == 0

    def test_calculate_absenteeism_with_absences(self, test_db, test_employees, test_shift, test_user):
        """Should calculate correct absenteeism rate with absences"""
        from backend.models.attendance import AttendanceRecordCreate

        # Day 1: All present (3 employees * 8 hours = 24 hours)
        for emp in test_employees:
            attendance_data = AttendanceRecordCreate(
                employee_id=emp.employee_id,
                shift_id=test_shift.shift_id,
                attendance_date=date.today(),
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                status="PRESENT"
            )
            create_attendance_record(test_db, attendance_data, test_user)

        # Day 2: 1 employee absent (2 present * 8 + 1 absent * 0 = 16 hours worked, 8 hours absent)
        yesterday = date.today() - timedelta(days=1)
        for i, emp in enumerate(test_employees):
            attendance_data = AttendanceRecordCreate(
                employee_id=emp.employee_id,
                shift_id=test_shift.shift_id,
                attendance_date=yesterday,
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0" if i < 2 else "0.0"),
                status="PRESENT" if i < 2 else "ABSENT"
            )
            create_attendance_record(test_db, attendance_data, test_user)

        rate, scheduled, absent, emp_count, absence_count = calculate_absenteeism(
            test_db,
            test_shift.shift_id,
            yesterday,
            date.today()
        )

        # Total scheduled: 3 employees * 2 days * 8 hours = 48 hours
        # Total absent: 8 hours
        # Rate: 8/48 = 0.1667 (16.67%)
        assert rate == Decimal("16.67")
        assert absence_count == 1


class TestBradfordFactorCalculation:
    """Test GET /api/kpi/bradford-factor/{employee_id} - Calculate Bradford Factor"""

    def test_bradford_factor_zero_absences(self, test_db, test_employees, test_shift, test_user):
        """Should calculate Bradford Factor = 0 for no absences"""
        from backend.models.attendance import AttendanceRecordCreate

        # All present
        for day in range(30):
            attendance_date = date.today() - timedelta(days=day)
            attendance_data = AttendanceRecordCreate(
                employee_id=test_employees[0].employee_id,
                shift_id=test_shift.shift_id,
                attendance_date=attendance_date,
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                status="PRESENT"
            )
            create_attendance_record(test_db, attendance_data, test_user)

        bradford_score = calculate_bradford_factor(
            test_db,
            test_employees[0].employee_id,
            date.today() - timedelta(days=29),
            date.today()
        )

        assert bradford_score == 0

    def test_bradford_factor_single_absence(self, test_db, test_employees, test_shift, test_user):
        """Should calculate Bradford Factor for single absence"""
        from backend.models.attendance import AttendanceRecordCreate

        # 29 days present, 1 day absent
        for day in range(30):
            attendance_date = date.today() - timedelta(days=day)
            status = "ABSENT" if day == 0 else "PRESENT"
            actual_hours = Decimal("0.0") if day == 0 else Decimal("8.0")

            attendance_data = AttendanceRecordCreate(
                employee_id=test_employees[0].employee_id,
                shift_id=test_shift.shift_id,
                attendance_date=attendance_date,
                scheduled_hours=Decimal("8.0"),
                actual_hours=actual_hours,
                status=status
            )
            create_attendance_record(test_db, attendance_data, test_user)

        bradford_score = calculate_bradford_factor(
            test_db,
            test_employees[0].employee_id,
            date.today() - timedelta(days=29),
            date.today()
        )

        # Bradford Factor = S^2 * D
        # S = 1 (one absence spell)
        # D = 1 (one day absent)
        # Score = 1^2 * 1 = 1
        assert bradford_score == 1

    def test_bradford_factor_multiple_spells(self, test_db, test_employees, test_shift, test_user):
        """Should calculate Bradford Factor for multiple absence spells"""
        from backend.models.attendance import AttendanceRecordCreate

        # Create attendance records with 3 separate absence spells
        # Spell 1: Day 0 (1 day)
        # Spell 2: Days 7-8 (2 days)
        # Spell 3: Day 15 (1 day)
        # Total: 3 spells, 4 days
        # Bradford = 3^2 * 4 = 36

        absent_days = [0, 7, 8, 15]
        for day in range(30):
            attendance_date = date.today() - timedelta(days=day)
            status = "ABSENT" if day in absent_days else "PRESENT"
            actual_hours = Decimal("0.0") if day in absent_days else Decimal("8.0")

            attendance_data = AttendanceRecordCreate(
                employee_id=test_employees[0].employee_id,
                shift_id=test_shift.shift_id,
                attendance_date=attendance_date,
                scheduled_hours=Decimal("8.0"),
                actual_hours=actual_hours,
                status=status
            )
            create_attendance_record(test_db, attendance_data, test_user)

        bradford_score = calculate_bradford_factor(
            test_db,
            test_employees[0].employee_id,
            date.today() - timedelta(days=29),
            date.today()
        )

        # Expected: 3 spells * 3 spells * 4 days = 36
        assert bradford_score == 36


class TestAttendanceRBAC:
    """Test role-based access control for attendance endpoints"""

    def test_operator_can_view_own_client_attendance(self, test_db, test_employees, test_shift):
        """OPERATOR role can view attendance for their client"""
        # Create operator user
        operator = User(
            username="operator",
            email="operator@test.com",
            password_hash="hashed",
            role="OPERATOR",
            is_active=True
        )
        test_db.add(operator)
        test_db.commit()

        from backend.models.attendance import AttendanceRecordCreate

        attendance_data = AttendanceRecordCreate(
            employee_id=test_employees[0].employee_id,
            shift_id=test_shift.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )

        created = create_attendance_record(test_db, attendance_data, operator)
        result = get_attendance_record(test_db, created.attendance_id, operator)

        assert result is not None

    def test_supervisor_can_delete_attendance(self, test_db, test_employees, test_shift):
        """SUPERVISOR role can delete attendance records"""
        supervisor = User(
            username="supervisor",
            email="supervisor@test.com",
            password_hash="hashed",
            role="SUPERVISOR",
            is_active=True
        )
        test_db.add(supervisor)
        test_db.commit()

        from backend.models.attendance import AttendanceRecordCreate

        attendance_data = AttendanceRecordCreate(
            employee_id=test_employees[0].employee_id,
            shift_id=test_shift.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )

        created = create_attendance_record(test_db, attendance_data, supervisor)
        success = delete_attendance_record(test_db, created.attendance_id, supervisor)

        assert success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
