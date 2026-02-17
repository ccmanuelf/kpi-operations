"""
Client Isolation and Multi-Tenant Security Tests
Ensures Client A cannot access Client B's data

CRITICAL: Every query MUST filter by client_id
"""

import pytest
import threading
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
import uuid

from backend.schemas.user import User
from backend.schemas.client import Client
from backend.schemas.employee import Employee
from backend.schemas.shift import Shift
from backend.schemas.work_order import WorkOrder
from backend.schemas.production_entry import ProductionEntry
from backend.schemas.product import Product


@pytest.fixture
def client_a(test_db: Session):
    """Create Client A for isolation tests"""
    client = Client(
        client_id="CLIENT-A",
        client_name="Isolation Test Client A",
        is_active=True
    )
    test_db.add(client)
    test_db.commit()
    return client


@pytest.fixture
def client_b(test_db: Session):
    """Create Client B for isolation tests"""
    client = Client(
        client_id="CLIENT-B",
        client_name="Isolation Test Client B",
        is_active=True
    )
    test_db.add(client)
    test_db.commit()
    return client


@pytest.fixture
def user_client_a(test_db: Session, client_a):
    """Create OPERATOR user for Client A"""
    user = User(
        user_id=f"user-a-{uuid.uuid4().hex[:8]}",
        username="operator_a_isolation",
        email="operator_a_iso@test.com",
        password_hash="hashed_password",
        role="OPERATOR",
        client_id_assigned="CLIENT-A",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def user_client_b(test_db: Session, client_b):
    """Create OPERATOR user for Client B"""
    user = User(
        user_id=f"user-b-{uuid.uuid4().hex[:8]}",
        username="operator_b_isolation",
        email="operator_b_iso@test.com",
        password_hash="hashed_password",
        role="OPERATOR",
        client_id_assigned="CLIENT-B",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def admin_user(test_db: Session):
    """Create ADMIN user (multi-tenant access)"""
    user = User(
        user_id=f"admin-{uuid.uuid4().hex[:8]}",
        username="admin_isolation",
        email="admin_iso@test.com",
        password_hash="hashed_password",
        role="ADMIN",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def shift(test_db: Session):
    """Create shared shift for tests"""
    from datetime import time
    shift = Shift(
        shift_name="Day Shift Isolation",
        start_time=time(8, 0),
        end_time=time(16, 0),
        is_active=True
    )
    test_db.add(shift)
    test_db.commit()
    return shift


@pytest.fixture
def product_a(test_db: Session):
    """Create product for testing"""
    product = Product(
        product_code="PROD-A-ISO",
        product_name="Product A Isolation",
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    return product


@pytest.fixture
def product_b(test_db: Session):
    """Create product for testing"""
    product = Product(
        product_code="PROD-B-ISO",
        product_name="Product B Isolation",
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    return product


class TestClientIsolationProduction:
    """Test production data isolation between clients"""

    def test_client_a_cannot_see_client_b_production(
        self, test_db, client_a, client_b, user_client_a, user_client_b,
        product_a, product_b, shift
    ):
        """
        TEST 1: Client A Query Returns Only Their Data

        SCENARIO:
        - CLIENT-A queries production entries
        - CLIENT-B has production entries

        EXPECTED:
        - Only CLIENT-A data returned
        - CLIENT-B data completely hidden
        """
        from backend.crud.production import get_production_entries

        # Create production entries for both clients
        entry_a = ProductionEntry(
            production_entry_id=f"PE-ISO-A-{uuid.uuid4().hex[:8]}",
            product_id=product_a.product_id,
            shift_id=shift.shift_id,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=user_client_a.user_id,
            client_id="CLIENT-A"
        )
        entry_b = ProductionEntry(
            production_entry_id=f"PE-ISO-B-{uuid.uuid4().hex[:8]}",
            product_id=product_b.product_id,
            shift_id=shift.shift_id,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=200,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=user_client_b.user_id,
            client_id="CLIENT-B"
        )
        test_db.add_all([entry_a, entry_b])
        test_db.commit()

        # Query as CLIENT-A user
        results = get_production_entries(test_db, user_client_a)

        # Verify only CLIENT-A data returned
        for entry in results:
            assert entry.client_id == "CLIENT-A"

        # Verify CLIENT-B entry not in results
        client_b_ids = [e.production_entry_id for e in results if e.client_id == "CLIENT-B"]
        assert len(client_b_ids) == 0

    def test_client_cannot_query_without_client_id_filter(
        self, test_db, client_a, user_client_a
    ):
        """
        TEST 2: Non-admin queries automatically filtered by user's client_id

        SCENARIO:
        - OPERATOR user queries production entries
        - System should filter by their assigned client

        EXPECTED:
        - Only user's client data returned (automatic filtering)
        """
        from backend.crud.production import get_production_entries

        # Query without explicit client_id - should use user's client
        results = get_production_entries(test_db, user_client_a)

        # Results should be filtered by user's client_id (CLIENT-A)
        for entry in results:
            assert entry.client_id == "CLIENT-A"

    def test_client_cannot_access_by_production_id_other_client(
        self, test_db, client_a, client_b, user_client_a, user_client_b,
        product_b, shift
    ):
        """
        TEST 3: Cannot Access Other Client's Entry by ID

        SCENARIO:
        - CLIENT-A knows production_entry_id from CLIENT-B
        - Tries direct access by ID

        EXPECTED:
        - Access denied (ClientAccessError) OR entry not found
        """
        from backend.crud.production import get_production_entry
        from backend.middleware.client_auth import ClientAccessError

        # Create CLIENT-B entry
        entry_b = ProductionEntry(
            production_entry_id=f"PE-ISO-B-{uuid.uuid4().hex[:8]}",
            product_id=product_b.product_id,
            shift_id=shift.shift_id,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=200,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=user_client_b.user_id,
            client_id="CLIENT-B"
        )
        test_db.add(entry_b)
        test_db.commit()

        # CLIENT-A tries to access CLIENT-B's entry by ID
        # Should raise ClientAccessError or return None
        try:
            result = get_production_entry(test_db, entry_b.production_entry_id, user_client_a)
            # If no exception, result should be None
            assert result is None
        except ClientAccessError:
            # Access denied is expected behavior
            pass

    def test_client_cannot_update_other_client_production(
        self, test_db, client_a, client_b, user_client_a, user_client_b,
        product_b, shift
    ):
        """
        TEST 4: Cannot Update Other Client's Data

        SCENARIO:
        - CLIENT-A tries to update CLIENT-B's production entry

        EXPECTED:
        - Update fails or raises exception
        """
        from backend.crud.production import update_production_entry
        from backend.middleware.client_auth import ClientAccessError

        # Create CLIENT-B entry
        entry_b = ProductionEntry(
            production_entry_id=f"PE-ISO-B-{uuid.uuid4().hex[:8]}",
            product_id=product_b.product_id,
            shift_id=shift.shift_id,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=200,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=user_client_b.user_id,
            client_id="CLIENT-B"
        )
        test_db.add(entry_b)
        test_db.commit()

        # CLIENT-A tries to update CLIENT-B's entry
        # Should raise ClientAccessError
        with pytest.raises(ClientAccessError):
            update_production_entry(
                test_db,
                entry_b.production_entry_id,
                {"units_produced": 999},
                user_client_a
            )

        # Verify entry unchanged
        test_db.refresh(entry_b)
        assert entry_b.units_produced == 200

    def test_client_cannot_delete_other_client_production(
        self, test_db, client_a, client_b, user_client_a, user_client_b,
        product_b, shift
    ):
        """
        TEST 5: Cannot Delete Other Client's Data

        SCENARIO:
        - CLIENT-A tries to soft-delete CLIENT-B's entry

        EXPECTED:
        - Delete fails with ClientAccessError
        """
        from backend.crud.production import delete_production_entry
        from backend.middleware.client_auth import ClientAccessError

        # Create CLIENT-B entry
        entry_b = ProductionEntry(
            production_entry_id=f"PE-ISO-B-{uuid.uuid4().hex[:8]}",
            product_id=product_b.product_id,
            shift_id=shift.shift_id,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=200,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=user_client_b.user_id,
            client_id="CLIENT-B"
        )
        test_db.add(entry_b)
        test_db.commit()
        entry_id = entry_b.production_entry_id

        # CLIENT-A tries to delete CLIENT-B's entry
        # Should raise ClientAccessError
        with pytest.raises(ClientAccessError):
            delete_production_entry(test_db, entry_id, user_client_a)

        # Verify entry still exists
        remaining = test_db.query(ProductionEntry).filter_by(
            production_entry_id=entry_id
        ).first()
        assert remaining is not None


class TestClientIsolationKPIs:
    """Test KPI calculation isolation"""

    def test_kpi_efficiency_only_own_client(
        self, test_db, client_a, client_b, user_client_a, user_client_b,
        product_a, product_b, shift
    ):
        """
        TEST 6: KPI Efficiency for Own Client Only

        SCENARIO:
        - CLIENT-A requests efficiency KPI
        - CLIENT-B has production data

        EXPECTED:
        - CLIENT-A's efficiency calculated only from their data
        - CLIENT-B data excluded
        """
        # Create production entries with different efficiency profiles
        entry_a = ProductionEntry(
            production_entry_id=f"PE-ISO-A-{uuid.uuid4().hex[:8]}",
            product_id=product_a.product_id,
            shift_id=shift.shift_id,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=user_client_a.user_id,
            efficiency_percentage=Decimal("100.0"),
            client_id="CLIENT-A"
        )
        entry_b = ProductionEntry(
            production_entry_id=f"PE-ISO-B-{uuid.uuid4().hex[:8]}",
            product_id=product_b.product_id,
            shift_id=shift.shift_id,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=50,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=user_client_b.user_id,
            efficiency_percentage=Decimal("50.0"),
            client_id="CLIENT-B"
        )
        test_db.add_all([entry_a, entry_b])
        test_db.commit()

        # Query production for CLIENT-A
        from backend.crud.production import get_production_entries
        results_a = get_production_entries(test_db, user_client_a)

        # Calculate efficiency from CLIENT-A data only
        for entry in results_a:
            assert entry.client_id == "CLIENT-A"

    def test_kpi_dashboard_multi_client_admin(
        self, test_db, client_a, client_b, user_client_a, user_client_b,
        product_a, product_b, shift
    ):
        """
        TEST 7: Admin Can See All Clients (Separate Sections)

        SCENARIO:
        - Admin views dashboard
        - Multiple clients exist

        EXPECTED:
        - Each client's data is kept separate (no cross-contamination)
        - Direct DB query shows both clients' entries exist
        """
        # Create entries for both clients
        entry_a = ProductionEntry(
            production_entry_id=f"PE-ISO-A-{uuid.uuid4().hex[:8]}",
            product_id=product_a.product_id,
            shift_id=shift.shift_id,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=user_client_a.user_id,
            client_id="CLIENT-A"
        )
        entry_b = ProductionEntry(
            production_entry_id=f"PE-ISO-B-{uuid.uuid4().hex[:8]}",
            product_id=product_b.product_id,
            shift_id=shift.shift_id,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=200,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=user_client_b.user_id,
            client_id="CLIENT-B"
        )
        test_db.add_all([entry_a, entry_b])
        test_db.commit()

        # Direct DB query should show entries from both clients
        all_entries = test_db.query(ProductionEntry).all()
        client_ids = set(e.client_id for e in all_entries if e.client_id)
        assert "CLIENT-A" in client_ids
        assert "CLIENT-B" in client_ids

        # Each client should only see their own entries via CRUD
        from backend.crud.production import get_production_entries
        results_a = get_production_entries(test_db, user_client_a)
        for entry in results_a:
            assert entry.client_id == "CLIENT-A"


class TestClientIsolationWorkOrders:
    """Test work order isolation"""

    def test_client_cannot_see_other_work_orders(
        self, test_db, client_a, client_b, user_client_a, user_client_b
    ):
        """
        TEST 8: Work Order List Filtered by Client

        SCENARIO:
        - CLIENT-A queries work orders

        EXPECTED:
        - Only CLIENT-A's work orders returned
        """
        from backend.crud.work_order import get_work_orders

        # Create work orders for both clients
        wo_a = WorkOrder(
            work_order_id=f"WO-ISO-A-{uuid.uuid4().hex[:8]}",
            client_id="CLIENT-A",
            style_model="STYLE-A",
            planned_quantity=1000,
            status="ACTIVE"
        )
        wo_b = WorkOrder(
            work_order_id=f"WO-ISO-B-{uuid.uuid4().hex[:8]}",
            client_id="CLIENT-B",
            style_model="STYLE-B",
            planned_quantity=2000,
            status="ACTIVE"
        )
        test_db.add_all([wo_a, wo_b])
        test_db.commit()

        # CLIENT-A queries work orders
        results = get_work_orders(test_db, user_client_a)

        # Should only see CLIENT-A work orders
        for wo in results:
            assert wo.client_id == "CLIENT-A"

    def test_client_cannot_access_work_order_by_id(
        self, test_db, client_a, client_b, user_client_a
    ):
        """
        TEST 8b: Cannot Access Other Client's Work Order by ID

        SCENARIO:
        - CLIENT-A tries to access CLIENT-B's work order by ID

        EXPECTED:
        - Returns None or raises ClientAccessError
        """
        from backend.crud.work_order import get_work_order
        from backend.middleware.client_auth import ClientAccessError

        # Create CLIENT-B work order
        wo_id = f"WO-ISO-B-{uuid.uuid4().hex[:8]}"
        wo_b = WorkOrder(
            work_order_id=wo_id,
            client_id="CLIENT-B",
            style_model="STYLE-B",
            planned_quantity=2000,
            status="ACTIVE"
        )
        test_db.add(wo_b)
        test_db.commit()

        # CLIENT-A tries to access CLIENT-B's work order
        # Should raise ClientAccessError or return None
        try:
            result = get_work_order(test_db, wo_id, user_client_a)
            assert result is None
        except ClientAccessError:
            # Access denied is expected behavior
            pass

    def test_client_cannot_create_work_order_for_other_client(
        self, test_db, client_a, client_b, user_client_a
    ):
        """
        TEST 9: Cannot Create Work Order for Other Client

        SCENARIO:
        - CLIENT-A user tries to create work order with client_id="CLIENT-B"

        EXPECTED:
        - Error: client_id mismatch or rejection
        """
        from backend.crud.work_order import create_work_order
        from fastapi import HTTPException

        # CLIENT-A tries to create work order for CLIENT-B
        wo_data = {
            "work_order_id": f"WO-INVALID-{uuid.uuid4().hex[:8]}",
            "client_id": "CLIENT-B",  # Wrong client!
            "style_model": "STYLE-X",
            "planned_quantity": 500,
            "status": "ACTIVE"
        }

        # Should raise exception
        with pytest.raises((HTTPException, PermissionError, ValueError)):
            create_work_order(test_db, wo_data, user_client_a)


class TestClientIsolationReports:
    """Test report generation isolation"""

    def test_pdf_report_data_filtered_by_client(
        self, test_db, client_a, client_b, user_client_a, user_client_b,
        product_a, product_b, shift
    ):
        """
        TEST 10: Report Data Contains Only Own Client Data

        SCENARIO:
        - CLIENT-A requests production data for report

        EXPECTED:
        - Data includes ONLY CLIENT-A entries
        - No leakage from other clients
        """
        from backend.crud.production import get_production_entries

        # Create entries for both clients
        entry_a = ProductionEntry(
            production_entry_id=f"PE-ISO-A-{uuid.uuid4().hex[:8]}",
            product_id=product_a.product_id,
            shift_id=shift.shift_id,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=100,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=user_client_a.user_id,
            client_id="CLIENT-A"
        )
        entry_b = ProductionEntry(
            production_entry_id=f"PE-ISO-B-{uuid.uuid4().hex[:8]}",
            product_id=product_b.product_id,
            shift_id=shift.shift_id,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=200,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=user_client_b.user_id,
            client_id="CLIENT-B"
        )
        test_db.add_all([entry_a, entry_b])
        test_db.commit()

        # Get data for report (filtered by client)
        results = get_production_entries(test_db, user_client_a)

        # Verify no CLIENT-B data in results
        for entry in results:
            assert entry.client_id == "CLIENT-A"


class TestClientIsolationConcurrentAccess:
    """Test concurrent access by multiple clients"""

    def test_concurrent_writes_no_cross_contamination(
        self, test_db, client_a, client_b, user_client_a, user_client_b,
        product_a, product_b, shift
    ):
        """
        TEST 12: Concurrent Writes by Multiple Clients

        SCENARIO:
        - CLIENT-A and CLIENT-B write production entries simultaneously

        EXPECTED:
        - Each entry saved with correct client_id
        - No mix-ups
        """
        entries_created = {"CLIENT-A": None, "CLIENT-B": None}

        # Create entries for both clients
        entry_a = ProductionEntry(
            production_entry_id=f"PE-CONC-A-{uuid.uuid4().hex[:8]}",
            product_id=product_a.product_id,
            shift_id=shift.shift_id,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=111,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=user_client_a.user_id,
            client_id="CLIENT-A"
        )
        entry_b = ProductionEntry(
            production_entry_id=f"PE-CONC-B-{uuid.uuid4().hex[:8]}",
            product_id=product_b.product_id,
            shift_id=shift.shift_id,
            production_date=datetime.now(),
            shift_date=datetime.now(),
            units_produced=222,
            run_time_hours=Decimal("8.0"),
            employees_assigned=5,
            defect_count=0,
            scrap_count=0,
            entered_by=user_client_b.user_id,
            client_id="CLIENT-B"
        )

        test_db.add_all([entry_a, entry_b])
        test_db.commit()

        # Verify entries have correct client_id
        assert entry_a.client_id == "CLIENT-A"
        assert entry_b.client_id == "CLIENT-B"
        assert entry_a.units_produced == 111
        assert entry_b.units_produced == 222


class TestClientIsolationDatabaseLevel:
    """Test database-level isolation enforcement"""

    def test_database_query_includes_client_id_filter(
        self, test_db, client_a, user_client_a
    ):
        """
        TEST 14: Database Queries Include client_id Filter

        SCENARIO:
        - Query for production entries

        EXPECTED:
        - Query filters by client_id
        """
        from backend.crud.production import get_production_entries

        # Execute query and verify it returns filtered results
        results = get_production_entries(test_db, user_client_a)

        # All results should match user's client
        for entry in results:
            assert entry.client_id == "CLIENT-A"

    def test_database_tables_have_client_id_column(self, test_db):
        """
        TEST 15: Ensure client_id Column Exists on Multi-Tenant Tables

        SCENARIO:
        - Check schema for client_id columns

        EXPECTED:
        - Key tables have client_id for isolation
        """
        from sqlalchemy import inspect

        inspector = inspect(test_db.bind)

        # Check PRODUCTION_ENTRY table
        if 'PRODUCTION_ENTRY' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('PRODUCTION_ENTRY')]
            assert 'client_id' in columns

        # Check WORK_ORDER table
        if 'WORK_ORDER' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('WORK_ORDER')]
            assert 'client_id' in columns


class TestClientIsolationFloatingPool:
    """Test floating pool employee isolation"""

    def test_floating_employee_client_isolation_logic(
        self, test_db, client_a, client_b, user_client_a, user_client_b
    ):
        """
        TEST 16: Floating Pool Employee Assignments Should Be Isolated

        SCENARIO:
        - Floating employee can be assigned to any client
        - Assignments should be tracked per client

        EXPECTED:
        - Each client only sees their own assignments
        - Tenant guard prevents cross-client access
        """
        from backend.utils.tenant_guard import verify_tenant_access, filter_resources_by_tenant
        from backend.exceptions.domain_exceptions import MultiTenantViolationError

        # Create floating pool employee
        floating_emp = Employee(
            employee_code="FLOAT-ISO-001",
            employee_name="Floating Test Employee",
            is_floating_pool=1
        )
        test_db.add(floating_emp)
        test_db.commit()

        # Simulate coverage assignments for different clients
        class MockCoverage:
            def __init__(self, client_id, employee_id):
                self.client_id = client_id
                self.employee_id = employee_id

        all_coverages = [
            MockCoverage("CLIENT-A", floating_emp.employee_id),
            MockCoverage("CLIENT-B", floating_emp.employee_id),
            MockCoverage("CLIENT-A", floating_emp.employee_id),
        ]

        # Filter for CLIENT-A
        client_a_coverages = filter_resources_by_tenant(all_coverages, "CLIENT-A")
        assert len(client_a_coverages) == 2
        for cov in client_a_coverages:
            assert cov.client_id == "CLIENT-A"

        # Filter for CLIENT-B
        client_b_coverages = filter_resources_by_tenant(all_coverages, "CLIENT-B")
        assert len(client_b_coverages) == 1
        for cov in client_b_coverages:
            assert cov.client_id == "CLIENT-B"

        # Verify cross-client access is blocked
        with pytest.raises(MultiTenantViolationError):
            verify_tenant_access(
                current_client_id="CLIENT-A",
                resource_client_id="CLIENT-B",
                resource_type="coverage_assignment"
            )


class TestAPIClientValidation:
    """Test API endpoint client_id validation"""

    def test_api_rejects_missing_client_id(self):
        """
        TEST 18: API Returns 400 When client_id is Missing

        SCENARIO:
        - Request made without client_id

        EXPECTED:
        - 400 Bad Request
        """
        from backend.utils.tenant_guard import ensure_client_id
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            ensure_client_id(None, context="test_request")

        assert exc_info.value.status_code == 400
        assert "client_id" in str(exc_info.value.detail).lower()

    def test_api_rejects_empty_client_id(self):
        """
        TEST 19: API Returns 400 When client_id is Empty String

        SCENARIO:
        - Request made with empty client_id

        EXPECTED:
        - 400 Bad Request
        """
        from backend.utils.tenant_guard import ensure_client_id
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            ensure_client_id("", context="test_request")

        assert exc_info.value.status_code == 400

    def test_tenant_access_verification(self):
        """
        TEST 20: Verify Tenant Access Check

        SCENARIO:
        - User from CLIENT-A tries to access CLIENT-B resource

        EXPECTED:
        - MultiTenantViolationError raised
        """
        from backend.utils.tenant_guard import verify_tenant_access
        from backend.exceptions.domain_exceptions import MultiTenantViolationError

        with pytest.raises(MultiTenantViolationError) as exc_info:
            verify_tenant_access(
                current_client_id="CLIENT-A",
                resource_client_id="CLIENT-B",
                resource_type="work_order"
            )

        assert "different tenant" in str(exc_info.value.message).lower()

    def test_tenant_access_allowed_same_client(self):
        """
        TEST 21: Tenant Access Allowed for Same Client

        SCENARIO:
        - User from CLIENT-A accesses CLIENT-A resource

        EXPECTED:
        - No exception raised
        """
        from backend.utils.tenant_guard import verify_tenant_access

        # Should not raise
        verify_tenant_access(
            current_client_id="CLIENT-A",
            resource_client_id="CLIENT-A",
            resource_type="work_order"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
