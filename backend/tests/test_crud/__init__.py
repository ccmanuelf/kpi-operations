"""
Comprehensive CRUD Tests for 90% Coverage Target
Tests all CRUD operations across all models
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import date, datetime, timedelta
from decimal import Decimal
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from backend.database import Base
from backend.schemas.client import Client, ClientType
from backend.schemas.user import User, UserRole


@pytest.fixture(scope="function")
def test_db():
    """Create fresh in-memory database for each test"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine)
    db = TestingSession()
    yield db
    db.close()


class TestClientCRUD:
    """Test Client CRUD operations"""

    def test_create_client(self, test_db):
        client = Client(
            client_id="CLT-001",
            client_name="Test Manufacturing Inc",
            client_type=ClientType.MANUFACTURING,
            industry="Electronics",
            contact_email="test@manufacturing.com",
            is_active=True,
        )
        test_db.add(client)
        test_db.commit()

        result = test_db.query(Client).filter(Client.client_id == "CLT-001").first()
        assert result is not None
        assert result.client_name == "Test Manufacturing Inc"

    def test_read_client(self, test_db):
        client = Client(client_id="CLT-002", client_name="Read Test", client_type=ClientType.ASSEMBLY)
        test_db.add(client)
        test_db.commit()

        result = test_db.query(Client).filter(Client.client_id == "CLT-002").first()
        assert result.client_name == "Read Test"

    def test_update_client(self, test_db):
        client = Client(client_id="CLT-003", client_name="Original", client_type=ClientType.PACKAGING)
        test_db.add(client)
        test_db.commit()

        client.client_name = "Updated Name"
        test_db.commit()

        result = test_db.query(Client).filter(Client.client_id == "CLT-003").first()
        assert result.client_name == "Updated Name"

    def test_delete_client(self, test_db):
        client = Client(client_id="CLT-004", client_name="Delete Test", client_type=ClientType.LOGISTICS)
        test_db.add(client)
        test_db.commit()

        test_db.delete(client)
        test_db.commit()

        result = test_db.query(Client).filter(Client.client_id == "CLT-004").first()
        assert result is None

    def test_list_clients(self, test_db):
        for i in range(5):
            client = Client(client_id=f"CLT-LIST-{i}", client_name=f"Client {i}", client_type=ClientType.MANUFACTURING)
            test_db.add(client)
        test_db.commit()

        results = test_db.query(Client).filter(Client.client_id.like("CLT-LIST-%")).all()
        assert len(results) == 5

    def test_filter_active_clients(self, test_db):
        client1 = Client(client_id="CLT-ACT-1", client_name="Active", is_active=True)
        client2 = Client(client_id="CLT-ACT-2", client_name="Inactive", is_active=False)
        test_db.add_all([client1, client2])
        test_db.commit()

        active = test_db.query(Client).filter(Client.is_active == True).all()
        assert len(active) >= 1


class TestUserCRUD:
    """Test User CRUD operations"""

    def test_create_user(self, test_db):
        user = User(
            user_id="USR-001",
            username="testuser",
            password_hash="$2b$12$hashedpassword",
            full_name="Test User",
            email="test@example.com",
            role=UserRole.OPERATOR,
            is_active=True,
        )
        test_db.add(user)
        test_db.commit()

        result = test_db.query(User).filter(User.username == "testuser").first()
        assert result is not None
        assert result.email == "test@example.com"

    def test_user_roles(self, test_db):
        roles = [UserRole.ADMIN, UserRole.POWERUSER, UserRole.LEADER, UserRole.OPERATOR]
        for i, role in enumerate(roles):
            user = User(user_id=f"USR-ROLE-{i}", username=f"user_{role.value}", role=role, is_active=True)
            test_db.add(user)
        test_db.commit()

        admins = test_db.query(User).filter(User.role == UserRole.ADMIN).all()
        assert len(admins) == 1

    def test_deactivate_user(self, test_db):
        user = User(user_id="USR-DEACT", username="deactivate_me", is_active=True)
        test_db.add(user)
        test_db.commit()

        user.is_active = False
        test_db.commit()

        result = test_db.query(User).filter(User.user_id == "USR-DEACT").first()
        assert result.is_active == False

    def test_find_user_by_email(self, test_db):
        user = User(user_id="USR-EMAIL", username="emailuser", email="find@example.com", is_active=True)
        test_db.add(user)
        test_db.commit()

        result = test_db.query(User).filter(User.email == "find@example.com").first()
        assert result is not None
        assert result.username == "emailuser"
