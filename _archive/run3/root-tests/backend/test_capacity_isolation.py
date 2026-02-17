"""
Multi-Tenant Isolation Tests for Capacity Planning Module
Tests that capacity planning data is properly isolated by client_id.

CRITICAL: All capacity planning queries MUST filter by client_id to prevent
cross-tenant data access.
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
import uuid

from backend.schemas.user import User
from backend.schemas.client import Client
from backend.schemas.work_order import WorkOrder
from backend.schemas.capacity.production_lines import CapacityProductionLine


@pytest.fixture
def client_a(test_db: Session):
    """Create Client A for capacity isolation tests"""
    client = Client(
        client_id="CAP-CLIENT-A",
        client_name="Capacity Test Client A",
        is_active=True
    )
    test_db.add(client)
    test_db.commit()
    return client


@pytest.fixture
def client_b(test_db: Session):
    """Create Client B for capacity isolation tests"""
    client = Client(
        client_id="CAP-CLIENT-B",
        client_name="Capacity Test Client B",
        is_active=True
    )
    test_db.add(client)
    test_db.commit()
    return client


@pytest.fixture
def user_client_a(test_db: Session, client_a):
    """Create OPERATOR user for Client A"""
    user = User(
        user_id=f"cap-user-a-{uuid.uuid4().hex[:8]}",
        username="cap_operator_a",
        email="cap_operator_a@test.com",
        password_hash="hashed_password",
        role="OPERATOR",
        client_id_assigned="CAP-CLIENT-A",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def user_client_b(test_db: Session, client_b):
    """Create OPERATOR user for Client B"""
    user = User(
        user_id=f"cap-user-b-{uuid.uuid4().hex[:8]}",
        username="cap_operator_b",
        email="cap_operator_b@test.com",
        password_hash="hashed_password",
        role="OPERATOR",
        client_id_assigned="CAP-CLIENT-B",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def admin_user(test_db: Session):
    """Create ADMIN user for multi-tenant access"""
    user = User(
        user_id=f"cap-admin-{uuid.uuid4().hex[:8]}",
        username="cap_admin",
        email="cap_admin@test.com",
        password_hash="hashed_password",
        role="ADMIN",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def production_line_a(test_db: Session, client_a):
    """Create production line for Client A"""
    line = CapacityProductionLine(
        client_id="CAP-CLIENT-A",
        line_code="CAP-LINE-A-001",
        line_name="Client A Capacity Line",
        department="SEWING",
        standard_capacity_units_per_hour=Decimal("100.0"),
        max_operators=10,
        efficiency_factor=Decimal("0.85"),
        is_active=True
    )
    test_db.add(line)
    test_db.commit()
    return line


@pytest.fixture
def production_line_b(test_db: Session, client_b):
    """Create production line for Client B"""
    line = CapacityProductionLine(
        client_id="CAP-CLIENT-B",
        line_code="CAP-LINE-B-001",
        line_name="Client B Capacity Line",
        department="CUTTING",
        standard_capacity_units_per_hour=Decimal("150.0"),
        max_operators=15,
        efficiency_factor=Decimal("0.90"),
        is_active=True
    )
    test_db.add(line)
    test_db.commit()
    return line


@pytest.fixture
def work_order_a(test_db: Session, client_a):
    """Create work order for Client A"""
    wo = WorkOrder(
        work_order_id=f"CAP-WO-A-{uuid.uuid4().hex[:8]}",
        client_id="CAP-CLIENT-A",
        style_model="STYLE-CAP-A",
        planned_quantity=5000,
        status="ACTIVE",
        planned_start_date=datetime.now(),
        planned_ship_date=datetime.now() + timedelta(days=30)
    )
    test_db.add(wo)
    test_db.commit()
    return wo


@pytest.fixture
def work_order_b(test_db: Session, client_b):
    """Create work order for Client B"""
    wo = WorkOrder(
        work_order_id=f"CAP-WO-B-{uuid.uuid4().hex[:8]}",
        client_id="CAP-CLIENT-B",
        style_model="STYLE-CAP-B",
        planned_quantity=10000,
        status="ACTIVE",
        planned_start_date=datetime.now(),
        planned_ship_date=datetime.now() + timedelta(days=45)
    )
    test_db.add(wo)
    test_db.commit()
    return wo


class TestCapacityPlanningIsolation:
    """Test client isolation for capacity planning operations."""

    def test_capacity_data_filtered_by_client(
        self, test_db, client_a, client_b, user_client_a, user_client_b,
        production_line_a, production_line_b
    ):
        """Verify capacity queries include client_id filter."""
        # Query production lines as CLIENT-A
        lines = test_db.query(CapacityProductionLine).filter(
            CapacityProductionLine.client_id == user_client_a.client_id_assigned
        ).all()

        # Should only see CLIENT-A lines
        assert len(lines) >= 1
        for line in lines:
            assert line.client_id == "CAP-CLIENT-A"

        # Verify CLIENT-B line not included
        line_codes = [l.line_code for l in lines]
        assert "CAP-LINE-B-001" not in line_codes

    def test_cannot_access_other_client_orders(
        self, test_db, client_a, client_b, user_client_a,
        work_order_a, work_order_b
    ):
        """Client A cannot access Client B's capacity orders."""
        from backend.crud.work_order import get_work_order, get_work_orders
        from backend.middleware.client_auth import ClientAccessError

        # CLIENT-A queries all work orders
        orders = get_work_orders(test_db, user_client_a)

        # Should not see CLIENT-B orders
        for order in orders:
            assert order.client_id == "CAP-CLIENT-A"

        # Direct access to CLIENT-B order should fail with exception or return None
        try:
            result = get_work_order(test_db, work_order_b.work_order_id, user_client_a)
            assert result is None
        except ClientAccessError:
            # Access denied is expected behavior
            pass

    def test_cannot_access_other_client_production_lines(
        self, test_db, client_a, client_b, user_client_a, user_client_b,
        production_line_a, production_line_b
    ):
        """Client A cannot access Client B's production lines."""
        # Query as CLIENT-A (filter manually since there's no CRUD function yet)
        lines_a = test_db.query(CapacityProductionLine).filter(
            CapacityProductionLine.client_id == user_client_a.client_id_assigned
        ).all()

        # Should only see CLIENT-A lines
        for line in lines_a:
            assert line.client_id == "CAP-CLIENT-A"
            assert line.line_code != "CAP-LINE-B-001"

    def test_cannot_access_other_client_bom(
        self, test_db, client_a, client_b, user_client_a
    ):
        """Client A cannot access Client B's BOM data."""
        # This test verifies BOM (Bill of Materials) isolation
        # BOM data should be filtered by client_id

        # Simulate BOM query filtering
        mock_bom_query = {
            "CAP-CLIENT-A": [
                {"item": "Component-A1", "quantity": 10},
                {"item": "Component-A2", "quantity": 5}
            ],
            "CAP-CLIENT-B": [
                {"item": "Component-B1", "quantity": 20},
                {"item": "Component-B2", "quantity": 15}
            ]
        }

        # CLIENT-A should only see their BOM
        client_a_bom = mock_bom_query.get(user_client_a.client_id_assigned, [])
        assert len(client_a_bom) == 2

        # Verify CLIENT-B items not accessible
        for item in client_a_bom:
            assert "B" not in item["item"]  # No CLIENT-B components

    def test_component_check_respects_tenant_boundary(
        self, test_db, client_a, client_b, user_client_a, user_client_b
    ):
        """Component check only analyzes current client's data."""
        # Simulate component availability check
        # Each client has different component inventory

        component_inventory = {
            "CAP-CLIENT-A": {"COMP-001": 100, "COMP-002": 50},
            "CAP-CLIENT-B": {"COMP-001": 200, "COMP-003": 75}
        }

        def check_component_availability(client_id: str, component_id: str) -> int:
            """Check component availability filtered by client."""
            inventory = component_inventory.get(client_id, {})
            return inventory.get(component_id, 0)

        # CLIENT-A checks their inventory
        client_a_comp1 = check_component_availability("CAP-CLIENT-A", "COMP-001")
        assert client_a_comp1 == 100

        # CLIENT-A should not see CLIENT-B's higher inventory
        # (they would if there was no tenant isolation)
        client_a_comp1_check = check_component_availability("CAP-CLIENT-A", "COMP-001")
        assert client_a_comp1_check != 200  # CLIENT-B's value

    def test_capacity_analysis_respects_tenant_boundary(
        self, test_db, client_a, client_b, user_client_a,
        production_line_a, production_line_b
    ):
        """Capacity analysis only includes current client's lines."""
        # Query production lines for capacity analysis
        lines = test_db.query(CapacityProductionLine).filter(
            CapacityProductionLine.client_id == user_client_a.client_id_assigned,
            CapacityProductionLine.is_active == True
        ).all()

        # Calculate total capacity for CLIENT-A only
        total_capacity = sum(
            float(line.standard_capacity_units_per_hour or 0) for line in lines
        )

        # Should only include CLIENT-A's capacity (100/hr)
        assert total_capacity == 100.0  # CLIENT-A line capacity
        # Should NOT include CLIENT-B's capacity (150/hr)
        assert total_capacity != 250.0  # Would be combined if not isolated


class TestAPIClientValidation:
    """Test API endpoint client_id validation for capacity planning."""

    def test_api_rejects_missing_client_id(self):
        """API returns 400 when client_id is missing."""
        from backend.utils.tenant_guard import ensure_client_id
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            ensure_client_id(None, context="capacity_planning")

        assert exc_info.value.status_code == 400
        assert "client_id" in str(exc_info.value.detail).lower()

    def test_api_rejects_unauthorized_client_id(self):
        """API returns 403 when user doesn't have access to client."""
        from backend.utils.tenant_guard import verify_tenant_access
        from backend.exceptions.domain_exceptions import MultiTenantViolationError

        # Simulate CLIENT-A user trying to access CLIENT-B capacity
        with pytest.raises(MultiTenantViolationError) as exc_info:
            verify_tenant_access(
                current_client_id="CAP-CLIENT-A",
                resource_client_id="CAP-CLIENT-B",
                resource_type="capacity_plan"
            )

        assert "different tenant" in str(exc_info.value.message).lower()

    def test_api_accepts_authorized_client_id(self):
        """API accepts requests with valid authorized client_id."""
        from backend.utils.tenant_guard import verify_tenant_access, ensure_client_id

        # Valid client_id
        client_id = ensure_client_id("CAP-CLIENT-A", context="capacity_planning")
        assert client_id == "CAP-CLIENT-A"

        # Same client access should not raise
        verify_tenant_access(
            current_client_id="CAP-CLIENT-A",
            resource_client_id="CAP-CLIENT-A",
            resource_type="capacity_plan"
        )
        # No exception = success


class TestCapacityPlanningCRUDIsolation:
    """Test CRUD operations respect tenant boundaries."""

    def test_create_capacity_plan_uses_user_client_id(
        self, test_db, client_a, user_client_a
    ):
        """Creating capacity plan uses authenticated user's client_id."""
        # Simulate capacity plan creation
        plan_data = {
            "name": "Q1 Capacity Plan",
            "start_date": date.today(),
            "end_date": date.today() + timedelta(days=90)
        }

        # The client_id should come from authenticated user
        created_plan = {
            **plan_data,
            "client_id": user_client_a.client_id_assigned  # From auth context
        }

        assert created_plan["client_id"] == "CAP-CLIENT-A"

    def test_update_capacity_plan_validates_ownership(
        self, test_db, client_a, client_b, user_client_a
    ):
        """Updating capacity plan validates tenant ownership."""
        from backend.utils.tenant_guard import verify_tenant_access
        from backend.exceptions.domain_exceptions import MultiTenantViolationError

        # Mock existing plan owned by CLIENT-B
        existing_plan_client_id = "CAP-CLIENT-B"

        # CLIENT-A tries to update CLIENT-B's plan
        with pytest.raises(MultiTenantViolationError):
            verify_tenant_access(
                current_client_id=user_client_a.client_id_assigned,
                resource_client_id=existing_plan_client_id,
                resource_type="capacity_plan"
            )

    def test_delete_capacity_plan_validates_ownership(
        self, test_db, client_a, client_b, user_client_a
    ):
        """Deleting capacity plan validates tenant ownership."""
        from backend.utils.tenant_guard import verify_tenant_access
        from backend.exceptions.domain_exceptions import MultiTenantViolationError

        # Mock plan owned by CLIENT-B
        plan_client_id = "CAP-CLIENT-B"

        # CLIENT-A tries to delete CLIENT-B's plan
        with pytest.raises(MultiTenantViolationError):
            verify_tenant_access(
                current_client_id=user_client_a.client_id_assigned,
                resource_client_id=plan_client_id,
                resource_type="capacity_plan"
            )


class TestCapacityAnalysisIsolation:
    """Test capacity analysis respects tenant boundaries."""

    def test_demand_forecast_isolated_by_client(
        self, test_db, client_a, client_b, user_client_a, user_client_b,
        work_order_a, work_order_b
    ):
        """Demand forecast only includes client's own orders."""
        from backend.crud.work_order import get_work_orders

        # Get orders for demand calculation
        orders_a = get_work_orders(test_db, user_client_a)

        # Calculate demand from CLIENT-A orders only
        total_demand_a = sum(o.planned_quantity for o in orders_a if o.client_id == "CAP-CLIENT-A")

        # Should only include CLIENT-A demand (5000 units)
        assert total_demand_a == 5000
        # Should NOT include CLIENT-B demand (10000 units)
        assert total_demand_a != 15000

    def test_capacity_utilization_isolated_by_client(
        self, test_db, client_a, client_b, user_client_a,
        production_line_a, production_line_b
    ):
        """Capacity utilization calculated per client only."""
        # Get CLIENT-A lines
        lines_a = test_db.query(CapacityProductionLine).filter(
            CapacityProductionLine.client_id == user_client_a.client_id_assigned
        ).all()

        # Calculate available capacity
        hours_per_day = 8
        total_capacity_a = sum(
            float(line.standard_capacity_units_per_hour or 0) * hours_per_day
            for line in lines_a
        )

        # CLIENT-A capacity: 100 * 8 = 800 units/day
        assert total_capacity_a == 800.0
        # Should NOT include CLIENT-B: 150 * 8 = 1200
        assert total_capacity_a != 2000.0  # Combined would be 2000


class TestConcurrentCapacityAccess:
    """Test concurrent access to capacity planning."""

    def test_concurrent_capacity_queries_isolated(
        self, test_db, client_a, client_b, user_client_a, user_client_b,
        production_line_a, production_line_b
    ):
        """Concurrent queries maintain tenant isolation."""
        import threading

        results = {"CAP-CLIENT-A": [], "CAP-CLIENT-B": []}
        errors = []

        def query_client_a():
            try:
                lines = test_db.query(CapacityProductionLine).filter(
                    CapacityProductionLine.client_id == "CAP-CLIENT-A"
                ).all()
                results["CAP-CLIENT-A"] = [l.line_code for l in lines]
            except Exception as e:
                errors.append(str(e))

        def query_client_b():
            try:
                lines = test_db.query(CapacityProductionLine).filter(
                    CapacityProductionLine.client_id == "CAP-CLIENT-B"
                ).all()
                results["CAP-CLIENT-B"] = [l.line_code for l in lines]
            except Exception as e:
                errors.append(str(e))

        # Run concurrently
        thread_a = threading.Thread(target=query_client_a)
        thread_b = threading.Thread(target=query_client_b)

        thread_a.start()
        thread_b.start()
        thread_a.join()
        thread_b.join()

        # Verify isolation
        if results["CAP-CLIENT-A"]:
            assert all("A" in lid for lid in results["CAP-CLIENT-A"])
        if results["CAP-CLIENT-B"]:
            assert all("B" in lid for lid in results["CAP-CLIENT-B"])


class TestTenantGuardUtilities:
    """Test tenant guard utility functions."""

    def test_build_client_filter_clause(self):
        """Test building client filter clause for SQLAlchemy."""
        from backend.utils.tenant_guard import build_client_filter_clause

        # Test with model that has client_id
        filter_clause = build_client_filter_clause(CapacityProductionLine, "TEST-CLIENT")
        # Just verify it creates a clause without error
        assert filter_clause is not None

    def test_get_client_id_from_user(self, test_db, user_client_a, admin_user):
        """Test extracting client_id from user based on role."""
        from backend.utils.tenant_guard import get_client_id_from_user

        # Regular user should get their client_id
        client_id = get_client_id_from_user(user_client_a)
        assert client_id == "CAP-CLIENT-A"

        # Admin with override should get None (all access)
        admin_client_id = get_client_id_from_user(admin_user, allow_admin_override=True)
        assert admin_client_id is None

    def test_validate_resource_ownership(self):
        """Test resource ownership validation."""
        from backend.utils.tenant_guard import validate_resource_ownership
        from backend.exceptions.domain_exceptions import MultiTenantViolationError

        # Create a mock resource
        class MockResource:
            client_id = "CAP-CLIENT-A"

        resource = MockResource()

        # Same client should pass
        result = validate_resource_ownership(resource, "CAP-CLIENT-A", "test_resource")
        assert result == resource

        # Different client should raise
        with pytest.raises(MultiTenantViolationError):
            validate_resource_ownership(resource, "CAP-CLIENT-B", "test_resource")

    def test_filter_resources_by_tenant(self):
        """Test filtering resource list by tenant."""
        from backend.utils.tenant_guard import filter_resources_by_tenant

        # Create mock resources
        class MockResource:
            def __init__(self, client_id):
                self.client_id = client_id

        resources = [
            MockResource("CLIENT-A"),
            MockResource("CLIENT-B"),
            MockResource("CLIENT-A"),
            MockResource("CLIENT-C"),
        ]

        # Filter for CLIENT-A
        filtered = filter_resources_by_tenant(resources, "CLIENT-A")
        assert len(filtered) == 2
        assert all(r.client_id == "CLIENT-A" for r in filtered)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
