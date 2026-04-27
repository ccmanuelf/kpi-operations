"""
Tests for Employee Line Assignment API routes.
Uses real in-memory SQLite database -- NO mocks for DB layer.
Follows the pattern from test_shift_routes.py.
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI

from backend.database import Base, get_db
from backend.auth.jwt import get_current_user, get_current_active_supervisor
from backend.orm.user import User, UserRole
from backend.orm.employee import Employee
from backend.orm.production_line import ProductionLine
from backend.orm.employee_line_assignment import EmployeeLineAssignment
from backend.routes.employee_line_assignments import router as ela_router
from backend.tests.fixtures.factories import TestDataFactory


# =============================================================================
# Test App Factory and Fixtures
# =============================================================================
CLIENT_ID = "ELA-RT-C1"
CLIENT_ID_B = "ELA-RT-C2"
TODAY = date.today().isoformat()


def _create_test_app(db_session, role="supervisor"):
    """Create a FastAPI test app with overridden dependencies."""
    app = FastAPI()
    app.include_router(ela_router)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    mock_user = User(
        user_id=f"test-ela-{role}-001",
        username=f"ela_test_{role}",
        email=f"ela_{role}@test.com",
        role=role,
        client_id_assigned=CLIENT_ID if role != "admin" else None,
        is_active=True,
    )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: mock_user

    if role in ("supervisor", "admin"):
        app.dependency_overrides[get_current_active_supervisor] = lambda: mock_user

    return app


@pytest.fixture(scope="function")
def ela_db():
    """Create a fresh in-memory database for each test."""
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
def supervisor_client(ela_db):
    """TestClient authenticated as supervisor."""
    TestDataFactory.create_client(ela_db, client_id=CLIENT_ID, client_name="ELA Route Test Client")
    ela_db.commit()
    app = _create_test_app(ela_db, role="supervisor")
    return TestClient(app), ela_db


@pytest.fixture
def admin_client(ela_db):
    """TestClient authenticated as admin."""
    TestDataFactory.create_client(ela_db, client_id=CLIENT_ID, client_name="ELA Route Test Client")
    ela_db.commit()
    app = _create_test_app(ela_db, role="admin")
    return TestClient(app), ela_db


@pytest.fixture
def operator_client(ela_db):
    """TestClient authenticated as operator (no write access)."""
    TestDataFactory.create_client(ela_db, client_id=CLIENT_ID, client_name="ELA Route Test Client")
    ela_db.commit()
    app = _create_test_app(ela_db, role="operator")
    return TestClient(app), ela_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _seed_employee(db, client_id=CLIENT_ID, **kwargs):
    """Create an employee in the test DB."""
    emp = TestDataFactory.create_employee(db, client_id=client_id, **kwargs)
    db.commit()
    return emp


def _seed_line(db, client_id=CLIENT_ID, line_code=None, line_name=None):
    """Create a production line in the test DB."""
    if line_code is None:
        line_code = TestDataFactory._next_id("LINE")
    if line_name is None:
        line_name = f"Test Line {line_code}"
    line = ProductionLine(
        client_id=client_id,
        line_code=line_code,
        line_name=line_name,
        line_type="DEDICATED",
        is_active=True,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def _create_assignment_payload(
    employee_id, line_id, client_id=CLIENT_ID, allocation="100.00", is_primary=True, effective_date=None
):
    """Build a JSON payload for POST /api/employee-line-assignments/."""
    return {
        "employee_id": employee_id,
        "line_id": line_id,
        "client_id": client_id,
        "allocation_percentage": allocation,
        "is_primary": is_primary,
        "effective_date": effective_date or TODAY,
    }


def _create_assignment_via_api(client, db, employee_id, line_id, **kwargs):
    """Helper to create an assignment via API and return response data."""
    payload = _create_assignment_payload(employee_id, line_id, **kwargs)
    response = client.post("/api/employee-line-assignments/", json=payload)
    assert response.status_code == 201, f"Expected 201 but got {response.status_code}: {response.text}"
    return response.json()


# ============================================================================
# TestListEndpoint
# ============================================================================
class TestListEndpoint:
    """Tests for GET /api/employee-line-assignments/"""

    def test_list_empty(self, supervisor_client):
        """List returns empty array when no assignments exist."""
        client, db = supervisor_client
        response = client.get("/api/employee-line-assignments/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_employee_filter(self, supervisor_client):
        """List filtered by employee_id."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line = _seed_line(db)
        _create_assignment_via_api(client, db, emp.employee_id, line.line_id)

        response = client.get(
            "/api/employee-line-assignments/",
            params={"employee_id": emp.employee_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["employee_id"] == emp.employee_id

    def test_list_with_client_filter(self, supervisor_client):
        """List filtered by client_id."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line = _seed_line(db)
        _create_assignment_via_api(client, db, emp.employee_id, line.line_id)

        response = client.get(
            "/api/employee-line-assignments/",
            params={"client_id": CLIENT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["client_id"] == CLIENT_ID

    def test_list_active_only_default(self, supervisor_client):
        """active_only defaults to True, hiding ended assignments."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line = _seed_line(db)
        created = _create_assignment_via_api(client, db, emp.employee_id, line.line_id)

        # End it via DELETE
        client.delete(f"/api/employee-line-assignments/{created['assignment_id']}")

        response = client.get("/api/employee-line-assignments/")
        assert response.status_code == 200
        assert len(response.json()) == 0

    def test_list_include_inactive(self, supervisor_client):
        """active_only=False includes ended assignments."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line = _seed_line(db)
        created = _create_assignment_via_api(client, db, emp.employee_id, line.line_id)

        # End it
        client.delete(f"/api/employee-line-assignments/{created['assignment_id']}")

        response = client.get(
            "/api/employee-line-assignments/",
            params={"active_only": False},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1


# ============================================================================
# TestGetEmployeeLinesEndpoint
# ============================================================================
class TestGetEmployeeLinesEndpoint:
    """Tests for GET /api/employee-line-assignments/employee/{employee_id}"""

    def test_get_employee_lines(self, supervisor_client):
        """Returns active lines for an employee."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")

        _create_assignment_via_api(
            client,
            db,
            emp.employee_id,
            line1.line_id,
            allocation="60.00",
        )
        _create_assignment_via_api(
            client,
            db,
            emp.employee_id,
            line2.line_id,
            allocation="40.00",
            is_primary=False,
        )

        response = client.get(
            f"/api/employee-line-assignments/employee/{emp.employee_id}",
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        # Primary first
        assert data[0]["is_primary"] is True

    def test_get_employee_lines_empty(self, supervisor_client):
        """Returns empty for employee with no assignments."""
        client, db = supervisor_client
        emp = _seed_employee(db)

        response = client.get(
            f"/api/employee-line-assignments/employee/{emp.employee_id}",
        )
        assert response.status_code == 200
        assert response.json() == []


# ============================================================================
# TestGetLineEmployeesEndpoint
# ============================================================================
class TestGetLineEmployeesEndpoint:
    """Tests for GET /api/employee-line-assignments/line/{line_id}"""

    def test_get_line_employees(self, supervisor_client):
        """Returns employees assigned to a line."""
        client, db = supervisor_client
        emp1 = _seed_employee(db, employee_code="E1")
        emp2 = _seed_employee(db, employee_code="E2")
        line = _seed_line(db)

        _create_assignment_via_api(client, db, emp1.employee_id, line.line_id)
        _create_assignment_via_api(client, db, emp2.employee_id, line.line_id)

        response = client.get(
            f"/api/employee-line-assignments/line/{line.line_id}",
            params={"client_id": CLIENT_ID},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_line_employees_requires_client_id(self, supervisor_client):
        """client_id is required for the line employees endpoint."""
        client, db = supervisor_client
        response = client.get("/api/employee-line-assignments/line/1")
        assert response.status_code == 422  # Missing required query param


# ============================================================================
# TestCreateEndpoint
# ============================================================================
class TestCreateEndpoint:
    """Tests for POST /api/employee-line-assignments/"""

    def test_create_as_supervisor(self, supervisor_client):
        """Supervisor can create an assignment."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line = _seed_line(db)

        payload = _create_assignment_payload(emp.employee_id, line.line_id)
        response = client.post("/api/employee-line-assignments/", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["employee_id"] == emp.employee_id
        assert data["line_id"] == line.line_id
        assert data["allocation_percentage"] == "100.00"
        assert data["is_primary"] is True
        assert "assignment_id" in data
        assert "created_at" in data

    def test_create_as_admin(self, admin_client):
        """Admin can create an assignment."""
        client, db = admin_client
        emp = _seed_employee(db)
        line = _seed_line(db)

        payload = _create_assignment_payload(emp.employee_id, line.line_id)
        response = client.post("/api/employee-line-assignments/", json=payload)
        assert response.status_code == 201

    def test_create_as_operator_forbidden(self, operator_client):
        """Operator cannot create an assignment."""
        client, db = operator_client
        emp = _seed_employee(db)
        line = _seed_line(db)

        payload = _create_assignment_payload(emp.employee_id, line.line_id)
        response = client.post("/api/employee-line-assignments/", json=payload)
        # Without supervisor dependency override, returns 403 or 500
        assert response.status_code in (403, 500)

    def test_create_duplicate_returns_409(self, supervisor_client):
        """Duplicate assignment returns 409 Conflict."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line = _seed_line(db)

        payload = _create_assignment_payload(
            emp.employee_id,
            line.line_id,
            allocation="50.00",
        )
        response1 = client.post("/api/employee-line-assignments/", json=payload)
        assert response1.status_code == 201

        response2 = client.post("/api/employee-line-assignments/", json=payload)
        assert response2.status_code == 409
        assert "Duplicate" in response2.json()["detail"]

    def test_create_exceeds_allocation_returns_422(self, supervisor_client):
        """Total allocation > 100% returns 422."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")

        _create_assignment_via_api(
            client,
            db,
            emp.employee_id,
            line1.line_id,
            allocation="70.00",
        )

        payload = _create_assignment_payload(
            emp.employee_id,
            line2.line_id,
            allocation="40.00",
            is_primary=False,
        )
        response = client.post("/api/employee-line-assignments/", json=payload)
        assert response.status_code == 422
        assert "100%" in response.json()["detail"]

    def test_create_max_assignments_returns_422(self, supervisor_client):
        """Third assignment returns 422."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")
        line3 = _seed_line(db, line_code="L3")

        _create_assignment_via_api(
            client,
            db,
            emp.employee_id,
            line1.line_id,
            allocation="50.00",
        )
        _create_assignment_via_api(
            client,
            db,
            emp.employee_id,
            line2.line_id,
            allocation="50.00",
            is_primary=False,
        )

        payload = _create_assignment_payload(
            emp.employee_id,
            line3.line_id,
            allocation="10.00",
            is_primary=False,
        )
        response = client.post("/api/employee-line-assignments/", json=payload)
        assert response.status_code == 422
        assert "Maximum 2" in response.json()["detail"]

    def test_create_employee_not_found_returns_422(self, supervisor_client):
        """Non-existent employee returns 422."""
        client, db = supervisor_client
        line = _seed_line(db)

        payload = _create_assignment_payload(99999, line.line_id)
        response = client.post("/api/employee-line-assignments/", json=payload)
        assert response.status_code == 422
        assert "not found" in response.json()["detail"]

    def test_create_validation_error_missing_fields(self, supervisor_client):
        """Missing required fields returns 422."""
        client, db = supervisor_client
        response = client.post(
            "/api/employee-line-assignments/",
            json={"employee_id": 1},  # Missing line_id, client_id, effective_date
        )
        assert response.status_code == 422


# ============================================================================
# TestUpdateEndpoint
# ============================================================================
class TestUpdateEndpoint:
    """Tests for PUT /api/employee-line-assignments/{assignment_id}"""

    def test_update_allocation(self, supervisor_client):
        """Supervisor can update allocation percentage."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line = _seed_line(db)
        created = _create_assignment_via_api(client, db, emp.employee_id, line.line_id)

        response = client.put(
            f"/api/employee-line-assignments/{created['assignment_id']}",
            json={"allocation_percentage": "80.00"},
        )
        assert response.status_code == 200
        assert response.json()["allocation_percentage"] == "80.00"

    def test_update_is_primary(self, supervisor_client):
        """Update is_primary flag."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line = _seed_line(db)
        created = _create_assignment_via_api(client, db, emp.employee_id, line.line_id)

        response = client.put(
            f"/api/employee-line-assignments/{created['assignment_id']}",
            json={"is_primary": False},
        )
        assert response.status_code == 200
        assert response.json()["is_primary"] is False

    def test_update_nonexistent_returns_404(self, supervisor_client):
        """Updating non-existent assignment returns 404."""
        client, db = supervisor_client
        response = client.put(
            "/api/employee-line-assignments/999999",
            json={"is_primary": False},
        )
        assert response.status_code == 404

    def test_update_allocation_exceeds_100_returns_422(self, supervisor_client):
        """Updating allocation to exceed 100% returns 422."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line1 = _seed_line(db, line_code="L1")
        line2 = _seed_line(db, line_code="L2")

        _create_assignment_via_api(
            client,
            db,
            emp.employee_id,
            line1.line_id,
            allocation="60.00",
        )
        a2 = _create_assignment_via_api(
            client,
            db,
            emp.employee_id,
            line2.line_id,
            allocation="40.00",
            is_primary=False,
        )

        response = client.put(
            f"/api/employee-line-assignments/{a2['assignment_id']}",
            json={"allocation_percentage": "50.00"},
        )
        assert response.status_code == 422
        assert "100%" in response.json()["detail"]


# ============================================================================
# TestDeleteEndpoint (End Assignment)
# ============================================================================
class TestDeleteEndpoint:
    """Tests for DELETE /api/employee-line-assignments/{assignment_id}"""

    def test_delete_ends_assignment(self, supervisor_client):
        """DELETE sets end_date to today and returns the assignment."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line = _seed_line(db)
        created = _create_assignment_via_api(client, db, emp.employee_id, line.line_id)

        response = client.delete(
            f"/api/employee-line-assignments/{created['assignment_id']}",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["end_date"] == date.today().isoformat()
        assert data["assignment_id"] == created["assignment_id"]

    def test_delete_nonexistent_returns_404(self, supervisor_client):
        """Deleting non-existent assignment returns 404."""
        client, db = supervisor_client
        response = client.delete("/api/employee-line-assignments/999999")
        assert response.status_code == 404

    def test_delete_makes_assignment_inactive(self, supervisor_client):
        """After DELETE, the assignment no longer appears in active list."""
        client, db = supervisor_client
        emp = _seed_employee(db)
        line = _seed_line(db)
        created = _create_assignment_via_api(client, db, emp.employee_id, line.line_id)

        client.delete(f"/api/employee-line-assignments/{created['assignment_id']}")

        # Verify not in active list
        response = client.get(
            f"/api/employee-line-assignments/employee/{emp.employee_id}",
        )
        assert response.status_code == 200
        assert len(response.json()) == 0


# ============================================================================
# TestRouteAuth
# ============================================================================
class TestRouteAuth:
    """Test route-level authentication requirements."""

    def test_read_endpoints_accessible_to_all_auth_users(self, operator_client):
        """GET endpoints are accessible to operators."""
        client, db = operator_client
        response = client.get("/api/employee-line-assignments/")
        assert response.status_code == 200

        response = client.get("/api/employee-line-assignments/employee/1")
        assert response.status_code == 200

        response = client.get(
            "/api/employee-line-assignments/line/1",
            params={"client_id": CLIENT_ID},
        )
        assert response.status_code == 200

    def test_write_endpoints_require_supervisor(self, operator_client):
        """POST/PUT/DELETE require supervisor role."""
        client, db = operator_client
        emp = _seed_employee(db)
        line = _seed_line(db)

        # POST
        payload = _create_assignment_payload(emp.employee_id, line.line_id)
        post_resp = client.post("/api/employee-line-assignments/", json=payload)
        assert post_resp.status_code in (403, 500)

        # PUT
        put_resp = client.put(
            "/api/employee-line-assignments/1",
            json={"is_primary": False},
        )
        assert put_resp.status_code in (403, 500)

        # DELETE
        del_resp = client.delete("/api/employee-line-assignments/1")
        assert del_resp.status_code in (403, 500)
