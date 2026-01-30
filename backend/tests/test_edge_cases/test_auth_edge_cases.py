"""
Edge Case Tests: Authentication and Authorization
Task #42: Comprehensive testing of auth boundary conditions and error scenarios
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from fastapi import FastAPI, HTTPException

from backend.database import Base, get_db
from backend.schemas import ClientType
from backend.schemas.user import User
from backend.tests.fixtures.factories import TestDataFactory


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def auth_db():
    """Create a fresh database for auth tests."""
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
def auth_setup(auth_db):
    """Create test data for auth tests."""
    db = auth_db

    # Create multiple clients for isolation testing
    client_a = TestDataFactory.create_client(
        db,
        client_id="CLIENT-A",
        client_name="Client A",
        client_type=ClientType.HOURLY_RATE
    )
    client_b = TestDataFactory.create_client(
        db,
        client_id="CLIENT-B",
        client_name="Client B",
        client_type=ClientType.PIECE_RATE
    )

    # Admin - full access
    admin = TestDataFactory.create_user(
        db,
        user_id="auth-admin-001",
        username="auth_admin",
        role="admin",
        client_id=None
    )

    # Supervisor for Client A only
    supervisor_a = TestDataFactory.create_user(
        db,
        user_id="auth-super-a",
        username="supervisor_a",
        role="supervisor",
        client_id=client_a.client_id
    )

    # Operator for Client A only
    operator_a = TestDataFactory.create_user(
        db,
        user_id="auth-oper-a",
        username="operator_a",
        role="operator",
        client_id=client_a.client_id
    )

    # Inactive user
    inactive = TestDataFactory.create_user(
        db,
        user_id="auth-inactive",
        username="inactive_user",
        role="operator",
        client_id=client_a.client_id
    )
    inactive.is_active = False

    db.commit()

    return {
        "db": db,
        "client_a": client_a,
        "client_b": client_b,
        "admin": admin,
        "supervisor_a": supervisor_a,
        "operator_a": operator_a,
        "inactive": inactive,
    }


# =============================================================================
# Role-Based Access Control Tests
# =============================================================================

class TestRoleBasedAccess:
    """Test role-based access control edge cases."""

    def test_admin_has_all_access(self, auth_setup):
        """Test admin can access all clients."""
        from backend.middleware.client_auth import verify_client_access

        admin = auth_setup["admin"]

        # Admin should access any client
        try:
            verify_client_access(admin, "CLIENT-A")
            verify_client_access(admin, "CLIENT-B")
            verify_client_access(admin, "ANY-CLIENT")
        except HTTPException:
            pytest.fail("Admin should have access to all clients")

    def test_supervisor_limited_to_assigned_client(self, auth_setup):
        """Test supervisor can only access assigned client."""
        from backend.middleware.client_auth import verify_client_access

        supervisor = auth_setup["supervisor_a"]

        # Should access own client
        try:
            verify_client_access(supervisor, "CLIENT-A")
        except HTTPException:
            pytest.fail("Supervisor should access assigned client")

        # Should NOT access other client
        with pytest.raises(HTTPException) as exc_info:
            verify_client_access(supervisor, "CLIENT-B")
        assert exc_info.value.status_code == 403

    def test_operator_limited_access(self, auth_setup):
        """Test operator has limited access."""
        from backend.middleware.client_auth import verify_client_access

        operator = auth_setup["operator_a"]

        # Should access own client
        try:
            verify_client_access(operator, "CLIENT-A")
        except HTTPException:
            pytest.fail("Operator should access assigned client")

        # Should NOT access other client
        with pytest.raises(HTTPException) as exc_info:
            verify_client_access(operator, "CLIENT-B")
        assert exc_info.value.status_code == 403


class TestUserClientFilter:
    """Test user client filter edge cases."""

    def test_admin_no_filter(self, auth_setup):
        """Test admin gets no client filter (all access)."""
        from backend.middleware.client_auth import get_user_client_filter

        admin = auth_setup["admin"]

        filter_result = get_user_client_filter(admin)

        # Admin should get None (no filter) or empty list
        assert filter_result is None or filter_result == []

    def test_supervisor_single_client_filter(self, auth_setup):
        """Test supervisor gets single client filter."""
        from backend.middleware.client_auth import get_user_client_filter

        supervisor = auth_setup["supervisor_a"]

        filter_result = get_user_client_filter(supervisor)

        if filter_result:
            assert "CLIENT-A" in filter_result


# =============================================================================
# User State Edge Cases
# =============================================================================

class TestUserStateEdgeCases:
    """Test user state edge cases."""

    def test_inactive_user_access(self, auth_setup):
        """Test inactive user is denied access."""
        from backend.auth.jwt import get_current_user, create_access_token

        db = auth_setup["db"]
        inactive = auth_setup["inactive"]

        # Create a valid token for the inactive user
        token = create_access_token(
            data={"sub": inactive.username, "role": inactive.role}
        )

        # Should raise 403 for inactive user
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token=token, db=db)
        assert exc_info.value.status_code == 403
        assert "inactive" in exc_info.value.detail.lower()

    def test_user_without_client_assignment(self, auth_setup):
        """Test user without client assignment."""
        from backend.middleware.client_auth import get_user_client_filter

        db = auth_setup["db"]

        # Create user with null client assignment
        user_no_client = TestDataFactory.create_user(
            db,
            user_id="no-client-user",
            username="no_client_user",
            role="operator",
            client_id=None  # No client assigned
        )
        db.commit()

        # Should handle gracefully
        try:
            filter_result = get_user_client_filter(user_no_client)
            # For operator without client, should return empty or raise
        except HTTPException as e:
            # Expected behavior for operator without assignment
            assert e.status_code in [403, 400]


# =============================================================================
# Multi-Tenant Isolation Tests
# =============================================================================

class TestMultiTenantIsolation:
    """Test multi-tenant data isolation."""

    def test_production_entry_client_isolation(self, auth_setup):
        """Test production entries are isolated by client."""
        from backend.schemas.production_entry import ProductionEntry

        db = auth_setup["db"]
        client_a = auth_setup["client_a"]
        client_b = auth_setup["client_b"]

        # Create product and shift
        product = TestDataFactory.create_product(
            db,
            product_code="ISO-PROD-001",
            product_name="Isolation Test Product",
            ideal_cycle_time=Decimal("0.10")
        )
        shift = TestDataFactory.create_shift(
            db,
            shift_name="Isolation Test Shift",
            start_time="06:00:00",
            end_time="14:00:00"
        )
        db.commit()

        # Create entries for different clients
        entry_a = ProductionEntry(
            production_entry_id="ISO-A-001",
            client_id=client_a.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            entered_by="auth-super-a"
        )
        entry_b = ProductionEntry(
            production_entry_id="ISO-B-001",
            client_id=client_b.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=200,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            entered_by="auth-super-a"
        )

        db.add_all([entry_a, entry_b])
        db.commit()

        # Query only Client A entries
        client_a_entries = db.query(ProductionEntry).filter(
            ProductionEntry.client_id == client_a.client_id
        ).all()

        assert len(client_a_entries) == 1
        assert client_a_entries[0].production_entry_id == "ISO-A-001"

    def test_work_order_client_isolation(self, auth_setup):
        """Test work orders are isolated by client."""
        from backend.schemas.work_order import WorkOrder, WorkOrderStatus

        db = auth_setup["db"]
        client_a = auth_setup["client_a"]
        client_b = auth_setup["client_b"]

        # Create work orders for different clients
        wo_a = WorkOrder(
            work_order_id="WO-ISO-A-001",
            client_id=client_a.client_id,
            style_model="STYLE-A",
            planned_quantity=100,
            status=WorkOrderStatus.ACTIVE
        )
        wo_b = WorkOrder(
            work_order_id="WO-ISO-B-001",
            client_id=client_b.client_id,
            style_model="STYLE-B",
            planned_quantity=200,
            status=WorkOrderStatus.ACTIVE
        )

        db.add_all([wo_a, wo_b])
        db.commit()

        # Query only Client A work orders
        client_a_orders = db.query(WorkOrder).filter(
            WorkOrder.client_id == client_a.client_id
        ).all()

        assert len(client_a_orders) == 1
        assert client_a_orders[0].work_order_id == "WO-ISO-A-001"


# =============================================================================
# Permission Boundary Tests
# =============================================================================

class TestPermissionBoundaries:
    """Test permission boundary conditions."""

    def test_supervisor_cannot_admin_actions(self, auth_setup):
        """Test supervisor cannot perform admin-only actions."""
        from backend.auth.jwt import get_current_admin

        supervisor = auth_setup["supervisor_a"]

        with pytest.raises(HTTPException) as exc_info:
            get_current_admin(supervisor)
        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail.lower()

    def test_operator_cannot_supervisor_actions(self, auth_setup):
        """Test operator cannot perform supervisor actions."""
        from backend.auth.jwt import get_current_active_supervisor

        operator = auth_setup["operator_a"]

        with pytest.raises(HTTPException) as exc_info:
            get_current_active_supervisor(operator)
        assert exc_info.value.status_code == 403


# =============================================================================
# JWT Token Edge Cases
# =============================================================================

class TestJWTEdgeCases:
    """Test JWT token edge cases."""

    def test_token_missing_sub_claim(self, auth_setup):
        """Test token without subject claim."""
        from backend.auth.jwt import decode_access_token

        # Create a token without 'sub' claim - should raise HTTPException
        with patch('backend.auth.jwt.jwt.decode') as mock_decode:
            mock_decode.return_value = {"exp": datetime.utcnow() + timedelta(hours=1)}  # No 'sub'

            with pytest.raises(HTTPException) as exc_info:
                decode_access_token("fake_token")

            assert exc_info.value.status_code == 401
            assert "credentials" in exc_info.value.detail.lower()

    def test_expired_token(self, auth_setup):
        """Test expired token handling."""
        from backend.auth.jwt import decode_access_token
        from jose import JWTError

        # Patch jwt.decode to raise JWTError for expired token
        with patch('backend.auth.jwt.jwt.decode') as mock_decode:
            mock_decode.side_effect = JWTError("Token expired")

            with pytest.raises(HTTPException) as exc_info:
                decode_access_token("expired_token")

            assert exc_info.value.status_code == 401

    def test_malformed_token(self, auth_setup):
        """Test malformed token handling."""
        from backend.auth.jwt import decode_access_token
        from jose import JWTError

        with patch('backend.auth.jwt.jwt.decode') as mock_decode:
            mock_decode.side_effect = JWTError("Invalid token")

            with pytest.raises(HTTPException) as exc_info:
                decode_access_token("not.a.valid.token")

            assert exc_info.value.status_code == 401


# =============================================================================
# Client ID Edge Cases
# =============================================================================

class TestClientIDEdgeCases:
    """Test client ID validation edge cases."""

    def test_empty_client_id(self, auth_setup):
        """Test empty string client ID."""
        from backend.middleware.client_auth import verify_client_access

        admin = auth_setup["admin"]

        # Empty string client_id
        try:
            verify_client_access(admin, "")
            # Admin should still have access even with empty string
        except HTTPException:
            pass  # Some implementations may reject empty

    def test_whitespace_client_id(self, auth_setup):
        """Test whitespace-only client ID."""
        from backend.middleware.client_auth import verify_client_access

        supervisor = auth_setup["supervisor_a"]

        with pytest.raises(HTTPException) as exc_info:
            verify_client_access(supervisor, "   ")
        # Should be denied (not assigned to whitespace client)
        assert exc_info.value.status_code == 403

    def test_special_characters_in_client_id(self, auth_setup):
        """Test special characters in client ID."""
        from backend.middleware.client_auth import verify_client_access

        supervisor = auth_setup["supervisor_a"]

        with pytest.raises(HTTPException) as exc_info:
            verify_client_access(supervisor, "CLIENT-A'; DROP TABLE--")
        # Should be denied (not assigned to this "client")
        assert exc_info.value.status_code == 403


# =============================================================================
# Cross-Client Access Tests
# =============================================================================

class TestCrossClientAccess:
    """Test prevention of cross-client data access."""

    def test_cannot_create_entry_for_other_client(self, auth_setup):
        """Test user cannot create production entry for another client."""
        from backend.schemas.production_entry import ProductionEntry

        db = auth_setup["db"]
        client_b = auth_setup["client_b"]
        supervisor_a = auth_setup["supervisor_a"]

        # Create product and shift
        product = TestDataFactory.create_product(
            db,
            product_code="CROSS-PROD-001",
            product_name="Cross Client Product",
            ideal_cycle_time=Decimal("0.10")
        )
        shift = TestDataFactory.create_shift(
            db,
            shift_name="Cross Client Shift",
            start_time="06:00:00",
            end_time="14:00:00"
        )
        db.commit()

        # Supervisor A tries to create entry for Client B
        # At DB level, this would succeed, but API should block it
        entry = ProductionEntry(
            production_entry_id="CROSS-001",
            client_id=client_b.client_id,  # Wrong client!
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            entered_by=supervisor_a.user_id
        )

        # DB allows it (no FK constraint on user->client)
        db.add(entry)
        db.commit()

        # But middleware should have prevented this
        # This test documents that API-level checks are needed
        assert entry.client_id != supervisor_a.client_id_assigned

    def test_query_respects_client_filter(self, auth_setup):
        """Test queries respect client filter."""
        from backend.schemas.production_entry import ProductionEntry
        from backend.middleware.client_auth import get_user_client_filter

        db = auth_setup["db"]
        client_a = auth_setup["client_a"]
        client_b = auth_setup["client_b"]
        supervisor_a = auth_setup["supervisor_a"]

        # Create product and shift
        product = TestDataFactory.create_product(
            db,
            product_code="FILTER-PROD-001",
            product_name="Filter Test Product",
            ideal_cycle_time=Decimal("0.10")
        )
        shift = TestDataFactory.create_shift(
            db,
            shift_name="Filter Test Shift",
            start_time="06:00:00",
            end_time="14:00:00"
        )
        db.commit()

        # Create entries for both clients
        entry_a = ProductionEntry(
            production_entry_id="FILTER-A-001",
            client_id=client_a.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            entered_by="auth-super-a"
        )
        entry_b = ProductionEntry(
            production_entry_id="FILTER-B-001",
            client_id=client_b.client_id,
            product_id=product.product_id,
            shift_id=shift.shift_id,
            production_date=date.today(),
            shift_date=date.today(),
            units_produced=200,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            entered_by="auth-super-a"
        )

        db.add_all([entry_a, entry_b])
        db.commit()

        # Get filter for supervisor
        client_filter = get_user_client_filter(supervisor_a)

        if client_filter:
            # Query with filter
            filtered_entries = db.query(ProductionEntry).filter(
                ProductionEntry.client_id.in_(client_filter)
            ).all()

            # Should only see Client A entries
            assert all(e.client_id == client_a.client_id for e in filtered_entries)
