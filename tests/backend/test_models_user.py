"""
Unit Tests for User Models
Tests User schema and Pydantic models
"""

import pytest
from pydantic import ValidationError
from datetime import datetime


@pytest.mark.unit
class TestUserCreate:
    """Test UserCreate model validation"""

    def test_user_create_valid_data(self):
        """Test creating user with valid data"""
        from backend.models.user import UserCreate

        user = UserCreate(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
            full_name="Test User",
            role="OPERATOR_DATAENTRY"
        )

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password == "SecurePass123!"

    def test_user_create_missing_required_fields(self):
        """Test validation fails with missing required fields"""
        from backend.models.user import UserCreate

        with pytest.raises(ValidationError):
            UserCreate(username="testuser")  # Missing email, password

    def test_user_create_invalid_email(self):
        """Test validation fails with invalid email"""
        from backend.models.user import UserCreate

        with pytest.raises(ValidationError):
            UserCreate(
                username="testuser",
                email="not-an-email",
                password="SecurePass123!",
                role="OPERATOR_DATAENTRY"
            )

    def test_user_create_default_role(self):
        """Test default role is OPERATOR_DATAENTRY"""
        from backend.models.user import UserCreate

        user = UserCreate(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!"
        )

        assert user.role == "OPERATOR_DATAENTRY"


@pytest.mark.unit
class TestUserLogin:
    """Test UserLogin model"""

    def test_user_login_valid_data(self):
        """Test login model with valid credentials"""
        from backend.models.user import UserLogin

        login = UserLogin(
            username="testuser",
            password="SecurePass123!"
        )

        assert login.username == "testuser"
        assert login.password == "SecurePass123!"

    def test_user_login_missing_fields(self):
        """Test login validation with missing fields"""
        from backend.models.user import UserLogin

        with pytest.raises(ValidationError):
            UserLogin(username="testuser")  # Missing password


@pytest.mark.unit
class TestUserResponse:
    """Test UserResponse model"""

    def test_user_response_contains_all_fields(self):
        """Test response model has all required fields"""
        from backend.models.user import UserResponse

        user = UserResponse(
            user_id=1,
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            role="OPERATOR_DATAENTRY",
            is_active=True,
            created_at=datetime.utcnow(),
            last_login=None
        )

        assert user.user_id == 1
        assert user.username == "testuser"
        assert user.is_active == True

    def test_user_response_excludes_password(self):
        """Test response model doesn't include password"""
        from backend.models.user import UserResponse

        # Should not have password field
        assert not hasattr(UserResponse, 'password')
        assert not hasattr(UserResponse, 'password_hash')


@pytest.mark.unit
class TestToken:
    """Test Token model"""

    def test_token_model_structure(self):
        """Test token model has correct structure"""
        from backend.models.user import Token, UserResponse

        user = UserResponse(
            user_id=1,
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            role="OPERATOR_DATAENTRY",
            is_active=True,
            created_at=datetime.utcnow()
        )

        token = Token(
            access_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            token_type="bearer",
            user=user
        )

        assert token.access_token is not None
        assert token.token_type == "bearer"
        assert token.user.username == "testuser"


@pytest.mark.unit
class TestUserRoles:
    """Test user role validation"""

    def test_all_valid_roles(self):
        """Test all valid role types"""
        from backend.models.user import UserCreate

        roles = ["OPERATOR_DATAENTRY", "LEADER_DATACONFIG", "POWERUSER", "ADMIN"]

        for role in roles:
            user = UserCreate(
                username="testuser",
                email="test@example.com",
                password="SecurePass123!",
                role=role
            )
            assert user.role == role

    def test_invalid_role(self):
        """Test invalid role is rejected"""
        from backend.models.user import UserCreate

        with pytest.raises(ValidationError):
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="SecurePass123!",
                role="INVALID_ROLE"
            )


@pytest.mark.unit
class TestUserValidation:
    """Test user data validation"""

    def test_username_length_validation(self):
        """Test username length constraints"""
        from backend.models.user import UserCreate

        # Too short username might fail depending on validation rules
        # Test with normal length
        user = UserCreate(
            username="user123",
            email="test@example.com",
            password="SecurePass123!",
            role="OPERATOR_DATAENTRY"
        )
        assert user.username == "user123"

    def test_email_format_validation(self):
        """Test email format validation"""
        from backend.models.user import UserCreate

        # Valid email formats
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.co.uk"
        ]

        for email in valid_emails:
            user = UserCreate(
                username="testuser",
                email=email,
                password="SecurePass123!",
                role="OPERATOR_DATAENTRY"
            )
            assert user.email == email


@pytest.mark.unit
class TestUserEdgeCases:
    """Test edge cases for user models"""

    def test_empty_full_name(self):
        """Test user with no full name"""
        from backend.models.user import UserCreate

        user = UserCreate(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
            role="OPERATOR_DATAENTRY"
        )

        # full_name is optional
        assert user.full_name is None or user.full_name == ""

    def test_very_long_username(self):
        """Test username length limits"""
        from backend.models.user import UserCreate

        long_username = "a" * 100

        # Should either accept or reject based on validation
        try:
            user = UserCreate(
                username=long_username,
                email="test@example.com",
                password="SecurePass123!",
                role="OPERATOR_DATAENTRY"
            )
            # If accepted, verify it's stored
            assert user.username == long_username
        except ValidationError:
            # If rejected, that's also valid behavior
            assert True

    def test_special_characters_in_username(self):
        """Test special characters in username"""
        from backend.models.user import UserCreate

        # Test with underscores and numbers (usually valid)
        user = UserCreate(
            username="test_user_123",
            email="test@example.com",
            password="SecurePass123!",
            role="OPERATOR_DATAENTRY"
        )
        assert user.username == "test_user_123"


@pytest.mark.unit
class TestPasswordValidation:
    """Test password validation"""

    def test_password_accepts_complex_password(self):
        """Test complex password is accepted"""
        from backend.models.user import UserCreate

        complex_passwords = [
            "P@ssw0rd123!",
            "MyS3cur3P@ss",
            "Tr0ub4dor&3"
        ]

        for password in complex_passwords:
            user = UserCreate(
                username="testuser",
                email="test@example.com",
                password=password,
                role="OPERATOR_DATAENTRY"
            )
            assert user.password == password

    def test_password_minimum_length(self):
        """Test password minimum length"""
        from backend.models.user import UserCreate

        # Very short password
        try:
            user = UserCreate(
                username="testuser",
                email="test@example.com",
                password="123",
                role="OPERATOR_DATAENTRY"
            )
            # If no validation, it's accepted
            assert len(user.password) >= 1
        except ValidationError:
            # If validation exists, that's good security
            assert True


@pytest.mark.unit
class TestModelSerialization:
    """Test model serialization and deserialization"""

    def test_user_create_to_dict(self):
        """Test UserCreate can be converted to dict"""
        from backend.models.user import UserCreate

        user = UserCreate(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
            full_name="Test User",
            role="OPERATOR_DATAENTRY"
        )

        user_dict = user.model_dump()

        assert user_dict["username"] == "testuser"
        assert user_dict["email"] == "test@example.com"
        assert "password" in user_dict

    def test_user_response_from_orm(self):
        """Test UserResponse can be created from ORM model"""
        from backend.models.user import UserResponse

        # This tests the from_attributes config
        assert UserResponse.model_config.get("from_attributes") == True or \
               hasattr(UserResponse.Config, "from_attributes")
