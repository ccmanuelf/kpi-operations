"""
Route tests for bulk attendance endpoints.
Tests POST /api/attendance/bulk and POST /api/attendance/mark-all-present.
Uses real database with TestDataFactory and real JWT tokens.
"""

import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.orm import ClientType
from backend.routes.attendance import router as attendance_router
from backend.tests.fixtures.factories import TestDataFactory
from backend.tests.fixtures.auth_fixtures import create_test_token


def _create_test_app(db_session):
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
def bulk_att_db():
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
def bulk_setup(bulk_att_db):
    """Create standard test data for bulk attendance route tests."""
    db = bulk_att_db

    # Create client
    client = TestDataFactory.create_client(
        db, client_id="BULK-RT-TEST", client_name="Bulk Route Test", client_type=ClientType.HOURLY_RATE
    )

    # Create admin user (access to all clients)
    admin = TestDataFactory.create_user(db, user_id="brt-admin-001", username="brt_admin", role="admin", client_id=None)

    # Create operator user (restricted to this client)
    operator = TestDataFactory.create_user(
        db, user_id="brt-oper-001", username="brt_operator", role="operator", client_id=client.client_id
    )

    # Create shift (06:00 - 14:00 = 8 hours)
    shift = TestDataFactory.create_shift(
        db,
        client_id=client.client_id,
        shift_name="Bulk Day Shift",
        start_time="06:00:00",
        end_time="14:00:00",
    )

    # Create employees
    employees = []
    for i in range(5):
        emp = TestDataFactory.create_employee(db, client_id=client.client_id, employee_name=f"Bulk Worker {i}")
        employees.append(emp)

    db.commit()

    # Create test app and client
    app = _create_test_app(db)
    test_client = TestClient(app)

    admin_token = create_test_token(admin)
    operator_token = create_test_token(operator)

    return {
        "db": db,
        "test_client": test_client,
        "client": client,
        "admin": admin,
        "operator": operator,
        "shift": shift,
        "employees": employees,
        "admin_headers": {"Authorization": f"Bearer {admin_token}"},
        "operator_headers": {"Authorization": f"Bearer {operator_token}"},
    }


class TestBulkCreateAttendanceRoute:
    """Tests for POST /api/attendance/bulk endpoint."""

    def test_bulk_create_success(self, bulk_setup):
        """Test successful bulk creation via API."""
        s = bulk_setup
        records = [
            {
                "client_id": s["client"].client_id,
                "employee_id": emp.employee_id,
                "shift_date": date.today().isoformat(),
                "shift_id": s["shift"].shift_id,
                "scheduled_hours": "8.0",
                "actual_hours": "8.0",
                "is_absent": 0,
            }
            for emp in s["employees"][:3]
        ]

        response = s["test_client"].post(
            "/api/attendance/bulk",
            json=records,
            headers=s["admin_headers"],
        )

        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 3
        assert data["successful"] == 3
        assert data["failed"] == 0

    def test_bulk_create_auth_required(self, bulk_setup):
        """Test that 401 is returned without authentication."""
        s = bulk_setup
        records = [
            {
                "client_id": s["client"].client_id,
                "employee_id": s["employees"][0].employee_id,
                "shift_date": date.today().isoformat(),
                "shift_id": s["shift"].shift_id,
                "scheduled_hours": "8.0",
                "actual_hours": "8.0",
                "is_absent": 0,
            }
        ]

        response = s["test_client"].post(
            "/api/attendance/bulk",
            json=records,
        )

        assert response.status_code == 401

    def test_bulk_create_empty_list(self, bulk_setup):
        """Test bulk creation with empty list."""
        s = bulk_setup

        response = s["test_client"].post(
            "/api/attendance/bulk",
            json=[],
            headers=s["admin_headers"],
        )

        assert response.status_code == 201
        data = response.json()
        assert data["total"] == 0
        assert data["successful"] == 0

    def test_bulk_create_invalid_payload(self, bulk_setup):
        """Test bulk creation with invalid payload returns 422."""
        s = bulk_setup

        response = s["test_client"].post(
            "/api/attendance/bulk",
            json=[{"invalid_field": "value"}],
            headers=s["admin_headers"],
        )

        assert response.status_code == 422


class TestMarkAllPresentRoute:
    """Tests for POST /api/attendance/mark-all-present endpoint."""

    def test_mark_all_present_success(self, bulk_setup):
        """Test successful mark all present via API."""
        s = bulk_setup
        today = date.today().isoformat()

        response = s["test_client"].post(
            "/api/attendance/mark-all-present",
            params={
                "client_id": s["client"].client_id,
                "shift_id": s["shift"].shift_id,
                "shift_date": today,
            },
            headers=s["admin_headers"],
        )

        assert response.status_code == 201
        data = response.json()
        assert data["total_employees"] == 5
        assert data["records_created"] == 5
        assert data["already_exists"] == 0

    def test_mark_all_present_auth_required(self, bulk_setup):
        """Test that 401 is returned without authentication."""
        s = bulk_setup

        response = s["test_client"].post(
            "/api/attendance/mark-all-present",
            params={
                "client_id": s["client"].client_id,
                "shift_id": s["shift"].shift_id,
                "shift_date": date.today().isoformat(),
            },
        )

        assert response.status_code == 401

    def test_mark_all_present_invalid_shift(self, bulk_setup):
        """Test mark all present with non-existent shift returns 404."""
        s = bulk_setup

        response = s["test_client"].post(
            "/api/attendance/mark-all-present",
            params={
                "client_id": s["client"].client_id,
                "shift_id": 99999,
                "shift_date": date.today().isoformat(),
            },
            headers=s["admin_headers"],
        )

        assert response.status_code == 404

    def test_mark_all_present_idempotent(self, bulk_setup):
        """Test calling mark all present twice does not create duplicates."""
        s = bulk_setup
        today = date.today().isoformat()
        params = {
            "client_id": s["client"].client_id,
            "shift_id": s["shift"].shift_id,
            "shift_date": today,
        }

        # First call
        r1 = s["test_client"].post(
            "/api/attendance/mark-all-present",
            params=params,
            headers=s["admin_headers"],
        )
        assert r1.status_code == 201
        assert r1.json()["records_created"] == 5

        # Second call
        r2 = s["test_client"].post(
            "/api/attendance/mark-all-present",
            params=params,
            headers=s["admin_headers"],
        )
        assert r2.status_code == 201
        assert r2.json()["records_created"] == 0
        assert r2.json()["already_exists"] == 5

    def test_mark_all_present_operator_own_client(self, bulk_setup):
        """Test operator can mark present for their own client."""
        s = bulk_setup

        response = s["test_client"].post(
            "/api/attendance/mark-all-present",
            params={
                "client_id": s["client"].client_id,
                "shift_id": s["shift"].shift_id,
                "shift_date": date.today().isoformat(),
            },
            headers=s["operator_headers"],
        )

        assert response.status_code == 201
        assert response.json()["records_created"] == 5

    def test_mark_all_present_operator_other_client_denied(self, bulk_setup):
        """Test operator is denied access to another client."""
        s = bulk_setup

        # Create another client with its own shift
        TestDataFactory.create_client(s["db"], client_id="BULK-OTHER-RT", client_name="Other RT")
        other_shift = TestDataFactory.create_shift(s["db"], client_id="BULK-OTHER-RT", shift_name="Other Day Shift")
        s["db"].commit()

        response = s["test_client"].post(
            "/api/attendance/mark-all-present",
            params={
                "client_id": "BULK-OTHER-RT",
                "shift_id": other_shift.shift_id,
                "shift_date": date.today().isoformat(),
            },
            headers=s["operator_headers"],
        )

        assert response.status_code == 403

    def test_mark_all_present_missing_params(self, bulk_setup):
        """Test mark all present with missing required params returns 422."""
        s = bulk_setup

        response = s["test_client"].post(
            "/api/attendance/mark-all-present",
            params={"client_id": s["client"].client_id},
            headers=s["admin_headers"],
        )

        assert response.status_code == 422
