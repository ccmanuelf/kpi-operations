"""
Multi-Tenant Downtime Event Client Isolation Tests
Tests strict data isolation for downtime events between clients
CRITICAL: Ensures downtime data cannot leak between clients
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.schemas.user import User
from backend.schemas.client import Client
from backend.schemas.machine import Machine
from backend.schemas.shift import Shift
from backend.models.downtime import DowntimeEventCreate
from backend.crud.downtime import (
    create_downtime_event,
    get_downtime_events,
    get_downtime_event,
    update_downtime_event,
    delete_downtime_event
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
def machine_client_a(test_db: Session, client_a):
    """Create machine for Client A"""
    machine = Machine(
        machine_code="MACH-A-001",
        machine_name="Machine A",
        client_id_fk="CLIENT-A",
        is_active=True
    )
    test_db.add(machine)
    test_db.commit()
    return machine


@pytest.fixture
def machine_client_b(test_db: Session, client_b):
    """Create machine for Client B"""
    machine = Machine(
        machine_code="MACH-B-001",
        machine_name="Machine B",
        client_id_fk="CLIENT-B",
        is_active=True
    )
    test_db.add(machine)
    test_db.commit()
    return machine


class TestDowntimeOperatorIsolation:
    """Test OPERATOR role downtime event isolation"""

    def test_operator_cannot_see_other_client_downtime(
        self, test_db, operator_client_a, operator_client_b,
        machine_client_a, machine_client_b, shift_day
    ):
        """Client A OPERATOR cannot see Client B downtime events"""
        # Create downtime events for both clients
        down_a = DowntimeEventCreate(
            machine_id=machine_client_a.machine_id,
            shift_id=shift_day.shift_id,
            downtime_date=date.today(),
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            duration_minutes=60,
            downtime_type="BREAKDOWN",
            reason="Mechanical failure",
            client_id_fk="CLIENT-A"
        )
        down_b = DowntimeEventCreate(
            machine_id=machine_client_b.machine_id,
            shift_id=shift_day.shift_id,
            downtime_date=date.today(),
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=2),
            duration_minutes=120,
            downtime_type="MAINTENANCE",
            reason="Scheduled maintenance",
            client_id_fk="CLIENT-B"
        )

        created_a = create_downtime_event(test_db, down_a, operator_client_a)
        created_b = create_downtime_event(test_db, down_b, operator_client_b)

        # Client A OPERATOR queries downtime
        results_a = get_downtime_events(test_db, operator_client_a)

        # Verify only Client A's records returned
        assert len(results_a) == 1
        assert all(r.client_id_fk == "CLIENT-A" for r in results_a)
        assert results_a[0].downtime_id == created_a.downtime_id

        # Verify Client B's record is not visible
        assert not any(r.downtime_id == created_b.downtime_id for r in results_a)

    def test_operator_cannot_access_other_client_downtime_by_id(
        self, test_db, operator_client_a, operator_client_b,
        machine_client_b, shift_day
    ):
        """OPERATOR cannot access specific downtime event from other client"""
        # Create downtime for Client B
        down_b = DowntimeEventCreate(
            machine_id=machine_client_b.machine_id,
            shift_id=shift_day.shift_id,
            downtime_date=date.today(),
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            duration_minutes=60,
            downtime_type="BREAKDOWN",
            reason="Equipment failure",
            client_id_fk="CLIENT-B"
        )
        created_b = create_downtime_event(test_db, down_b, operator_client_b)

        # Client A OPERATOR tries to access Client B's record
        result = get_downtime_event(test_db, created_b.downtime_id, operator_client_a)

        # Should return None (access denied)
        assert result is None

    def test_operator_cannot_update_other_client_downtime(
        self, test_db, operator_client_a, operator_client_b,
        machine_client_b, shift_day
    ):
        """OPERATOR cannot update downtime from other client"""
        # Create downtime for Client B
        down_b = DowntimeEventCreate(
            machine_id=machine_client_b.machine_id,
            shift_id=shift_day.shift_id,
            downtime_date=date.today(),
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            duration_minutes=60,
            downtime_type="BREAKDOWN",
            reason="Equipment failure",
            client_id_fk="CLIENT-B"
        )
        created_b = create_downtime_event(test_db, down_b, operator_client_b)

        # Client A OPERATOR tries to update Client B's record
        update_data = {"duration_minutes": 120, "reason": "Updated reason"}
        result = update_downtime_event(
            test_db,
            created_b.downtime_id,
            update_data,
            operator_client_a
        )

        # Should return None (access denied)
        assert result is None

        # Verify record unchanged
        original = get_downtime_event(test_db, created_b.downtime_id, operator_client_b)
        assert original.duration_minutes == 60
        assert original.reason == "Equipment failure"

    def test_operator_cannot_delete_other_client_downtime(
        self, test_db, operator_client_a, operator_client_b,
        machine_client_b, shift_day
    ):
        """OPERATOR cannot delete downtime from other client"""
        # Create downtime for Client B
        down_b = DowntimeEventCreate(
            machine_id=machine_client_b.machine_id,
            shift_id=shift_day.shift_id,
            downtime_date=date.today(),
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            duration_minutes=60,
            downtime_type="BREAKDOWN",
            reason="Equipment failure",
            client_id_fk="CLIENT-B"
        )
        created_b = create_downtime_event(test_db, down_b, operator_client_b)

        # Client A OPERATOR tries to delete Client B's record
        result = delete_downtime_event(
            test_db,
            created_b.downtime_id,
            operator_client_a
        )

        # Should return False (access denied)
        assert result is False

        # Verify record still exists
        existing = get_downtime_event(test_db, created_b.downtime_id, operator_client_b)
        assert existing is not None


class TestDowntimeLeaderIsolation:
    """Test LEADER role downtime event isolation"""

    def test_leader_restricted_to_assigned_client(
        self, test_db, leader_client_a, operator_client_b,
        machine_client_a, machine_client_b, shift_day
    ):
        """LEADER can only access their assigned client's downtime"""
        # Create downtime for both clients
        down_a = DowntimeEventCreate(
            machine_id=machine_client_a.machine_id,
            shift_id=shift_day.shift_id,
            downtime_date=date.today(),
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            duration_minutes=60,
            downtime_type="BREAKDOWN",
            reason="Mechanical failure",
            client_id_fk="CLIENT-A"
        )
        down_b = DowntimeEventCreate(
            machine_id=machine_client_b.machine_id,
            shift_id=shift_day.shift_id,
            downtime_date=date.today(),
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            duration_minutes=60,
            downtime_type="BREAKDOWN",
            reason="Equipment failure",
            client_id_fk="CLIENT-B"
        )

        created_a = create_downtime_event(test_db, down_a, leader_client_a)
        created_b = create_downtime_event(test_db, down_b, operator_client_b)

        # LEADER queries downtime
        results = get_downtime_events(test_db, leader_client_a)

        # Verify only assigned client's records
        assert len(results) == 1
        assert all(r.client_id_fk == "CLIENT-A" for r in results)
        assert not any(r.downtime_id == created_b.downtime_id for r in results)


class TestDowntimeAdminAccess:
    """Test ADMIN role can access all clients"""

    def test_admin_can_see_all_clients_downtime(
        self, test_db, admin_user, operator_client_a, operator_client_b,
        machine_client_a, machine_client_b, shift_day
    ):
        """ADMIN can access downtime events for all clients"""
        # Create downtime for both clients
        down_a = DowntimeEventCreate(
            machine_id=machine_client_a.machine_id,
            shift_id=shift_day.shift_id,
            downtime_date=date.today(),
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=1),
            duration_minutes=60,
            downtime_type="BREAKDOWN",
            reason="Mechanical failure",
            client_id_fk="CLIENT-A"
        )
        down_b = DowntimeEventCreate(
            machine_id=machine_client_b.machine_id,
            shift_id=shift_day.shift_id,
            downtime_date=date.today(),
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(hours=2),
            duration_minutes=120,
            downtime_type="MAINTENANCE",
            reason="Scheduled maintenance",
            client_id_fk="CLIENT-B"
        )

        created_a = create_downtime_event(test_db, down_a, operator_client_a)
        created_b = create_downtime_event(test_db, down_b, operator_client_b)

        # ADMIN queries all downtime
        results = get_downtime_events(test_db, admin_user)

        # Verify both clients' records returned
        assert len(results) >= 2
        client_ids = set(r.client_id_fk for r in results)
        assert "CLIENT-A" in client_ids
        assert "CLIENT-B" in client_ids

        # Verify specific records exist
        record_ids = [r.downtime_id for r in results]
        assert created_a.downtime_id in record_ids
        assert created_b.downtime_id in record_ids


class TestDowntimeDataLeakagePrevention:
    """Test cross-client downtime data leakage prevention"""

    def test_downtime_metrics_isolated_by_client(
        self, test_db, operator_client_a, operator_client_b,
        machine_client_a, machine_client_b, shift_day
    ):
        """Downtime metrics and statistics isolated by client"""
        # Client A: Low downtime (2 hours total)
        for i in range(2):
            down_a = DowntimeEventCreate(
                machine_id=machine_client_a.machine_id,
                shift_id=shift_day.shift_id,
                downtime_date=date.today(),
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=1),
                duration_minutes=60,
                downtime_type="BREAKDOWN",
                reason=f"Issue {i+1}",
                client_id_fk="CLIENT-A"
            )
            create_downtime_event(test_db, down_a, operator_client_a)

        # Client B: High downtime (8 hours total)
        for i in range(4):
            down_b = DowntimeEventCreate(
                machine_id=machine_client_b.machine_id,
                shift_id=shift_day.shift_id,
                downtime_date=date.today(),
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=2),
                duration_minutes=120,
                downtime_type="BREAKDOWN",
                reason=f"Issue {i+1}",
                client_id_fk="CLIENT-B"
            )
            create_downtime_event(test_db, down_b, operator_client_b)

        # Client A queries their downtime metrics
        results_a = get_downtime_events(test_db, operator_client_a)
        total_downtime_a = sum(r.duration_minutes for r in results_a)

        assert len(results_a) == 2
        assert total_downtime_a == 120  # 2 hours

        # Client B queries their downtime metrics
        results_b = get_downtime_events(test_db, operator_client_b)
        total_downtime_b = sum(r.duration_minutes for r in results_b)

        assert len(results_b) == 4
        assert total_downtime_b == 480  # 8 hours


class TestDowntimeDateRangeIsolation:
    """Test date range filtering maintains client isolation"""

    def test_date_range_query_respects_client_boundary(
        self, test_db, operator_client_a, operator_client_b,
        machine_client_a, machine_client_b, shift_day
    ):
        """Date range queries maintain client isolation"""
        # Create downtime for multiple dates
        dates = [date.today() - timedelta(days=i) for i in range(7)]

        for downtime_date in dates:
            # Client A downtime
            down_a = DowntimeEventCreate(
                machine_id=machine_client_a.machine_id,
                shift_id=shift_day.shift_id,
                downtime_date=downtime_date,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=1),
                duration_minutes=60,
                downtime_type="BREAKDOWN",
                reason="Daily issue",
                client_id_fk="CLIENT-A"
            )
            # Client B downtime
            down_b = DowntimeEventCreate(
                machine_id=machine_client_b.machine_id,
                shift_id=shift_day.shift_id,
                downtime_date=downtime_date,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=1),
                duration_minutes=60,
                downtime_type="BREAKDOWN",
                reason="Daily issue",
                client_id_fk="CLIENT-B"
            )

            create_downtime_event(test_db, down_a, operator_client_a)
            create_downtime_event(test_db, down_b, operator_client_b)

        # Client A queries date range
        results_a = get_downtime_events(
            test_db,
            operator_client_a,
            start_date=dates[-1],
            end_date=dates[0]
        )

        # Verify only Client A records
        assert len(results_a) == 7
        assert all(r.client_id_fk == "CLIENT-A" for r in results_a)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
