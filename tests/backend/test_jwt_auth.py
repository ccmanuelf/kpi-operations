"""
Unit Tests for JWT Authentication Module
Tests token creation, verification, password hashing, and user dependencies
"""

import pytest
from datetime import datetime, timedelta
from jose import jwt, JWTError
from unittest.mock import Mock, patch


@pytest.mark.unit
class TestPasswordHashing:
    """Test password hashing and verification"""

    def test_password_hash_creates_hash(self):
        """Test password is hashed"""
        from backend.auth.jwt import get_password_hash

        password = "TestPassword123!"
        hashed = get_password_hash(password)

        assert hashed is not None
        assert hashed != password
        assert len(hashed) > 20  # Bcrypt hashes are long

    def test_password_hash_is_different_each_time(self):
        """Test same password creates different hashes (salt)"""
        from backend.auth.jwt import get_password_hash

        password = "TestPassword123!"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        assert hash1 != hash2  # Salt makes them different

    def test_verify_password_correct(self):
        """Test correct password verification"""
        from backend.auth.jwt import get_password_hash, verify_password

        password = "TestPassword123!"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) == True

    def test_verify_password_incorrect(self):
        """Test incorrect password verification"""
        from backend.auth.jwt import get_password_hash, verify_password

        password = "TestPassword123!"
        hashed = get_password_hash(password)

        assert verify_password("WrongPassword", hashed) == False

    def test_password_hash_empty_string(self):
        """Test hashing empty password"""
        from backend.auth.jwt import get_password_hash

        hashed = get_password_hash("")
        assert hashed is not None
        assert len(hashed) > 0


@pytest.mark.unit
class TestTokenCreation:
    """Test JWT token creation"""

    def test_create_access_token_basic(self):
        """Test basic token creation"""
        from backend.auth.jwt import create_access_token

        data = {"sub": "testuser"}
        token = create_access_token(data)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 20

    def test_create_access_token_contains_data(self):
        """Test token contains the provided data"""
        from backend.auth.jwt import create_access_token
        from backend.config import settings

        data = {"sub": "testuser"}
        token = create_access_token(data)

        # Decode without verification to check payload
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_create_access_token_custom_expiry(self):
        """Test token with custom expiry time"""
        from backend.auth.jwt import create_access_token
        from backend.config import settings

        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=15)
        token = create_access_token(data, expires_delta)

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp_timestamp = payload["exp"]

        # Should expire in ~15 minutes
        now = datetime.utcnow()
        exp_time = datetime.fromtimestamp(exp_timestamp)
        time_diff = (exp_time - now).total_seconds()

        assert 14 * 60 < time_diff < 16 * 60  # Between 14-16 minutes

    def test_create_access_token_default_expiry(self):
        """Test token uses default expiry from settings"""
        from backend.auth.jwt import create_access_token
        from backend.config import settings

        data = {"sub": "testuser"}
        token = create_access_token(data)

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp_timestamp = payload["exp"]

        now = datetime.utcnow()
        exp_time = datetime.fromtimestamp(exp_timestamp)
        time_diff = (exp_time - now).total_seconds() / 60  # Convert to minutes

        assert abs(time_diff - settings.ACCESS_TOKEN_EXPIRE_MINUTES) < 1


@pytest.mark.unit
class TestTokenValidation:
    """Test JWT token validation and user extraction"""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """Test extracting user from valid token"""
        from backend.auth.jwt import create_access_token, get_current_user
        from backend.schemas.user import User
        from unittest.mock import AsyncMock

        # Create test user
        test_user = User(
            user_id=1,
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            role="OPERATOR_DATAENTRY",
            is_active=True
        )

        # Create valid token
        token = create_access_token({"sub": "testuser"})

        # Mock database
        mock_db = Mock()
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.first.return_value = test_user
        mock_query.filter.return_value = mock_filter
        mock_db.query.return_value = mock_query

        # Get current user
        user = await get_current_user(token=token, db=mock_db)

        assert user is not None
        assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(self):
        """Test expired token raises exception"""
        from backend.auth.jwt import create_access_token, get_current_user
        from fastapi import HTTPException

        # Create expired token
        expired_delta = timedelta(minutes=-1)
        token = create_access_token({"sub": "testuser"}, expired_delta)

        mock_db = Mock()

        # Should raise HTTPException for expired token
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=mock_db)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test invalid token raises exception"""
        from backend.auth.jwt import get_current_user
        from fastapi import HTTPException

        invalid_token = "invalid.token.here"
        mock_db = Mock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=invalid_token, db=mock_db)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_no_username(self):
        """Test token without username raises exception"""
        from backend.auth.jwt import create_access_token, get_current_user
        from fastapi import HTTPException

        # Token without 'sub' field
        token = create_access_token({"user_id": 1})
        mock_db = Mock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token=token, db=mock_db)

        assert exc_info.value.status_code == 401


@pytest.mark.unit
class TestUserDependencies:
    """Test user dependency functions"""

    @pytest.mark.asyncio
    async def test_get_current_active_supervisor(self):
        """Test supervisor role check"""
        from backend.auth.jwt import get_current_active_supervisor
        from backend.schemas.user import User
        from fastapi import HTTPException

        # Test with supervisor
        supervisor = User(
            user_id=1,
            username="supervisor",
            email="supervisor@example.com",
            role="LEADER_DATACONFIG",
            is_active=True
        )

        result = await get_current_active_supervisor(supervisor)
        assert result.username == "supervisor"

        # Test with non-supervisor
        operator = User(
            user_id=2,
            username="operator",
            email="operator@example.com",
            role="OPERATOR_DATAENTRY",
            is_active=True
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_supervisor(operator)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_current_active_supervisor_inactive_user(self):
        """Test inactive supervisor is rejected"""
        from backend.auth.jwt import get_current_active_supervisor
        from backend.schemas.user import User
        from fastapi import HTTPException

        inactive_supervisor = User(
            user_id=1,
            username="inactive_supervisor",
            email="supervisor@example.com",
            role="LEADER_DATACONFIG",
            is_active=False
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_supervisor(inactive_supervisor)

        assert exc_info.value.status_code == 403


@pytest.mark.security
class TestSecurityFeatures:
    """Test security features of JWT implementation"""

    def test_token_signature_verification(self):
        """Test token signature is verified"""
        from backend.auth.jwt import create_access_token
        from backend.config import settings
        from jose import jwt, JWTError

        token = create_access_token({"sub": "testuser"})

        # Valid signature
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "testuser"

        # Invalid signature (wrong key)
        with pytest.raises(JWTError):
            jwt.decode(token, "wrong-secret-key", algorithms=[settings.ALGORITHM])

    def test_token_algorithm_enforcement(self):
        """Test only allowed algorithm is accepted"""
        from backend.auth.jwt import create_access_token
        from backend.config import settings
        from jose import jwt, JWTError

        token = create_access_token({"sub": "testuser"})

        # Should fail with wrong algorithm
        with pytest.raises(JWTError):
            jwt.decode(token, settings.SECRET_KEY, algorithms=["HS512"])


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_hash_special_characters_password(self):
        """Test password with special characters"""
        from backend.auth.jwt import get_password_hash, verify_password

        password = "P@ssw0rd!@#$%^&*()_+-=[]{}|;:'\",.<>?/~`"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) == True

    def test_hash_unicode_password(self):
        """Test password with unicode characters"""
        from backend.auth.jwt import get_password_hash, verify_password

        password = "пароль密码🔐"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) == True

    def test_token_with_complex_data(self):
        """Test token with complex data payload"""
        from backend.auth.jwt import create_access_token
        from backend.config import settings
        from jose import jwt

        data = {
            "sub": "testuser",
            "role": "ADMIN",
            "permissions": ["read", "write", "delete"],
            "metadata": {"client_id": 123}
        }

        token = create_access_token(data)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        assert payload["sub"] == "testuser"
        assert payload["role"] == "ADMIN"
        assert "exp" in payload


@pytest.mark.performance
class TestPerformance:
    """Test performance of auth operations"""

    def test_password_hashing_performance(self):
        """Test password hashing is reasonably fast"""
        from backend.auth.jwt import get_password_hash
        import time

        password = "TestPassword123!"

        start = time.time()
        for _ in range(10):
            get_password_hash(password)
        duration = time.time() - start

        # 10 hashes should complete in reasonable time
        assert duration < 5.0  # Bcrypt is intentionally slow, but not too slow

    def test_token_creation_performance(self):
        """Test token creation is fast"""
        from backend.auth.jwt import create_access_token
        import time

        data = {"sub": "testuser"}

        start = time.time()
        for _ in range(1000):
            create_access_token(data)
        duration = time.time() - start

        assert duration < 1.0  # 1000 tokens in < 1 second
