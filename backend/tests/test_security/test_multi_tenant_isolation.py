"""
Test Suite for Multi-Tenant Isolation

Tests that client A cannot access client B's data.
Tests middleware enforcement and database query filtering.
Tests all CRUD operations for tenant isolation.

CRITICAL: These tests ensure data security in the multi-tenant system.
"""
import pytest
from fastapi import HTTPException

from middleware.client_auth import (
    get_user_client_filter,
    verify_client_access,
    build_client_filter_clause,
    ClientAccessError,
)
from backend.schemas.user import UserRole


class TestClientFilterGeneration:
    """Test client filter generation for different user roles"""

    def test_admin_has_access_to_all_clients(self, admin_user):
        """Test that ADMIN users can access all clients (no filtering)"""
        # When: Get client filter for admin
        client_filter = get_user_client_filter(admin_user)

        # Then: Should return None (no filtering)
        assert client_filter is None

    def test_operator_has_single_client_access(self, operator_user_client_a):
        """Test that OPERATOR gets single client filter"""
        # When: Get client filter for operator
        client_filter = get_user_client_filter(operator_user_client_a)

        # Then: Should return list with single client
        assert client_filter == ["CLIENT-A"]
        assert len(client_filter) == 1

    def test_leader_has_multi_client_access(self, leader_user_multi_client):
        """Test that LEADER can access multiple clients"""
        # When: Get client filter for leader
        client_filter = get_user_client_filter(leader_user_multi_client)

        # Then: Should return list with multiple clients
        assert "CLIENT-A" in client_filter
        assert "CLIENT-B" in client_filter
        assert len(client_filter) == 2

    def test_user_without_client_assignment_raises_error(self):
        """Test that user without client assignment raises error"""
        # Given: User without client assignment
        from backend.schemas.user import User

        user = User(
            user_id=99,
            username="no_client",
            email="no_client@test.com",
            role=UserRole.OPERATOR,
            client_id_assigned=None,  # No assignment
            is_active=True
        )

        # When/Then: Should raise ClientAccessError
        with pytest.raises(ClientAccessError) as exc_info:
            get_user_client_filter(user)

        assert "no client assignment" in str(exc_info.value.detail).lower()

    def test_user_with_empty_client_assignment_raises_error(self):
        """Test that user with empty string assignment raises error"""
        # Given: User with empty assignment
        from backend.schemas.user import User

        user = User(
            user_id=99,
            username="empty_client",
            email="empty@test.com",
            role=UserRole.OPERATOR,
            client_id_assigned="",  # Empty string
            is_active=True
        )

        # When/Then: Should raise ClientAccessError
        with pytest.raises(ClientAccessError) as exc_info:
            get_user_client_filter(user)

        # Error message should indicate missing/no client assignment
        assert "no client assignment" in str(exc_info.value.detail).lower()


class TestClientAccessVerification:
    """Test verify_client_access function"""

    def test_admin_can_access_any_client(self, admin_user):
        """Test that ADMIN can access any client's resources"""
        # When/Then: Should return True for any client
        assert verify_client_access(admin_user, "CLIENT-A") is True
        assert verify_client_access(admin_user, "CLIENT-B") is True
        assert verify_client_access(admin_user, "ANY-CLIENT") is True

    def test_operator_can_access_assigned_client(self, operator_user_client_a):
        """Test that OPERATOR can access their assigned client"""
        # When/Then: Should allow access to assigned client
        assert verify_client_access(operator_user_client_a, "CLIENT-A") is True

    def test_operator_cannot_access_other_client(self, operator_user_client_a):
        """Test that OPERATOR cannot access other clients"""
        # When/Then: Should raise ClientAccessError
        with pytest.raises(ClientAccessError) as exc_info:
            verify_client_access(operator_user_client_a, "CLIENT-B")

        assert "cannot access client" in str(exc_info.value.detail).lower()
        assert "CLIENT-B" in str(exc_info.value.detail)

    def test_leader_can_access_multiple_assigned_clients(self, leader_user_multi_client):
        """Test that LEADER can access all assigned clients"""
        # When/Then: Should allow access to both clients
        assert verify_client_access(leader_user_multi_client, "CLIENT-A") is True
        assert verify_client_access(leader_user_multi_client, "CLIENT-B") is True

    def test_leader_cannot_access_unassigned_client(self, leader_user_multi_client):
        """Test that LEADER cannot access unassigned clients"""
        # When/Then: Should deny access to CLIENT-C
        with pytest.raises(ClientAccessError) as exc_info:
            verify_client_access(leader_user_multi_client, "CLIENT-C")

        assert "cannot access client" in str(exc_info.value.detail).lower()
        assert "CLIENT-C" in str(exc_info.value.detail)


class TestDatabaseQueryFiltering:
    """Test SQLAlchemy query filtering"""

    def test_admin_query_has_no_filter(self, admin_user):
        """Test that ADMIN queries are not filtered"""
        # Given: Mock column
        from sqlalchemy import Column, String

        mock_column = Column("client_id", String)

        # When: Build filter clause
        filter_clause = build_client_filter_clause(admin_user, mock_column)

        # Then: Should return None (no filtering)
        assert filter_clause is None

    def test_operator_query_filters_to_single_client(self, operator_user_client_a):
        """Test that OPERATOR queries filter to assigned client"""
        # Given: Mock column
        from sqlalchemy import Column, String

        mock_column = Column("client_id", String)

        # When: Build filter clause
        filter_clause = build_client_filter_clause(operator_user_client_a, mock_column)

        # Then: Should create IN clause for CLIENT-A
        assert filter_clause is not None
        # Clause will be: client_id.in_(["CLIENT-A"])

    def test_leader_query_filters_to_multiple_clients(self, leader_user_multi_client):
        """Test that LEADER queries filter to assigned clients"""
        # Given: Mock column
        from sqlalchemy import Column, String

        mock_column = Column("client_id", String)

        # When: Build filter clause
        filter_clause = build_client_filter_clause(leader_user_multi_client, mock_column)

        # Then: Should create IN clause for CLIENT-A and CLIENT-B
        assert filter_clause is not None
        # Clause will be: client_id.in_(["CLIENT-A", "CLIENT-B"])


class TestCRUDIsolation:
    """Test CRUD operations respect tenant isolation"""

    def test_create_respects_client_assignment(self, db_session, operator_user_client_a):
        """Test that CREATE operations are scoped to user's client"""
        # This is more of an integration test - verifying that
        # when creating a record, the client_id is set correctly
        pass  # Placeholder for actual CRUD test

    def test_read_filters_by_client(self, db_session, operator_user_client_a, operator_user_client_b):
        """Test that READ operations only return user's client data"""
        # Given: Data for both clients
        from backend.schemas.production import ProductionEntry
        from datetime import date

        # Create entries for both clients
        entry_a = ProductionEntry(
            client_id="CLIENT-A",
            product_id=101,
            shift_id=1,
            work_order_number="WO-A-001",
            production_date=date(2024, 1, 15),
            units_produced=1000,
            employees_assigned=5,
            run_time_hours=8.0,
        )
        entry_b = ProductionEntry(
            client_id="CLIENT-B",
            product_id=101,
            shift_id=1,
            work_order_number="WO-B-001",
            production_date=date(2024, 1, 15),
            units_produced=1000,
            employees_assigned=5,
            run_time_hours=8.0,
        )

        db_session.add_all([entry_a, entry_b])
        db_session.commit()

        # When: Query with client filter for user A
        query = db_session.query(ProductionEntry)
        filter_clause = build_client_filter_clause(operator_user_client_a, ProductionEntry.client_id)
        if filter_clause is not None:
            query = query.filter(filter_clause)

        results_a = query.all()

        # Then: Should only get CLIENT-A entries
        assert len(results_a) == 1
        assert all(r.client_id == "CLIENT-A" for r in results_a)

        # When: Query with client filter for user B
        query = db_session.query(ProductionEntry)
        filter_clause = build_client_filter_clause(operator_user_client_b, ProductionEntry.client_id)
        if filter_clause is not None:
            query = query.filter(filter_clause)

        results_b = query.all()

        # Then: Should only get CLIENT-B entries
        assert len(results_b) == 1
        assert all(r.client_id == "CLIENT-B" for r in results_b)

    def test_update_prevents_cross_client_modification(self, db_session, operator_user_client_a):
        """Test that UPDATE operations cannot modify other client's data"""
        # Given: Entry for CLIENT-B
        from backend.schemas.production import ProductionEntry
        from datetime import date

        entry_b = ProductionEntry(
            client_id="CLIENT-B",
            product_id=101,
            shift_id=1,
            work_order_number="WO-B-001",
            production_date=date(2024, 1, 15),
            units_produced=1000,
            employees_assigned=5,
            run_time_hours=8.0,
        )
        db_session.add(entry_b)
        db_session.commit()

        # When: User A tries to query and update CLIENT-B entry
        query = db_session.query(ProductionEntry).filter(ProductionEntry.client_id == "CLIENT-B")
        filter_clause = build_client_filter_clause(operator_user_client_a, ProductionEntry.client_id)

        if filter_clause is not None:
            query = query.filter(filter_clause)

        results = query.all()

        # Then: Should not find any entries (filtered out)
        assert len(results) == 0

    def test_delete_prevents_cross_client_deletion(self, db_session, operator_user_client_a):
        """Test that DELETE operations cannot delete other client's data"""
        # Given: Entries for both clients
        from backend.schemas.production import ProductionEntry
        from datetime import date

        entry_a = ProductionEntry(
            client_id="CLIENT-A",
            product_id=101,
            shift_id=1,
            work_order_number="WO-A-001",
            production_date=date(2024, 1, 15),
            units_produced=1000,
            employees_assigned=5,
            run_time_hours=8.0,
        )
        entry_b = ProductionEntry(
            client_id="CLIENT-B",
            product_id=101,
            shift_id=1,
            work_order_number="WO-B-001",
            production_date=date(2024, 1, 15),
            units_produced=1000,
            employees_assigned=5,
            run_time_hours=8.0,
        )

        db_session.add_all([entry_a, entry_b])
        db_session.commit()

        # When: Try to delete with client filter
        query = db_session.query(ProductionEntry)
        filter_clause = build_client_filter_clause(operator_user_client_a, ProductionEntry.client_id)

        if filter_clause is not None:
            query = query.filter(filter_clause)

        # Delete operation
        deleted_count = query.delete()
        db_session.commit()

        # Then: Should only delete CLIENT-A entries
        assert deleted_count == 1

        # Verify CLIENT-B entry still exists
        remaining = db_session.query(ProductionEntry).filter(ProductionEntry.client_id == "CLIENT-B").all()
        assert len(remaining) == 1


class TestRealWorldIsolationScenarios:
    """Test real-world multi-tenant scenarios"""

    def test_production_dashboard_shows_only_client_data(self, db_session, test_data_factory):
        """Test that production dashboard respects client isolation"""
        # Given: Production entries for multiple clients
        test_data_factory.create_production_entries(db_session, 10, client_id="CLIENT-A")
        test_data_factory.create_production_entries(db_session, 10, client_id="CLIENT-B")

        # When: Operator A queries production entries
        from backend.schemas.user import User

        operator_a = User(
            user_id=2,
            username="operator_a",
            email="operator_a@test.com",
            role=UserRole.OPERATOR,
            client_id_assigned="CLIENT-A",
            is_active=True
        )

        from backend.schemas.production import ProductionEntry

        query = db_session.query(ProductionEntry)
        filter_clause = build_client_filter_clause(operator_a, ProductionEntry.client_id)

        if filter_clause is not None:
            query = query.filter(filter_clause)

        results = query.all()

        # Then: Should only see CLIENT-A data
        assert len(results) == 10
        assert all(r.client_id == "CLIENT-A" for r in results)

    def test_kpi_reports_exclude_other_clients(self, db_session, test_data_factory):
        """Test that KPI reports are client-scoped"""
        # Given: Quality inspections for multiple clients
        test_data_factory.create_quality_inspections(db_session, 5, client_id="CLIENT-A", defect_rate=0.01)
        test_data_factory.create_quality_inspections(db_session, 5, client_id="CLIENT-B", defect_rate=0.05)

        # When: Calculate KPIs for CLIENT-A operator
        from backend.schemas.user import User

        operator_a = User(
            user_id=2,
            username="operator_a",
            email="operator_a@test.com",
            role=UserRole.OPERATOR,
            client_id_assigned="CLIENT-A",
            is_active=True
        )

        from backend.schemas.quality import QualityInspection

        query = db_session.query(QualityInspection)
        filter_clause = build_client_filter_clause(operator_a, QualityInspection.client_id)

        if filter_clause is not None:
            query = query.filter(filter_clause)

        results = query.all()

        # Then: Should only include CLIENT-A inspections
        assert len(results) == 5
        assert all(r.client_id == "CLIENT-A" for r in results)

        # Calculate PPM for CLIENT-A only
        total_inspected = sum(r.units_inspected for r in results)
        total_defects = sum(r.defects_found for r in results)

        # CLIENT-A has 1% defect rate
        assert total_defects / total_inspected == pytest.approx(0.01, rel=0.001)

    def test_leader_aggregates_multiple_clients(self, db_session, test_data_factory):
        """Test that LEADER can see aggregated data for assigned clients"""
        # Given: Data for 3 clients
        test_data_factory.create_production_entries(db_session, 5, client_id="CLIENT-A")
        test_data_factory.create_production_entries(db_session, 5, client_id="CLIENT-B")
        test_data_factory.create_production_entries(db_session, 5, client_id="CLIENT-C")

        # When: Leader with CLIENT-A and CLIENT-B access queries
        from backend.schemas.user import User

        leader = User(
            user_id=4,
            username="leader",
            email="leader@test.com",
            role=UserRole.LEADER,
            client_id_assigned="CLIENT-A,CLIENT-B",
            is_active=True
        )

        from backend.schemas.production import ProductionEntry

        query = db_session.query(ProductionEntry)
        filter_clause = build_client_filter_clause(leader, ProductionEntry.client_id)

        if filter_clause is not None:
            query = query.filter(filter_clause)

        results = query.all()

        # Then: Should see CLIENT-A and CLIENT-B, but not CLIENT-C
        assert len(results) == 10
        clients = {r.client_id for r in results}
        assert "CLIENT-A" in clients
        assert "CLIENT-B" in clients
        assert "CLIENT-C" not in clients
