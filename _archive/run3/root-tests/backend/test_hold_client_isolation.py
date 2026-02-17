"""
Multi-Tenant WIP Hold Client Isolation Tests
Tests strict data isolation for WIP (Work-In-Progress) holds between clients
CRITICAL: Ensures hold data cannot leak between clients
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.schemas.user import User
from backend.schemas.client import Client
from backend.schemas.work_order import WorkOrder
from backend.schemas.shift import Shift
from backend.models.hold import WIPHoldCreate
from backend.crud.hold import (
    create_wip_hold,
    get_wip_holds,
    get_wip_hold,
    update_wip_hold,
    delete_wip_hold
)


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
def operator_client_a(test_db: Session, client_a):
    """Create OPERATOR user for Client A"""
    user = User(
        username="operator_a",
        email="operator_a@test.com",
        password_hash="hashed_password",
        role="OPERATOR",
        client_id_fk="CLIENT-A",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def operator_client_b(test_db: Session, client_b):
    """Create OPERATOR user for Client B"""
    user = User(
        username="operator_b",
        email="operator_b@test.com",
        password_hash="hashed_password",
        role="OPERATOR",
        client_id_fk="CLIENT-B",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def leader_client_a(test_db: Session, client_a):
    """Create LEADER user for Client A"""
    user = User(
        username="leader_a",
        email="leader_a@test.com",
        password_hash="hashed_password",
        role="LEADER",
        client_id_fk="CLIENT-A",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def admin_user(test_db: Session):
    """Create ADMIN user (can access all clients)"""
    user = User(
        username="admin_user",
        email="admin@test.com",
        password_hash="hashed_password",
        role="ADMIN",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()
    return user


@pytest.fixture
def shift_day(test_db: Session):
    """Create day shift"""
    shift = Shift(
        shift_name="Day Shift",
        start_time="08:00",
        end_time="16:00",
        is_active=True
    )
    test_db.add(shift)
    test_db.commit()
    return shift


@pytest.fixture
def work_order_client_a(test_db: Session, client_a):
    """Create work order for Client A"""
    work_order = WorkOrder(
        work_order_id="WO-A-001",
        client_id="CLIENT-A",
        style_model="STYLE-A",
        planned_quantity=1000,
        status="ACTIVE"
    )
    test_db.add(work_order)
    test_db.commit()
    return work_order


@pytest.fixture
def work_order_client_b(test_db: Session, client_b):
    """Create work order for Client B"""
    work_order = WorkOrder(
        work_order_id="WO-B-001",
        client_id="CLIENT-B",
        style_model="STYLE-B",
        planned_quantity=2000,
        status="ACTIVE"
    )
    test_db.add(work_order)
    test_db.commit()
    return work_order


class TestHoldOperatorIsolation:
    """Test OPERATOR role WIP hold isolation"""

    def test_operator_cannot_see_other_client_holds(
        self, test_db, operator_client_a, operator_client_b,
        work_order_client_a, work_order_client_b, shift_day
    ):
        """Client A OPERATOR cannot see Client B WIP holds"""
        # Create holds for both clients
        hold_a = WIPHoldCreate(
            work_order_id=work_order_client_a.work_order_id,
            shift_id=shift_day.shift_id,
            hold_date=date.today(),
            units_on_hold=100,
            hold_reason="Quality issue",
            hold_type="QUALITY",
            status="ACTIVE",
            client_id_fk="CLIENT-A"
        )
        hold_b = WIPHoldCreate(
            work_order_id=work_order_client_b.work_order_id,
            shift_id=shift_day.shift_id,
            hold_date=date.today(),
            units_on_hold=200,
            hold_reason="Material shortage",
            hold_type="MATERIAL",
            status="ACTIVE",
            client_id_fk="CLIENT-B"
        )

        created_a = create_wip_hold(test_db, hold_a, operator_client_a)
        created_b = create_wip_hold(test_db, hold_b, operator_client_b)

        # Client A OPERATOR queries holds
        results_a = get_wip_holds(test_db, operator_client_a)

        # Verify only Client A's records returned
        assert len(results_a) == 1
        assert all(r.client_id_fk == "CLIENT-A" for r in results_a)
        assert results_a[0].hold_id == created_a.hold_id

        # Verify Client B's record is not visible
        assert not any(r.hold_id == created_b.hold_id for r in results_a)

    def test_operator_cannot_access_other_client_hold_by_id(
        self, test_db, operator_client_a, operator_client_b,
        work_order_client_b, shift_day
    ):
        """OPERATOR cannot access specific WIP hold from other client"""
        # Create hold for Client B
        hold_b = WIPHoldCreate(
            work_order_id=work_order_client_b.work_order_id,
            shift_id=shift_day.shift_id,
            hold_date=date.today(),
            units_on_hold=200,
            hold_reason="Quality issue",
            hold_type="QUALITY",
            status="ACTIVE",
            client_id_fk="CLIENT-B"
        )
        created_b = create_wip_hold(test_db, hold_b, operator_client_b)

        # Client A OPERATOR tries to access Client B's record
        result = get_wip_hold(test_db, created_b.hold_id, operator_client_a)

        # Should return None (access denied)
        assert result is None

    def test_operator_cannot_update_other_client_hold(
        self, test_db, operator_client_a, operator_client_b,
        work_order_client_b, shift_day
    ):
        """OPERATOR cannot update WIP hold from other client"""
        # Create hold for Client B
        hold_b = WIPHoldCreate(
            work_order_id=work_order_client_b.work_order_id,
            shift_id=shift_day.shift_id,
            hold_date=date.today(),
            units_on_hold=200,
            hold_reason="Quality issue",
            hold_type="QUALITY",
            status="ACTIVE",
            client_id_fk="CLIENT-B"
        )
        created_b = create_wip_hold(test_db, hold_b, operator_client_b)

        # Client A OPERATOR tries to update Client B's record
        update_data = {"status": "RESOLVED", "units_released": 200}
        result = update_wip_hold(
            test_db,
            created_b.hold_id,
            update_data,
            operator_client_a
        )

        # Should return None (access denied)
        assert result is None

        # Verify record unchanged
        original = get_wip_hold(test_db, created_b.hold_id, operator_client_b)
        assert original.status == "ACTIVE"
        assert original.units_released == 0

    def test_operator_cannot_delete_other_client_hold(
        self, test_db, operator_client_a, operator_client_b,
        work_order_client_b, shift_day
    ):
        """OPERATOR cannot delete WIP hold from other client"""
        # Create hold for Client B
        hold_b = WIPHoldCreate(
            work_order_id=work_order_client_b.work_order_id,
            shift_id=shift_day.shift_id,
            hold_date=date.today(),
            units_on_hold=200,
            hold_reason="Quality issue",
            hold_type="QUALITY",
            status="ACTIVE",
            client_id_fk="CLIENT-B"
        )
        created_b = create_wip_hold(test_db, hold_b, operator_client_b)

        # Client A OPERATOR tries to delete Client B's record
        result = delete_wip_hold(
            test_db,
            created_b.hold_id,
            operator_client_a
        )

        # Should return False (access denied)
        assert result is False

        # Verify record still exists
        existing = get_wip_hold(test_db, created_b.hold_id, operator_client_b)
        assert existing is not None


class TestHoldLeaderIsolation:
    """Test LEADER role WIP hold isolation"""

    def test_leader_restricted_to_assigned_client(
        self, test_db, leader_client_a, operator_client_b,
        work_order_client_a, work_order_client_b, shift_day
    ):
        """LEADER can only access their assigned client's holds"""
        # Create holds for both clients
        hold_a = WIPHoldCreate(
            work_order_id=work_order_client_a.work_order_id,
            shift_id=shift_day.shift_id,
            hold_date=date.today(),
            units_on_hold=100,
            hold_reason="Quality issue",
            hold_type="QUALITY",
            status="ACTIVE",
            client_id_fk="CLIENT-A"
        )
        hold_b = WIPHoldCreate(
            work_order_id=work_order_client_b.work_order_id,
            shift_id=shift_day.shift_id,
            hold_date=date.today(),
            units_on_hold=200,
            hold_reason="Material shortage",
            hold_type="MATERIAL",
            status="ACTIVE",
            client_id_fk="CLIENT-B"
        )

        created_a = create_wip_hold(test_db, hold_a, leader_client_a)
        created_b = create_wip_hold(test_db, hold_b, operator_client_b)

        # LEADER queries holds
        results = get_wip_holds(test_db, leader_client_a)

        # Verify only assigned client's records
        assert len(results) == 1
        assert all(r.client_id_fk == "CLIENT-A" for r in results)
        assert not any(r.hold_id == created_b.hold_id for r in results)


class TestHoldAdminAccess:
    """Test ADMIN role can access all clients"""

    def test_admin_can_see_all_clients_holds(
        self, test_db, admin_user, operator_client_a, operator_client_b,
        work_order_client_a, work_order_client_b, shift_day
    ):
        """ADMIN can access WIP holds for all clients"""
        # Create holds for both clients
        hold_a = WIPHoldCreate(
            work_order_id=work_order_client_a.work_order_id,
            shift_id=shift_day.shift_id,
            hold_date=date.today(),
            units_on_hold=100,
            hold_reason="Quality issue",
            hold_type="QUALITY",
            status="ACTIVE",
            client_id_fk="CLIENT-A"
        )
        hold_b = WIPHoldCreate(
            work_order_id=work_order_client_b.work_order_id,
            shift_id=shift_day.shift_id,
            hold_date=date.today(),
            units_on_hold=200,
            hold_reason="Material shortage",
            hold_type="MATERIAL",
            status="ACTIVE",
            client_id_fk="CLIENT-B"
        )

        created_a = create_wip_hold(test_db, hold_a, operator_client_a)
        created_b = create_wip_hold(test_db, hold_b, operator_client_b)

        # ADMIN queries all holds
        results = get_wip_holds(test_db, admin_user)

        # Verify both clients' records returned
        assert len(results) >= 2
        client_ids = set(r.client_id_fk for r in results)
        assert "CLIENT-A" in client_ids
        assert "CLIENT-B" in client_ids

        # Verify specific records exist
        record_ids = [r.hold_id for r in results]
        assert created_a.hold_id in record_ids
        assert created_b.hold_id in record_ids


class TestHoldDataLeakagePrevention:
    """Test cross-client WIP hold data leakage prevention"""

    def test_hold_metrics_isolated_by_client(
        self, test_db, operator_client_a, operator_client_b,
        work_order_client_a, work_order_client_b, shift_day
    ):
        """Hold metrics and statistics isolated by client"""
        # Client A: Low holds (300 units total)
        for i in range(3):
            hold_a = WIPHoldCreate(
                work_order_id=work_order_client_a.work_order_id,
                shift_id=shift_day.shift_id,
                hold_date=date.today(),
                units_on_hold=100,
                hold_reason=f"Issue {i+1}",
                hold_type="QUALITY",
                status="ACTIVE",
                client_id_fk="CLIENT-A"
            )
            create_wip_hold(test_db, hold_a, operator_client_a)

        # Client B: High holds (1000 units total)
        for i in range(5):
            hold_b = WIPHoldCreate(
                work_order_id=work_order_client_b.work_order_id,
                shift_id=shift_day.shift_id,
                hold_date=date.today(),
                units_on_hold=200,
                hold_reason=f"Issue {i+1}",
                hold_type="QUALITY",
                status="ACTIVE",
                client_id_fk="CLIENT-B"
            )
            create_wip_hold(test_db, hold_b, operator_client_b)

        # Client A queries their hold metrics
        results_a = get_wip_holds(test_db, operator_client_a)
        total_units_a = sum(r.units_on_hold for r in results_a)

        assert len(results_a) == 3
        assert total_units_a == 300

        # Client B queries their hold metrics
        results_b = get_wip_holds(test_db, operator_client_b)
        total_units_b = sum(r.units_on_hold for r in results_b)

        assert len(results_b) == 5
        assert total_units_b == 1000

    def test_hold_release_tracking_isolated(
        self, test_db, operator_client_a, operator_client_b,
        work_order_client_a, work_order_client_b, shift_day
    ):
        """Hold release tracking isolated by client"""
        # Create holds for both clients
        hold_a = WIPHoldCreate(
            work_order_id=work_order_client_a.work_order_id,
            shift_id=shift_day.shift_id,
            hold_date=date.today(),
            units_on_hold=100,
            hold_reason="Quality issue",
            hold_type="QUALITY",
            status="ACTIVE",
            client_id_fk="CLIENT-A"
        )
        hold_b = WIPHoldCreate(
            work_order_id=work_order_client_b.work_order_id,
            shift_id=shift_day.shift_id,
            hold_date=date.today(),
            units_on_hold=200,
            hold_reason="Quality issue",
            hold_type="QUALITY",
            status="ACTIVE",
            client_id_fk="CLIENT-B"
        )

        created_a = create_wip_hold(test_db, hold_a, operator_client_a)
        created_b = create_wip_hold(test_db, hold_b, operator_client_b)

        # Client A releases their hold
        update_a = {"status": "RESOLVED", "units_released": 100}
        update_wip_hold(test_db, created_a.hold_id, update_a, operator_client_a)

        # Verify Client A's release doesn't affect Client B
        hold_b_after = get_wip_hold(test_db, created_b.hold_id, operator_client_b)
        assert hold_b_after.status == "ACTIVE"
        assert hold_b_after.units_released == 0


class TestHoldDateRangeIsolation:
    """Test date range filtering maintains client isolation"""

    def test_date_range_query_respects_client_boundary(
        self, test_db, operator_client_a, operator_client_b,
        work_order_client_a, work_order_client_b, shift_day
    ):
        """Date range queries maintain client isolation"""
        # Create holds for multiple dates
        dates = [date.today() - timedelta(days=i) for i in range(7)]

        for hold_date in dates:
            # Client A hold
            hold_a = WIPHoldCreate(
                work_order_id=work_order_client_a.work_order_id,
                shift_id=shift_day.shift_id,
                hold_date=hold_date,
                units_on_hold=100,
                hold_reason="Daily issue",
                hold_type="QUALITY",
                status="ACTIVE",
                client_id_fk="CLIENT-A"
            )
            # Client B hold
            hold_b = WIPHoldCreate(
                work_order_id=work_order_client_b.work_order_id,
                shift_id=shift_day.shift_id,
                hold_date=hold_date,
                units_on_hold=200,
                hold_reason="Daily issue",
                hold_type="QUALITY",
                status="ACTIVE",
                client_id_fk="CLIENT-B"
            )

            create_wip_hold(test_db, hold_a, operator_client_a)
            create_wip_hold(test_db, hold_b, operator_client_b)

        # Client A queries date range
        results_a = get_wip_holds(
            test_db,
            operator_client_a,
            start_date=dates[-1],
            end_date=dates[0]
        )

        # Verify only Client A records
        assert len(results_a) == 7
        assert all(r.client_id_fk == "CLIENT-A" for r in results_a)
        assert all(r.units_on_hold == 100 for r in results_a)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
