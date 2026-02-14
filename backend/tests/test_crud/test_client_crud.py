"""
Real-database tests for Client CRUD operations.
Uses transactional_db fixture (in-memory SQLite with automatic rollback).
No mocks for database operations.
"""
import pytest
from datetime import date, datetime
from decimal import Decimal

from backend.schemas import (
    Client, ClientType,
    User, UserRole,
    Employee,
    WorkOrder, WorkOrderStatus,
    Product,
)
from backend.tests.fixtures.factories import TestDataFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_admin_user(db, client_id=None):
    """Create an admin user (no client restriction)."""
    return TestDataFactory.create_user(
        db,
        username="admin_user",
        role="admin",
        client_id=client_id,
    )


class TestClientCRUD:
    """Test suite for client CRUD operations using real database."""

    def test_create_client(self, transactional_db):
        """Test client creation persists to DB."""
        db = transactional_db

        client = TestDataFactory.create_client(
            db,
            client_id="CLIENT-001",
            client_name="Test Manufacturing Co",
            client_type=ClientType.SERVICE,
        )
        db.flush()

        from_db = db.query(Client).filter_by(client_id="CLIENT-001").first()
        assert from_db is not None
        assert from_db.client_name == "Test Manufacturing Co"
        assert from_db.client_type == ClientType.SERVICE
        assert from_db.is_active == 1

    def test_get_client_by_id(self, transactional_db):
        """Test getting client by primary key."""
        db = transactional_db

        TestDataFactory.create_client(db, client_id="CLIENT-001", client_name="Acme Corp")
        db.flush()

        result = db.query(Client).filter_by(client_id="CLIENT-001").first()
        assert result is not None
        assert result.client_id == "CLIENT-001"
        assert result.client_name == "Acme Corp"

    def test_get_all_active_clients(self, transactional_db):
        """Test getting all active clients filters correctly."""
        db = transactional_db

        TestDataFactory.create_client(db, client_id="ACTIVE-1", client_name="Active One", is_active=True)
        TestDataFactory.create_client(db, client_id="ACTIVE-2", client_name="Active Two", is_active=True)

        inactive = Client(
            client_id="INACTIVE-1",
            client_name="Inactive One",
            client_type=ClientType.HOURLY_RATE,
            is_active=0,
        )
        db.add(inactive)
        db.flush()

        active_clients = db.query(Client).filter(Client.is_active == 1).all()
        assert len(active_clients) == 2
        assert all(c.is_active == 1 for c in active_clients)

    def test_update_client(self, transactional_db):
        """Test updating client information persists."""
        db = transactional_db

        client = TestDataFactory.create_client(
            db,
            client_id="CLIENT-001",
            client_name="Old Name",
        )
        db.flush()

        client.client_name = "Updated Manufacturing Co"
        db.flush()

        from_db = db.query(Client).filter_by(client_id="CLIENT-001").first()
        assert from_db.client_name == "Updated Manufacturing Co"

    def test_deactivate_client(self, transactional_db):
        """Test deactivating a client (soft delete pattern)."""
        db = transactional_db

        client = TestDataFactory.create_client(db, client_id="CLIENT-001")
        db.flush()
        assert client.is_active == 1

        client.is_active = 0
        db.flush()

        from_db = db.query(Client).filter_by(client_id="CLIENT-001").first()
        assert from_db.is_active == 0

    def test_delete_client_soft(self, transactional_db):
        """Test soft delete sets is_active=0, does NOT remove from DB."""
        db = transactional_db

        client = TestDataFactory.create_client(db, client_id="CLIENT-SOFT-DEL")
        db.flush()

        client.is_active = 0
        db.flush()

        # Still exists in DB
        from_db = db.query(Client).filter_by(client_id="CLIENT-SOFT-DEL").first()
        assert from_db is not None
        assert from_db.is_active == 0

        # But filtered query excludes it
        active_only = db.query(Client).filter(
            Client.client_id == "CLIENT-SOFT-DEL",
            Client.is_active == 1,
        ).first()
        assert active_only is None

    def test_client_type_enum_stored(self, transactional_db):
        """Test client type enum values persist correctly."""
        db = transactional_db

        for ct in [ClientType.HOURLY_RATE, ClientType.PIECE_RATE, ClientType.HYBRID, ClientType.SERVICE]:
            c = TestDataFactory.create_client(db, client_type=ct)
            db.flush()
            from_db = db.query(Client).filter_by(client_id=c.client_id).first()
            assert from_db.client_type == ct

    def test_get_client_not_found(self, transactional_db):
        """Test querying non-existent client returns None."""
        db = transactional_db

        result = db.query(Client).filter_by(client_id="DOES-NOT-EXIST").first()
        assert result is None

    def test_client_isolation_multi_tenant(self, transactional_db):
        """Test multi-tenant isolation: each client is an independent entity."""
        db = transactional_db

        TestDataFactory.create_client(db, client_id="CLIENT-001", client_name="Client One")
        TestDataFactory.create_client(db, client_id="CLIENT-002", client_name="Client Two")
        db.flush()

        user_assigned_client = "CLIENT-001"
        accessible = db.query(Client).filter(
            Client.client_id == user_assigned_client
        ).all()
        assert len(accessible) == 1
        assert accessible[0].client_id == "CLIENT-001"

    def test_duplicate_client_id_rejected(self, transactional_db):
        """Test that duplicate client_id is rejected by the database."""
        db = transactional_db

        TestDataFactory.create_client(db, client_id="DUP-CLIENT")
        db.flush()

        dup = Client(
            client_id="DUP-CLIENT",
            client_name="Duplicate",
            client_type=ClientType.HOURLY_RATE,
            is_active=1,
        )
        db.add(dup)

        with pytest.raises(Exception):
            db.flush()
        db.rollback()


class TestClientEmployee:
    """Test suite for client-employee relationship using real DB."""

    def test_create_employee(self, transactional_db):
        """Test employee creation with client assignment persists."""
        db = transactional_db

        client = TestDataFactory.create_client(db, client_id="CLIENT-001")
        db.flush()

        employee = TestDataFactory.create_employee(
            db,
            client_id=client.client_id,
            employee_name="John Doe",
            employee_code="EMP-001",
        )
        db.flush()

        from_db = db.query(Employee).filter_by(
            employee_code="EMP-001"
        ).first()
        assert from_db is not None
        assert from_db.employee_name == "John Doe"
        assert from_db.client_id_assigned == client.client_id

    def test_get_employees_by_client(self, transactional_db):
        """Test getting employees filtered by client."""
        db = transactional_db

        client = TestDataFactory.create_client(db, client_id="CLIENT-001")
        db.flush()

        for i in range(3):
            TestDataFactory.create_employee(
                db,
                client_id=client.client_id,
                employee_name=f"Employee {i}",
            )
        db.flush()

        results = db.query(Employee).filter(
            Employee.client_id_assigned == client.client_id
        ).all()
        assert len(results) == 3

    def test_employee_department_assignment(self, transactional_db):
        """Test employee department field is stored correctly."""
        db = transactional_db

        client = TestDataFactory.create_client(db, client_id="CLIENT-001")
        db.flush()

        employee = TestDataFactory.create_employee(
            db,
            client_id=client.client_id,
            department="Assembly",
        )
        db.flush()

        from_db = db.query(Employee).filter_by(
            employee_id=employee.employee_id
        ).first()
        assert from_db.department == "Assembly"

    def test_employee_active_status(self, transactional_db):
        """Test employee active/inactive status filtering."""
        db = transactional_db

        client = TestDataFactory.create_client(db, client_id="CLIENT-001")
        db.flush()

        active_emp = TestDataFactory.create_employee(db, client_id=client.client_id, is_active=True)
        inactive_emp = TestDataFactory.create_employee(db, client_id=client.client_id, is_active=False)
        db.flush()

        active_only = db.query(Employee).filter(
            Employee.client_id_assigned == client.client_id,
            Employee.is_active == 1,
        ).all()
        assert len(active_only) == 1

    def test_floating_pool_employee(self, transactional_db):
        """Test floating pool flag is stored correctly."""
        db = transactional_db

        client = TestDataFactory.create_client(db, client_id="CLIENT-001")
        db.flush()

        fp_emp = TestDataFactory.create_employee(
            db,
            client_id=client.client_id,
            is_floating_pool=True,
        )
        db.flush()

        from_db = db.query(Employee).filter_by(
            employee_id=fp_emp.employee_id
        ).first()
        assert from_db.is_floating_pool == 1


class TestWorkOrderCRUD:
    """Test suite for work order CRUD operations using real database."""

    def test_create_work_order(self, transactional_db):
        """Test work order creation persists to DB."""
        db = transactional_db

        client = TestDataFactory.create_client(db, client_id="CLIENT-001")
        db.flush()

        wo = TestDataFactory.create_work_order(
            db,
            client_id=client.client_id,
            work_order_id="WO-001",
            planned_quantity=1000,
        )
        db.flush()

        from_db = db.query(WorkOrder).filter_by(work_order_id="WO-001").first()
        assert from_db is not None
        assert from_db.client_id == "CLIENT-001"
        assert from_db.planned_quantity == 1000
        assert from_db.status == WorkOrderStatus.RECEIVED

    def test_update_work_order_status(self, transactional_db):
        """Test updating work order status persists."""
        db = transactional_db

        client = TestDataFactory.create_client(db, client_id="CLIENT-001")
        wo = TestDataFactory.create_work_order(db, client_id=client.client_id)
        db.flush()

        wo.status = WorkOrderStatus.IN_PROGRESS
        db.flush()

        from_db = db.query(WorkOrder).filter_by(
            work_order_id=wo.work_order_id
        ).first()
        assert from_db.status == WorkOrderStatus.IN_PROGRESS

    def test_complete_work_order(self, transactional_db):
        """Test completing a work order and computing fulfillment rate."""
        db = transactional_db

        client = TestDataFactory.create_client(db, client_id="CLIENT-001")
        wo = TestDataFactory.create_work_order(
            db,
            client_id=client.client_id,
            planned_quantity=1000,
        )
        db.flush()

        wo.status = WorkOrderStatus.COMPLETED
        wo.actual_quantity = 980
        db.flush()

        from_db = db.query(WorkOrder).filter_by(
            work_order_id=wo.work_order_id
        ).first()
        assert from_db.status == WorkOrderStatus.COMPLETED

        fulfillment_rate = (from_db.actual_quantity / from_db.planned_quantity) * 100
        assert fulfillment_rate == 98.0

    def test_work_order_on_time_delivery(self, transactional_db):
        """Test on-time delivery flag based on ship dates."""
        db = transactional_db

        client = TestDataFactory.create_client(db, client_id="CLIENT-001")
        wo = TestDataFactory.create_work_order(
            db,
            client_id=client.client_id,
            planned_ship_date=datetime(2026, 1, 15),
        )
        db.flush()

        wo.actual_delivery_date = datetime(2026, 1, 14)
        db.flush()

        from_db = db.query(WorkOrder).filter_by(
            work_order_id=wo.work_order_id
        ).first()
        is_on_time = from_db.actual_delivery_date <= from_db.planned_ship_date
        assert is_on_time is True

    def test_work_orders_filtered_by_client(self, transactional_db):
        """Test work orders are isolated per client."""
        db = transactional_db

        c1 = TestDataFactory.create_client(db, client_id="CLIENT-001")
        c2 = TestDataFactory.create_client(db, client_id="CLIENT-002")
        db.flush()

        TestDataFactory.create_work_order(db, client_id=c1.client_id)
        TestDataFactory.create_work_order(db, client_id=c1.client_id)
        TestDataFactory.create_work_order(db, client_id=c2.client_id)
        db.flush()

        c1_orders = db.query(WorkOrder).filter(
            WorkOrder.client_id == "CLIENT-001"
        ).all()
        c2_orders = db.query(WorkOrder).filter(
            WorkOrder.client_id == "CLIENT-002"
        ).all()

        assert len(c1_orders) == 2
        assert len(c2_orders) == 1

    def test_work_order_status_transitions(self, transactional_db):
        """Test work order status can transition through lifecycle."""
        db = transactional_db

        client = TestDataFactory.create_client(db, client_id="CLIENT-001")
        wo = TestDataFactory.create_work_order(db, client_id=client.client_id)
        db.flush()

        assert wo.status == WorkOrderStatus.RECEIVED

        for target_status in [WorkOrderStatus.RELEASED, WorkOrderStatus.IN_PROGRESS, WorkOrderStatus.COMPLETED]:
            wo.status = target_status
            db.flush()

            from_db = db.query(WorkOrder).filter_by(
                work_order_id=wo.work_order_id
            ).first()
            assert from_db.status == target_status
