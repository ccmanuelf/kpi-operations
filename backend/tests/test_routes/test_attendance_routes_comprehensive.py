"""
Comprehensive Attendance Routes Tests
Tests API endpoints with authenticated clients and real database.
Target: Increase routes/attendance.py coverage from 30% to 80%+
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.schemas import ClientType
from backend.routes.attendance import router as attendance_router
from backend.tests.fixtures.factories import TestDataFactory


def create_test_app(db_session):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(attendance_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture(scope="function")
def attendance_db():
    """Create a fresh database for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    session = TestingSession()
    TestDataFactory.reset_counters()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def attendance_setup(attendance_db):
    """Create standard test data for attendance tests."""
    db = attendance_db

    # Create client
    client = TestDataFactory.create_client(
        db, client_id="ATTENDANCE-TEST", client_name="Attendance Test Client", client_type=ClientType.HOURLY_RATE
    )

    # Create users
    admin = TestDataFactory.create_user(db, user_id="att-admin-001", username="att_admin", role="admin", client_id=None)

    supervisor = TestDataFactory.create_user(
        db, user_id="att-super-001", username="att_supervisor", role="supervisor", client_id=client.client_id
    )

    operator = TestDataFactory.create_user(
        db, user_id="att-oper-001", username="att_operator", role="operator", client_id=client.client_id
    )

    # Create shift
    shift = TestDataFactory.create_shift(
        db, client_id=client.client_id, shift_name="Attendance Shift", start_time="06:00:00", end_time="14:00:00"
    )

    # Create employees
    employees = []
    for i in range(3):
        emp = TestDataFactory.create_employee(
            db,
            client_id=client.client_id,
            employee_name=f"Attendance Employee {i+1}",
            employee_code=f"ATT-EMP-{i+1:03d}",
        )
        employees.append(emp)

    db.flush()

    db.commit()

    return {
        "db": db,
        "client": client,
        "admin": admin,
        "supervisor": supervisor,
        "operator": operator,
        "shift": shift,
        "employees": employees,
    }


@pytest.fixture
def authenticated_client(attendance_setup):
    """Create an authenticated test client."""
    db = attendance_setup["db"]
    user = attendance_setup["supervisor"]
    app = create_test_app(db)

    # Mock auth dependencies
    from backend.auth.jwt import get_current_user, get_current_active_supervisor

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_active_supervisor] = lambda: user

    return TestClient(app), attendance_setup


@pytest.fixture
def admin_client(attendance_setup):
    """Create an admin test client."""
    db = attendance_setup["db"]
    user = attendance_setup["admin"]
    app = create_test_app(db)

    from backend.auth.jwt import get_current_user, get_current_active_supervisor

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_current_active_supervisor] = lambda: user

    return TestClient(app), attendance_setup


class TestListAttendance:
    """Tests for GET /api/attendance endpoint."""

    def test_list_attendance_success(self, authenticated_client):
        """Test listing attendance records."""
        client, setup = authenticated_client

        response = client.get("/api/attendance")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_attendance_with_pagination(self, authenticated_client):
        """Test pagination."""
        client, setup = authenticated_client

        response = client.get("/api/attendance?skip=0&limit=5")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 5

    def test_list_attendance_filter_by_date(self, authenticated_client):
        """Test filtering by date range."""
        client, setup = authenticated_client
        today = date.today()
        week_ago = today - timedelta(days=7)

        response = client.get(f"/api/attendance?start_date={week_ago}&end_date={today}")

        assert response.status_code == 200

    def test_list_attendance_filter_by_employee(self, authenticated_client):
        """Test filtering by employee."""
        client, setup = authenticated_client
        employee = setup["employees"][0]

        response = client.get(f"/api/attendance?employee_id={employee.employee_id}")

        assert response.status_code == 200

    def test_list_attendance_filter_by_shift(self, authenticated_client):
        """Test filtering by shift."""
        client, setup = authenticated_client
        shift = setup["shift"]

        response = client.get(f"/api/attendance?shift_id={shift.shift_id}")

        assert response.status_code == 200

    def test_list_attendance_filter_absent(self, authenticated_client):
        """Test filtering by absent status."""
        client, setup = authenticated_client

        response = client.get("/api/attendance?is_absent=1")

        assert response.status_code == 200


class TestGetAttendance:
    """Tests for GET /api/attendance/{attendance_id} endpoint."""

    def test_get_attendance_not_found(self, authenticated_client):
        """Test error when record doesn't exist."""
        client, _ = authenticated_client

        response = client.get("/api/attendance/99999")

        assert response.status_code == 404


class TestGetAttendanceByEmployee:
    """Tests for GET /api/attendance/by-employee/{employee_id} endpoint."""

    def test_get_attendance_by_employee_success(self, authenticated_client):
        """Test getting attendance by employee."""
        client, setup = authenticated_client
        employee = setup["employees"][0]

        response = client.get(f"/api/attendance/by-employee/{employee.employee_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_attendance_by_employee_with_dates(self, authenticated_client):
        """Test getting attendance by employee with date filter."""
        client, setup = authenticated_client
        employee = setup["employees"][0]
        today = date.today()
        week_ago = today - timedelta(days=7)

        response = client.get(
            f"/api/attendance/by-employee/{employee.employee_id}?" f"start_date={week_ago}&end_date={today}"
        )

        assert response.status_code == 200


class TestGetAttendanceByDateRange:
    """Tests for GET /api/attendance/by-date-range endpoint."""

    def test_get_attendance_by_date_range(self, authenticated_client):
        """Test getting attendance by date range."""
        client, _ = authenticated_client
        today = date.today()
        week_ago = today - timedelta(days=7)

        response = client.get(f"/api/attendance/by-date-range?start_date={week_ago}&end_date={today}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestUpdateAttendance:
    """Tests for PUT /api/attendance/{attendance_id} endpoint."""

    def test_update_attendance_not_found(self, authenticated_client):
        """Test error when record doesn't exist."""
        client, _ = authenticated_client

        response = client.put("/api/attendance/99999", json={"actual_hours_worked": 7.5})

        assert response.status_code == 404


class TestDeleteAttendance:
    """Tests for DELETE /api/attendance/{attendance_id} endpoint."""

    def test_delete_attendance_not_found(self, authenticated_client):
        """Test error when record doesn't exist."""
        client, _ = authenticated_client

        response = client.delete("/api/attendance/99999")

        assert response.status_code == 404


class TestAttendanceStatistics:
    """Tests for GET /api/attendance/statistics/summary endpoint."""

    def test_get_attendance_statistics(self, authenticated_client):
        """Test getting attendance statistics."""
        client, setup = authenticated_client
        today = date.today()
        month_ago = today - timedelta(days=30)

        response = client.get(f"/api/attendance/statistics/summary?start_date={month_ago}&end_date={today}")

        assert response.status_code == 200
        data = response.json()
        assert "start_date" in data
        assert "end_date" in data
        assert "statistics" in data

    def test_get_attendance_statistics_with_shift(self, authenticated_client):
        """Test statistics with shift filter."""
        client, setup = authenticated_client
        shift = setup["shift"]
        today = date.today()
        month_ago = today - timedelta(days=30)

        response = client.get(
            f"/api/attendance/statistics/summary?" f"start_date={month_ago}&end_date={today}&shift_id={shift.shift_id}"
        )

        assert response.status_code == 200


class TestAbsenteeismKPI:
    """Tests for GET /api/attendance/kpi/absenteeism endpoint."""

    def test_calculate_absenteeism_default(self, authenticated_client):
        """Test absenteeism calculation with defaults."""
        client, _ = authenticated_client

        response = client.get("/api/attendance/kpi/absenteeism")

        assert response.status_code == 200
        data = response.json()
        assert "absenteeism_rate" in data or "rate" in data
        assert "total_scheduled_hours" in data
        assert "total_hours_absent" in data

    def test_calculate_absenteeism_with_dates(self, authenticated_client):
        """Test absenteeism with specific dates."""
        client, _ = authenticated_client
        today = date.today()
        week_ago = today - timedelta(days=7)

        response = client.get(f"/api/attendance/kpi/absenteeism?start_date={week_ago}&end_date={today}")

        assert response.status_code == 200
        data = response.json()
        assert data["start_date"] == str(week_ago)
        assert data["end_date"] == str(today)

    def test_calculate_absenteeism_with_shift(self, authenticated_client):
        """Test absenteeism with shift filter."""
        client, setup = authenticated_client
        shift = setup["shift"]

        response = client.get(f"/api/attendance/kpi/absenteeism?shift_id={shift.shift_id}")

        assert response.status_code == 200

    def test_calculate_absenteeism_breakdown_data(self, authenticated_client):
        """Test absenteeism includes breakdown data."""
        client, _ = authenticated_client

        response = client.get("/api/attendance/kpi/absenteeism")

        assert response.status_code == 200
        data = response.json()
        # Should include breakdown sections
        assert "by_reason" in data
        assert "by_department" in data
        assert "high_absence_employees" in data
        assert isinstance(data["by_reason"], list)
        assert isinstance(data["by_department"], list)
        assert isinstance(data["high_absence_employees"], list)

    def test_calculate_absenteeism_total_employees(self, authenticated_client):
        """Test absenteeism includes employee count."""
        client, _ = authenticated_client

        response = client.get("/api/attendance/kpi/absenteeism")

        assert response.status_code == 200
        data = response.json()
        assert "total_employees" in data
        assert "total_absences" in data


class TestAbsenteeismTrend:
    """Tests for GET /api/attendance/kpi/absenteeism/trend endpoint."""

    def test_get_absenteeism_trend_default(self, authenticated_client):
        """Test absenteeism trend with defaults."""
        client, _ = authenticated_client

        response = client.get("/api/attendance/kpi/absenteeism/trend")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_absenteeism_trend_with_dates(self, authenticated_client):
        """Test absenteeism trend with specific dates."""
        client, _ = authenticated_client
        today = date.today()
        week_ago = today - timedelta(days=7)

        response = client.get(f"/api/attendance/kpi/absenteeism/trend?start_date={week_ago}&end_date={today}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_absenteeism_trend_structure(self, authenticated_client):
        """Test absenteeism trend response structure."""
        client, _ = authenticated_client

        response = client.get("/api/attendance/kpi/absenteeism/trend")

        assert response.status_code == 200
        data = response.json()
        # If data exists, check structure
        if data:
            first = data[0]
            assert "date" in first
            assert "value" in first


class TestBradfordFactor:
    """Tests for GET /api/attendance/kpi/bradford-factor/{employee_id} endpoint."""

    def test_calculate_bradford_factor(self, authenticated_client):
        """Test Bradford Factor calculation."""
        client, setup = authenticated_client
        employee = setup["employees"][0]
        today = date.today()
        month_ago = today - timedelta(days=30)

        response = client.get(
            f"/api/attendance/kpi/bradford-factor/{employee.employee_id}?" f"start_date={month_ago}&end_date={today}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "employee_id" in data
        assert "bradford_score" in data
        assert "interpretation" in data
        assert data["employee_id"] == employee.employee_id

    def test_bradford_factor_interpretation_low(self, authenticated_client):
        """Test Bradford Factor interpretation for low risk."""
        client, setup = authenticated_client
        employee = setup["employees"][0]
        today = date.today()
        month_ago = today - timedelta(days=30)

        response = client.get(
            f"/api/attendance/kpi/bradford-factor/{employee.employee_id}?" f"start_date={month_ago}&end_date={today}"
        )

        assert response.status_code == 200
        data = response.json()
        # Score should be numeric and interpretation should be present
        assert isinstance(data["bradford_score"], (int, float))
        assert isinstance(data["interpretation"], str)


class TestAdminAccess:
    """Tests for admin-specific attendance access."""

    def test_admin_sees_all_clients(self, admin_client):
        """Test admin can see all client data."""
        client, _ = admin_client

        response = client.get("/api/attendance")

        assert response.status_code == 200

    def test_admin_statistics_all_clients(self, admin_client):
        """Test admin can get statistics for all clients."""
        client, _ = admin_client
        today = date.today()
        month_ago = today - timedelta(days=30)

        response = client.get(f"/api/attendance/statistics/summary?start_date={month_ago}&end_date={today}")

        assert response.status_code == 200

    def test_admin_absenteeism_all_clients(self, admin_client):
        """Test admin can get absenteeism for all clients."""
        client, _ = admin_client

        response = client.get("/api/attendance/kpi/absenteeism")

        assert response.status_code == 200
