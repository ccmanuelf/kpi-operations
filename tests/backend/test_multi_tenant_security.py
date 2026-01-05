"""
Comprehensive Multi-Tenant Security Tests
Ensures strict data isolation between clients across ALL endpoints
CRITICAL: Every query MUST enforce client_id filtering
"""
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.schemas.user import User
from backend.schemas.client import Client


@pytest.fixture
def client_a(test_db: Session):
    """Create Client A"""
    client = Client(
        client_id="CLIENT-A",
        client_name="Test Client A",
        is_active=True
    )
    test_db.add(client)
    test_db.commit()
    return client


@pytest.fixture
def client_b(test_db: Session):
    """Create Client B"""
    client = Client(
        client_id="CLIENT-B",
        client_name="Test Client B",
        is_active=True
    )
    test_db.add(client)
    test_db.commit()
    return client


@pytest.fixture
def user_client_a(test_db: Session, client_a):
    """Create user for Client A (OPERATOR role)"""
    user = User(
        username="operator_client_a",
        email="operator_a@test.com",
        password_hash="hashed",
        role="OPERATOR",
        client_id_fk="CLIENT-A",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def user_client_b(test_db: Session, client_b):
    """Create user for Client B (OPERATOR role)"""
    user = User(
        username="operator_client_b",
        email="operator_b@test.com",
        password_hash="hashed",
        role="OPERATOR",
        client_id_fk="CLIENT-B",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def admin_user(test_db: Session):
    """Create ADMIN user (can see all clients)"""
    user = User(
        username="admin_user",
        email="admin@test.com",
        password_hash="hashed",
        role="ADMIN",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


class TestAttendanceIsolation:
    """Test attendance data isolation between clients"""

    def test_client_a_cannot_see_client_b_attendance(
        self, test_db, client_a, client_b, user_client_a, user_client_b
    ):
        """Client A user cannot see Client B's attendance records"""
        from backend.schemas.employee import Employee
        from backend.schemas.shift import Shift
        from backend.models.attendance import AttendanceRecordCreate
        from backend.crud.attendance import create_attendance_record, get_attendance_records

        # Create shift
        shift = Shift(shift_name="Day Shift", start_time="08:00", end_time="16:00", is_active=True)
        test_db.add(shift)
        test_db.commit()

        # Create employees for both clients
        emp_a = Employee(employee_code="EMP-A-001", employee_name="Employee A", client_id_fk="CLIENT-A")
        emp_b = Employee(employee_code="EMP-B-001", employee_name="Employee B", client_id_fk="CLIENT-B")
        test_db.add_all([emp_a, emp_b])
        test_db.commit()

        # Create attendance for both clients
        att_a = AttendanceRecordCreate(
            employee_id=emp_a.employee_id,
            shift_id=shift.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )
        att_b = AttendanceRecordCreate(
            employee_id=emp_b.employee_id,
            shift_id=shift.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )

        create_attendance_record(test_db, att_a, user_client_a)
        create_attendance_record(test_db, att_b, user_client_b)

        # Client A queries attendance
        results_a = get_attendance_records(test_db, user_client_a)

        # Verify only Client A's records returned
        assert all(r.employee.client_id_fk == "CLIENT-A" for r in results_a)
        assert len(results_a) == 1

    def test_admin_can_see_all_clients(self, test_db, client_a, client_b, admin_user):
        """ADMIN role can see attendance for all clients"""
        from backend.schemas.employee import Employee
        from backend.schemas.shift import Shift
        from backend.models.attendance import AttendanceRecordCreate
        from backend.crud.attendance import create_attendance_record, get_attendance_records

        # Create shift
        shift = Shift(shift_name="Day Shift", start_time="08:00", end_time="16:00", is_active=True)
        test_db.add(shift)
        test_db.commit()

        # Create employees for both clients
        emp_a = Employee(employee_code="EMP-A-002", employee_name="Employee A2", client_id_fk="CLIENT-A")
        emp_b = Employee(employee_code="EMP-B-002", employee_name="Employee B2", client_id_fk="CLIENT-B")
        test_db.add_all([emp_a, emp_b])
        test_db.commit()

        # Create attendance for both
        for emp in [emp_a, emp_b]:
            att = AttendanceRecordCreate(
                employee_id=emp.employee_id,
                shift_id=shift.shift_id,
                attendance_date=date.today(),
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                status="PRESENT"
            )
            create_attendance_record(test_db, att, admin_user)

        # Admin queries all
        results = get_attendance_records(test_db, admin_user)

        # Verify both clients' records returned
        client_ids = set(r.employee.client_id_fk for r in results)
        assert "CLIENT-A" in client_ids
        assert "CLIENT-B" in client_ids


class TestWorkOrderIsolation:
    """Test work order data isolation"""

    def test_client_cannot_access_other_client_work_order(
        self, test_db, client_a, client_b, user_client_a, user_client_b
    ):
        """Client A cannot access Client B's work orders"""
        from backend.models.work_order import WorkOrderCreate
        from backend.crud.work_order import create_work_order, get_work_order, get_work_orders

        # Create work orders for both clients
        wo_a = WorkOrderCreate(
            work_order_id="WO-A-001",
            client_id="CLIENT-A",
            style_model="STYLE-A",
            planned_quantity=1000,
            status="ACTIVE"
        )
        wo_b = WorkOrderCreate(
            work_order_id="WO-B-001",
            client_id="CLIENT-B",
            style_model="STYLE-B",
            planned_quantity=2000,
            status="ACTIVE"
        )

        created_a = create_work_order(test_db, wo_a.model_dump(), user_client_a)
        created_b = create_work_order(test_db, wo_b.model_dump(), user_client_b)

        # Client A tries to access Client B's work order
        result = get_work_order(test_db, "WO-B-001", user_client_a)

        # Should return None (access denied)
        assert result is None

        # Client A lists work orders
        wo_list_a = get_work_orders(test_db, user_client_a)

        # Should only see own work orders
        assert all(wo.client_id == "CLIENT-A" for wo in wo_list_a)


class TestQualityIsolation:
    """Test quality inspection data isolation"""

    def test_quality_data_isolated_by_client(
        self, test_db, client_a, client_b, user_client_a, user_client_b
    ):
        """Quality inspections isolated by client"""
        from backend.schemas.product import Product
        from backend.schemas.shift import Shift
        from backend.models.quality import QualityInspectionCreate
        from backend.crud.quality import create_quality_inspection, get_quality_inspections

        # Create products
        prod_a = Product(product_code="PROD-A", product_name="Product A", is_active=True)
        prod_b = Product(product_code="PROD-B", product_name="Product B", is_active=True)
        test_db.add_all([prod_a, prod_b])

        # Create shift
        shift = Shift(shift_name="Day", start_time="08:00", end_time="16:00", is_active=True)
        test_db.add(shift)
        test_db.commit()

        # Create quality inspections
        insp_a = QualityInspectionCreate(
            product_id=prod_a.product_id,
            shift_id=shift.shift_id,
            inspection_date=date.today(),
            units_inspected=100,
            units_passed=95,
            units_failed=5,
            inspection_stage="FINAL",
            defect_count=5,
            client_id_fk="CLIENT-A"
        )
        insp_b = QualityInspectionCreate(
            product_id=prod_b.product_id,
            shift_id=shift.shift_id,
            inspection_date=date.today(),
            units_inspected=200,
            units_passed=190,
            units_failed=10,
            inspection_stage="FINAL",
            defect_count=10,
            client_id_fk="CLIENT-B"
        )

        create_quality_inspection(test_db, insp_a, user_client_a)
        create_quality_inspection(test_db, insp_b, user_client_b)

        # Client A queries inspections
        results_a = get_quality_inspections(test_db, user_client_a)

        # Verify isolation
        assert len(results_a) == 1
        assert results_a[0].client_id_fk == "CLIENT-A"


class TestFloatingPoolIsolation:
    """Test floating pool employee assignment isolation"""

    def test_floating_pool_assignment_tracked_per_client(
        self, test_db, client_a, client_b, user_client_a, user_client_b
    ):
        """Floating pool assignments tracked per client"""
        from backend.schemas.employee import Employee
        from backend.schemas.shift import Shift
        from backend.models.coverage import ShiftCoverageCreate
        from backend.crud.coverage import create_shift_coverage, get_shift_coverages

        # Create floating pool employee
        floating_emp = Employee(
            employee_code="FLOAT-001",
            employee_name="Floating Employee",
            is_floating_pool=1
        )
        test_db.add(floating_emp)

        # Create shift
        shift = Shift(shift_name="Day", start_time="08:00", end_time="16:00", is_active=True)
        test_db.add(shift)
        test_db.commit()

        # Assign to Client A today
        coverage_a = ShiftCoverageCreate(
            shift_id=shift.shift_id,
            coverage_date=date.today(),
            employee_id=floating_emp.employee_id,
            hours_assigned=Decimal("8.0"),
            is_floating_pool=True,
            client_id_fk="CLIENT-A"
        )

        create_shift_coverage(test_db, coverage_a, user_client_a)

        # Client A sees assignment
        results_a = get_shift_coverages(test_db, user_client_a, coverage_date=date.today())
        assert len(results_a) == 1

        # Client B should NOT see Client A's assignment
        results_b = get_shift_coverages(test_db, user_client_b, coverage_date=date.today())
        assert len(results_b) == 0


class TestKPICalculationIsolation:
    """Test KPI calculations respect client boundaries"""

    def test_absenteeism_kpi_per_client(
        self, test_db, client_a, client_b, user_client_a, user_client_b
    ):
        """Absenteeism KPI calculated per client"""
        from backend.schemas.employee import Employee
        from backend.schemas.shift import Shift
        from backend.models.attendance import AttendanceRecordCreate
        from backend.crud.attendance import create_attendance_record
        from backend.calculations.absenteeism import calculate_absenteeism

        # Create shift
        shift = Shift(shift_name="Day", start_time="08:00", end_time="16:00", is_active=True)
        test_db.add(shift)
        test_db.commit()

        # Create employees
        emp_a = Employee(employee_code="EMP-A-KPI", employee_name="Emp A", client_id_fk="CLIENT-A")
        emp_b = Employee(employee_code="EMP-B-KPI", employee_name="Emp B", client_id_fk="CLIENT-B")
        test_db.add_all([emp_a, emp_b])
        test_db.commit()

        # Client A: 1 present, 0 absent (0% absenteeism)
        att_a = AttendanceRecordCreate(
            employee_id=emp_a.employee_id,
            shift_id=shift.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("8.0"),
            status="PRESENT"
        )

        # Client B: 1 absent (100% absenteeism)
        att_b = AttendanceRecordCreate(
            employee_id=emp_b.employee_id,
            shift_id=shift.shift_id,
            attendance_date=date.today(),
            scheduled_hours=Decimal("8.0"),
            actual_hours=Decimal("0.0"),
            status="ABSENT"
        )

        create_attendance_record(test_db, att_a, user_client_a)
        create_attendance_record(test_db, att_b, user_client_b)

        # Calculate KPI for Client A (should be 0%)
        rate_a, _, _, _, _ = calculate_absenteeism(
            test_db, shift.shift_id, date.today(), date.today()
        )

        # Note: This test assumes calculate_absenteeism filters by client
        # Implementation should use current_user's client_id
        assert rate_a == Decimal("0.0")


class TestConcurrentAccessIsolation:
    """Test concurrent access maintains isolation"""

    def test_concurrent_queries_maintain_isolation(
        self, test_db, client_a, client_b, user_client_a, user_client_b
    ):
        """Concurrent queries by different clients maintain isolation"""
        import threading
        from backend.schemas.employee import Employee
        from backend.schemas.shift import Shift
        from backend.models.attendance import AttendanceRecordCreate
        from backend.crud.attendance import create_attendance_record, get_attendance_records

        # Create shift
        shift = Shift(shift_name="Day", start_time="08:00", end_time="16:00", is_active=True)
        test_db.add(shift)

        # Create employees
        emp_a = Employee(employee_code="CONCURRENT-A", employee_name="Emp A", client_id_fk="CLIENT-A")
        emp_b = Employee(employee_code="CONCURRENT-B", employee_name="Emp B", client_id_fk="CLIENT-B")
        test_db.add_all([emp_a, emp_b])
        test_db.commit()

        # Create attendance
        for emp, user in [(emp_a, user_client_a), (emp_b, user_client_b)]:
            att = AttendanceRecordCreate(
                employee_id=emp.employee_id,
                shift_id=shift.shift_id,
                attendance_date=date.today(),
                scheduled_hours=Decimal("8.0"),
                actual_hours=Decimal("8.0"),
                status="PRESENT"
            )
            create_attendance_record(test_db, att, user)

        # Concurrent queries
        results = {"CLIENT-A": None, "CLIENT-B": None}

        def query_client_a():
            results["CLIENT-A"] = get_attendance_records(test_db, user_client_a)

        def query_client_b():
            results["CLIENT-B"] = get_attendance_records(test_db, user_client_b)

        thread_a = threading.Thread(target=query_client_a)
        thread_b = threading.Thread(target=query_client_b)

        thread_a.start()
        thread_b.start()
        thread_a.join()
        thread_b.join()

        # Verify no cross-contamination
        assert all(r.employee.client_id_fk == "CLIENT-A" for r in results["CLIENT-A"])
        assert all(r.employee.client_id_fk == "CLIENT-B" for r in results["CLIENT-B"])


class TestDatabaseLevelIsolation:
    """Test database-level isolation enforcement"""

    def test_foreign_key_constraints_enforce_client_id(self, test_db, client_a, client_b):
        """Foreign key constraints prevent cross-client references"""
        from backend.schemas.employee import Employee
        from backend.schemas.work_order import WorkOrder
        from backend.models.job import Job

        # Create employee for Client A
        emp_a = Employee(employee_code="EMP-FK-A", employee_name="Emp A", client_id_fk="CLIENT-A")
        test_db.add(emp_a)

        # Create work order for Client B
        wo_b = WorkOrder(
            work_order_id="WO-FK-B",
            client_id="CLIENT-B",
            style_model="STYLE",
            planned_quantity=1000,
            status="ACTIVE"
        )
        test_db.add(wo_b)
        test_db.commit()

        # Try to create job linking Client B work order with Client A employee
        # This should fail due to client_id mismatch
        with pytest.raises(Exception):  # Integrity error or validation error
            job = Job(
                job_id="JOB-INVALID",
                work_order_id="WO-FK-B",
                employee_id=emp_a.employee_id,
                client_id_fk="CLIENT-B"  # Mismatch!
            )
            test_db.add(job)
            test_db.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
