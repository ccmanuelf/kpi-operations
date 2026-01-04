"""
Multi-Tenant Quality Inspection Client Isolation Tests
Tests strict data isolation for quality inspections between clients
CRITICAL: Ensures quality data cannot leak between clients
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from backend.schemas.user import User
from backend.schemas.client import Client
from backend.schemas.product import Product
from backend.schemas.shift import Shift
from backend.models.quality import QualityInspectionCreate
from backend.crud.quality import (
    create_quality_inspection,
    get_quality_inspections,
    get_quality_inspection,
    update_quality_inspection,
    delete_quality_inspection
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
def product_a(test_db: Session):
    """Create product A"""
    product = Product(
        product_code="PROD-A",
        product_name="Product A",
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    return product


@pytest.fixture
def product_b(test_db: Session):
    """Create product B"""
    product = Product(
        product_code="PROD-B",
        product_name="Product B",
        is_active=True
    )
    test_db.add(product)
    test_db.commit()
    return product


class TestQualityOperatorIsolation:
    """Test OPERATOR role quality inspection isolation"""

    def test_operator_cannot_see_other_client_inspections(
        self, test_db, operator_client_a, operator_client_b,
        product_a, product_b, shift_day
    ):
        """Client A OPERATOR cannot see Client B quality inspections"""
        # Create inspections for both clients
        insp_a = QualityInspectionCreate(
            product_id=product_a.product_id,
            shift_id=shift_day.shift_id,
            inspection_date=date.today(),
            units_inspected=100,
            units_passed=95,
            units_failed=5,
            inspection_stage="FINAL",
            defect_count=5,
            client_id_fk="CLIENT-A"
        )
        insp_b = QualityInspectionCreate(
            product_id=product_b.product_id,
            shift_id=shift_day.shift_id,
            inspection_date=date.today(),
            units_inspected=200,
            units_passed=180,
            units_failed=20,
            inspection_stage="FINAL",
            defect_count=20,
            client_id_fk="CLIENT-B"
        )

        created_a = create_quality_inspection(test_db, insp_a, operator_client_a)
        created_b = create_quality_inspection(test_db, insp_b, operator_client_b)

        # Client A OPERATOR queries inspections
        results_a = get_quality_inspections(test_db, operator_client_a)

        # Verify only Client A's records returned
        assert len(results_a) == 1
        assert all(r.client_id_fk == "CLIENT-A" for r in results_a)
        assert results_a[0].inspection_id == created_a.inspection_id

        # Verify Client B's record is not visible
        assert not any(r.inspection_id == created_b.inspection_id for r in results_a)

    def test_operator_cannot_access_other_client_inspection_by_id(
        self, test_db, operator_client_a, operator_client_b,
        product_b, shift_day
    ):
        """OPERATOR cannot access specific inspection from other client"""
        # Create inspection for Client B
        insp_b = QualityInspectionCreate(
            product_id=product_b.product_id,
            shift_id=shift_day.shift_id,
            inspection_date=date.today(),
            units_inspected=200,
            units_passed=180,
            units_failed=20,
            inspection_stage="FINAL",
            defect_count=20,
            client_id_fk="CLIENT-B"
        )
        created_b = create_quality_inspection(test_db, insp_b, operator_client_b)

        # Client A OPERATOR tries to access Client B's record
        result = get_quality_inspection(test_db, created_b.inspection_id, operator_client_a)

        # Should return None (access denied)
        assert result is None

    def test_operator_cannot_update_other_client_inspection(
        self, test_db, operator_client_a, operator_client_b,
        product_b, shift_day
    ):
        """OPERATOR cannot update inspection from other client"""
        # Create inspection for Client B
        insp_b = QualityInspectionCreate(
            product_id=product_b.product_id,
            shift_id=shift_day.shift_id,
            inspection_date=date.today(),
            units_inspected=200,
            units_passed=180,
            units_failed=20,
            inspection_stage="FINAL",
            defect_count=20,
            client_id_fk="CLIENT-B"
        )
        created_b = create_quality_inspection(test_db, insp_b, operator_client_b)

        # Client A OPERATOR tries to update Client B's record
        update_data = {"units_passed": 190, "units_failed": 10, "defect_count": 10}
        result = update_quality_inspection(
            test_db,
            created_b.inspection_id,
            update_data,
            operator_client_a
        )

        # Should return None (access denied)
        assert result is None

        # Verify record unchanged
        original = get_quality_inspection(test_db, created_b.inspection_id, operator_client_b)
        assert original.units_passed == 180
        assert original.units_failed == 20


class TestQualityLeaderIsolation:
    """Test LEADER role quality inspection isolation"""

    def test_leader_restricted_to_assigned_client(
        self, test_db, leader_client_a, operator_client_b,
        product_a, product_b, shift_day
    ):
        """LEADER can only access their assigned client's inspections"""
        # Create inspections for both clients
        insp_a = QualityInspectionCreate(
            product_id=product_a.product_id,
            shift_id=shift_day.shift_id,
            inspection_date=date.today(),
            units_inspected=100,
            units_passed=95,
            units_failed=5,
            inspection_stage="FINAL",
            defect_count=5,
            client_id_fk="CLIENT-A"
        )
        insp_b = QualityInspectionCreate(
            product_id=product_b.product_id,
            shift_id=shift_day.shift_id,
            inspection_date=date.today(),
            units_inspected=200,
            units_passed=180,
            units_failed=20,
            inspection_stage="FINAL",
            defect_count=20,
            client_id_fk="CLIENT-B"
        )

        created_a = create_quality_inspection(test_db, insp_a, leader_client_a)
        created_b = create_quality_inspection(test_db, insp_b, operator_client_b)

        # LEADER queries inspections
        results = get_quality_inspections(test_db, leader_client_a)

        # Verify only assigned client's records
        assert len(results) == 1
        assert all(r.client_id_fk == "CLIENT-A" for r in results)
        assert not any(r.inspection_id == created_b.inspection_id for r in results)


class TestQualityAdminAccess:
    """Test ADMIN role can access all clients"""

    def test_admin_can_see_all_clients_inspections(
        self, test_db, admin_user, operator_client_a, operator_client_b,
        product_a, product_b, shift_day
    ):
        """ADMIN can access quality inspections for all clients"""
        # Create inspections for both clients
        insp_a = QualityInspectionCreate(
            product_id=product_a.product_id,
            shift_id=shift_day.shift_id,
            inspection_date=date.today(),
            units_inspected=100,
            units_passed=95,
            units_failed=5,
            inspection_stage="FINAL",
            defect_count=5,
            client_id_fk="CLIENT-A"
        )
        insp_b = QualityInspectionCreate(
            product_id=product_b.product_id,
            shift_id=shift_day.shift_id,
            inspection_date=date.today(),
            units_inspected=200,
            units_passed=180,
            units_failed=20,
            inspection_stage="FINAL",
            defect_count=20,
            client_id_fk="CLIENT-B"
        )

        created_a = create_quality_inspection(test_db, insp_a, operator_client_a)
        created_b = create_quality_inspection(test_db, insp_b, operator_client_b)

        # ADMIN queries all inspections
        results = get_quality_inspections(test_db, admin_user)

        # Verify both clients' records returned
        assert len(results) >= 2
        client_ids = set(r.client_id_fk for r in results)
        assert "CLIENT-A" in client_ids
        assert "CLIENT-B" in client_ids

        # Verify specific records exist
        record_ids = [r.inspection_id for r in results]
        assert created_a.inspection_id in record_ids
        assert created_b.inspection_id in record_ids


class TestQualityDataLeakagePrevention:
    """Test cross-client data leakage prevention"""

    def test_defect_data_isolated_by_client(
        self, test_db, operator_client_a, operator_client_b,
        product_a, product_b, shift_day
    ):
        """Defect counts and quality metrics isolated by client"""
        # Client A: High quality (95% pass rate)
        insp_a = QualityInspectionCreate(
            product_id=product_a.product_id,
            shift_id=shift_day.shift_id,
            inspection_date=date.today(),
            units_inspected=1000,
            units_passed=950,
            units_failed=50,
            inspection_stage="FINAL",
            defect_count=50,
            client_id_fk="CLIENT-A"
        )

        # Client B: Low quality (70% pass rate)
        insp_b = QualityInspectionCreate(
            product_id=product_b.product_id,
            shift_id=shift_day.shift_id,
            inspection_date=date.today(),
            units_inspected=1000,
            units_passed=700,
            units_failed=300,
            inspection_stage="FINAL",
            defect_count=300,
            client_id_fk="CLIENT-B"
        )

        create_quality_inspection(test_db, insp_a, operator_client_a)
        create_quality_inspection(test_db, insp_b, operator_client_b)

        # Client A queries their quality metrics
        results_a = get_quality_inspections(test_db, operator_client_a)

        # Verify Client A only sees their own quality data
        assert len(results_a) == 1
        assert results_a[0].units_passed == 950
        assert results_a[0].defect_count == 50

        # Client B queries their quality metrics
        results_b = get_quality_inspections(test_db, operator_client_b)

        # Verify Client B only sees their own quality data
        assert len(results_b) == 1
        assert results_b[0].units_passed == 700
        assert results_b[0].defect_count == 300

    def test_quality_kpi_calculation_isolated(
        self, test_db, operator_client_a, operator_client_b,
        product_a, product_b, shift_day
    ):
        """Quality KPI calculations respect client boundaries"""
        # Create multiple inspections for each client
        for i in range(5):
            # Client A: Consistent 95% quality
            insp_a = QualityInspectionCreate(
                product_id=product_a.product_id,
                shift_id=shift_day.shift_id,
                inspection_date=date.today() - timedelta(days=i),
                units_inspected=100,
                units_passed=95,
                units_failed=5,
                inspection_stage="FINAL",
                defect_count=5,
                client_id_fk="CLIENT-A"
            )
            create_quality_inspection(test_db, insp_a, operator_client_a)

            # Client B: Consistent 80% quality
            insp_b = QualityInspectionCreate(
                product_id=product_b.product_id,
                shift_id=shift_day.shift_id,
                inspection_date=date.today() - timedelta(days=i),
                units_inspected=100,
                units_passed=80,
                units_failed=20,
                inspection_stage="FINAL",
                defect_count=20,
                client_id_fk="CLIENT-B"
            )
            create_quality_inspection(test_db, insp_b, operator_client_b)

        # Verify Client A's quality metrics not affected by Client B
        results_a = get_quality_inspections(test_db, operator_client_a)
        total_passed_a = sum(r.units_passed for r in results_a)
        total_inspected_a = sum(r.units_inspected for r in results_a)
        quality_rate_a = (total_passed_a / total_inspected_a) * 100

        assert len(results_a) == 5
        assert quality_rate_a == 95.0

        # Verify Client B's quality metrics not affected by Client A
        results_b = get_quality_inspections(test_db, operator_client_b)
        total_passed_b = sum(r.units_passed for r in results_b)
        total_inspected_b = sum(r.units_inspected for r in results_b)
        quality_rate_b = (total_passed_b / total_inspected_b) * 100

        assert len(results_b) == 5
        assert quality_rate_b == 80.0


class TestQualityDateRangeIsolation:
    """Test date range filtering maintains client isolation"""

    def test_date_range_query_respects_client_boundary(
        self, test_db, operator_client_a, operator_client_b,
        product_a, product_b, shift_day
    ):
        """Date range queries maintain client isolation"""
        # Create inspections for multiple dates
        dates = [date.today() - timedelta(days=i) for i in range(7)]

        for inspection_date in dates:
            # Client A inspection
            insp_a = QualityInspectionCreate(
                product_id=product_a.product_id,
                shift_id=shift_day.shift_id,
                inspection_date=inspection_date,
                units_inspected=100,
                units_passed=95,
                units_failed=5,
                inspection_stage="FINAL",
                defect_count=5,
                client_id_fk="CLIENT-A"
            )
            # Client B inspection
            insp_b = QualityInspectionCreate(
                product_id=product_b.product_id,
                shift_id=shift_day.shift_id,
                inspection_date=inspection_date,
                units_inspected=100,
                units_passed=80,
                units_failed=20,
                inspection_stage="FINAL",
                defect_count=20,
                client_id_fk="CLIENT-B"
            )

            create_quality_inspection(test_db, insp_a, operator_client_a)
            create_quality_inspection(test_db, insp_b, operator_client_b)

        # Client A queries date range
        results_a = get_quality_inspections(
            test_db,
            operator_client_a,
            start_date=dates[-1],
            end_date=dates[0]
        )

        # Verify only Client A records
        assert len(results_a) == 7
        assert all(r.client_id_fk == "CLIENT-A" for r in results_a)
        assert all(r.units_passed == 95 for r in results_a)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
