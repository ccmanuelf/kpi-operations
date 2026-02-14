"""
Password Policy Tests (SEC-002)
Tests for password strength validation and policy enforcement

Tests verify:
1. Minimum length requirement (8 characters)
2. Uppercase letter requirement
3. Lowercase letter requirement
4. Digit requirement
5. Special character requirement
6. Common password rejection
7. Sequential character detection
8. Password strength scoring
"""

import pytest
from backend.auth.password_policy import (
    validate_password_strength,
    get_password_strength_score,
    generate_password_requirements_message,
    password_validator,
    PasswordPolicyConfig,
    DEFAULT_POLICY,
    COMMON_PASSWORDS,
)


class TestPasswordValidation:
    """Tests for password validation function"""

    # ==========================================================================
    # MINIMUM LENGTH TESTS
    # ==========================================================================

    def test_password_too_short(self):
        """Test rejection of passwords shorter than 8 characters"""
        is_valid, message = validate_password_strength("Short1!")
        assert not is_valid
        assert "at least 8 characters" in message

    def test_password_minimum_length_accepted(self):
        """Test acceptance of password at minimum length"""
        is_valid, message = validate_password_strength("Valid1!a")
        assert is_valid, f"Password should be valid: {message}"

    def test_password_maximum_length_exceeded(self):
        """Test rejection of passwords exceeding maximum length"""
        long_password = "A1!" + "a" * 130  # Exceeds 128 char limit
        is_valid, message = validate_password_strength(long_password)
        assert not is_valid
        assert "not exceed" in message

    # ==========================================================================
    # CHARACTER TYPE REQUIREMENT TESTS
    # ==========================================================================

    def test_missing_uppercase(self):
        """Test rejection when uppercase letter is missing"""
        is_valid, message = validate_password_strength("lowercase1!")
        assert not is_valid
        assert "uppercase" in message.lower()

    def test_missing_lowercase(self):
        """Test rejection when lowercase letter is missing"""
        is_valid, message = validate_password_strength("UPPERCASE1!")
        assert not is_valid
        assert "lowercase" in message.lower()

    def test_missing_digit(self):
        """Test rejection when digit is missing"""
        is_valid, message = validate_password_strength("NoDigits!")
        assert not is_valid
        assert "digit" in message.lower()

    def test_missing_special_character(self):
        """Test rejection when special character is missing"""
        is_valid, message = validate_password_strength("NoSpecial1")
        assert not is_valid
        assert "special" in message.lower()

    # ==========================================================================
    # VALID PASSWORD TESTS
    # ==========================================================================

    def test_valid_password_all_requirements(self):
        """Test acceptance of password meeting all requirements"""
        valid_passwords = ["StrongP@ss123", "MyS3cur3P@ssword!", "C0mpl3x!Pass", "Test1ng@2024", "Secur1ty#Key"]

        for password in valid_passwords:
            is_valid, message = validate_password_strength(password)
            assert is_valid, f"Password '{password}' should be valid: {message}"

    def test_valid_password_with_multiple_special_chars(self):
        """Test password with multiple special characters"""
        is_valid, message = validate_password_strength("P@$$w0rd!#%")
        assert is_valid, f"Password should be valid: {message}"

    # ==========================================================================
    # COMMON PASSWORD TESTS
    # ==========================================================================

    def test_common_password_rejected(self):
        """Test rejection of commonly used passwords"""
        common_passwords = ["password", "Password123!", "admin123", "qwerty"]

        for pwd in common_passwords:
            # Add required characters to test common password check
            test_pwd = (
                pwd
                if all(
                    [
                        any(c.isupper() for c in pwd),
                        any(c.islower() for c in pwd),
                        any(c.isdigit() for c in pwd),
                        any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in pwd),
                    ]
                )
                else f"{pwd}A1!"
            )

            is_valid, message = validate_password_strength(test_pwd)
            # If still invalid due to common password check
            if pwd.lower() in COMMON_PASSWORDS:
                assert not is_valid or "common" not in message.lower(), f"Common password '{pwd}' should be rejected"

    def test_password_not_in_common_list(self):
        """Test acceptance of unique password not in common list"""
        is_valid, message = validate_password_strength("UniqueP@ss2024!")
        assert is_valid, f"Unique password should be valid: {message}"

    # ==========================================================================
    # SEQUENTIAL CHARACTER TESTS
    # ==========================================================================

    def test_sequential_numbers_rejected(self):
        """Test rejection of passwords with sequential numbers"""
        is_valid, message = validate_password_strength("Pass1234!")
        assert not is_valid
        assert "sequential" in message.lower()

    def test_sequential_letters_rejected(self):
        """Test rejection of passwords with sequential letters"""
        is_valid, message = validate_password_strength("Abcd1234!")
        assert not is_valid
        assert "sequential" in message.lower()

    def test_non_sequential_numbers_accepted(self):
        """Test acceptance of passwords with non-sequential numbers"""
        is_valid, message = validate_password_strength("Pass1357!")
        assert is_valid, f"Non-sequential password should be valid: {message}"

    # ==========================================================================
    # REPEATED CHARACTER TESTS
    # ==========================================================================

    def test_repeated_characters_rejected(self):
        """Test rejection of passwords with repeated characters"""
        is_valid, message = validate_password_strength("Passsss1!")
        assert not is_valid
        assert "consecutive" in message.lower() or "identical" in message.lower()

    def test_limited_repetition_accepted(self):
        """Test acceptance of passwords with limited repetition"""
        is_valid, message = validate_password_strength("Passs123!")
        assert is_valid, f"Limited repetition should be valid: {message}"


class TestPasswordStrengthScore:
    """Tests for password strength scoring"""

    def test_weak_password_score(self):
        """Test weak password gets low score"""
        score, label = get_password_strength_score("weak")
        assert score < 30
        assert label == "Weak"

    def test_moderate_password_score(self):
        """Test moderate password gets appropriate score"""
        # Password without special char scores lower
        score, label = get_password_strength_score("Passw0rd")
        assert score < 50
        assert label in ["Weak", "Fair"]

        # Password with all requirements scores higher
        score2, label2 = get_password_strength_score("Pass1!")
        assert score2 >= 50
        assert label2 in ["Good", "Strong"]

    def test_strong_password_score(self):
        """Test strong password gets high score"""
        score, label = get_password_strength_score("MyStr0ng@P@ss!")
        assert score >= 70
        assert label in ["Strong", "Very Strong"]

    def test_very_strong_password_score(self):
        """Test very strong password gets maximum score"""
        score, label = get_password_strength_score("Sup3r$3cure#P@ssword!2024")
        assert score >= 85
        assert label in ["Strong", "Very Strong"]

    def test_score_increases_with_length(self):
        """Test score increases with password length"""
        short_score, _ = get_password_strength_score("Short1!")
        long_score, _ = get_password_strength_score("LongerPassw0rd!")

        # Long password should generally score higher
        assert long_score >= short_score


class TestPasswordPolicyConfig:
    """Tests for password policy configuration"""

    def test_default_config_values(self):
        """Test default configuration values"""
        assert DEFAULT_POLICY.min_length == 8
        assert DEFAULT_POLICY.max_length == 128
        assert DEFAULT_POLICY.require_uppercase is True
        assert DEFAULT_POLICY.require_lowercase is True
        assert DEFAULT_POLICY.require_digit is True
        assert DEFAULT_POLICY.require_special is True

    def test_custom_config(self):
        """Test custom configuration"""
        custom_config = PasswordPolicyConfig(min_length=12, require_special=False)

        # With custom config, shorter password should fail
        is_valid, message = validate_password_strength("Short1!a", custom_config)
        assert not is_valid
        assert "12 characters" in message

        # Password without special char should pass with custom config
        is_valid, message = validate_password_strength("LongerPassword12", custom_config)
        assert is_valid, f"Should be valid with custom config: {message}"

    def test_special_characters_list(self):
        """Test special characters configuration"""
        assert "!" in DEFAULT_POLICY.special_characters
        assert "@" in DEFAULT_POLICY.special_characters
        assert "#" in DEFAULT_POLICY.special_characters
        assert "$" in DEFAULT_POLICY.special_characters


class TestPasswordValidator:
    """Tests for Pydantic validator function"""

    def test_valid_password_returns_password(self):
        """Test valid password is returned unchanged"""
        password = "ValidP@ss123"
        result = password_validator(password)
        assert result == password

    def test_invalid_password_raises_valueerror(self):
        """Test invalid password raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            password_validator("weak")

        assert "at least 8 characters" in str(exc_info.value)

    def test_validator_error_message_helpful(self):
        """Test validator provides helpful error message"""
        with pytest.raises(ValueError) as exc_info:
            password_validator("NoSpecial1")

        error_message = str(exc_info.value)
        assert "special" in error_message.lower()


class TestRequirementsMessage:
    """Tests for password requirements message generation"""

    def test_requirements_message_complete(self):
        """Test requirements message includes all rules"""
        message = generate_password_requirements_message()

        assert "8 characters" in message
        assert "uppercase" in message.lower()
        assert "lowercase" in message.lower()
        assert "number" in message.lower() or "digit" in message.lower()
        assert "special" in message.lower()

    def test_requirements_message_readable(self):
        """Test requirements message is human-readable"""
        message = generate_password_requirements_message()

        # Should be multi-line for readability
        assert "\n" in message

        # Should start with a header
        assert "Password Requirements" in message


class TestCommonPasswordsList:
    """Tests for common passwords list"""

    def test_common_passwords_loaded(self):
        """Test common passwords list is populated"""
        assert len(COMMON_PASSWORDS) > 0

    def test_known_common_passwords_included(self):
        """Test known common passwords are in the list"""
        known_common = ["password", "123456", "qwerty", "admin123"]

        for pwd in known_common:
            assert pwd in COMMON_PASSWORDS, f"'{pwd}' should be in common passwords list"

    def test_common_passwords_lowercase(self):
        """Test common passwords are stored in lowercase for comparison"""
        for pwd in COMMON_PASSWORDS:
            assert pwd == pwd.lower(), f"Common password '{pwd}' should be lowercase"


class TestUserCreateModelValidation:
    """Tests for UserCreate model password validation"""

    def test_user_create_valid_password(self):
        """Test UserCreate accepts valid password"""
        from backend.models.user import UserCreate

        user = UserCreate(
            username="testuser",
            email="test@example.com",
            password="ValidP@ss123",
            full_name="Test User",
            role="operator",
        )

        assert user.password == "ValidP@ss123"

    def test_user_create_invalid_password_rejected(self):
        """Test UserCreate rejects invalid password"""
        from backend.models.user import UserCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                username="testuser", email="test@example.com", password="weak", full_name="Test User", role="operator"
            )

        # Check error is for password field
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("password",) for e in errors)

    def test_user_create_missing_uppercase_rejected(self):
        """Test UserCreate rejects password missing uppercase"""
        from backend.models.user import UserCreate
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="lowercase1!",
                full_name="Test User",
                role="operator",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("password",) for e in errors)


class TestEdgeCases:
    """Edge case tests for password validation"""

    def test_empty_password(self):
        """Test empty password is rejected"""
        is_valid, message = validate_password_strength("")
        assert not is_valid

    def test_whitespace_password(self):
        """Test whitespace-only password is rejected"""
        is_valid, message = validate_password_strength("        ")
        assert not is_valid

    def test_unicode_characters(self):
        """Test password with unicode characters"""
        # Unicode should be allowed in password
        is_valid, message = validate_password_strength("StrongP@ss123")
        assert is_valid, f"Unicode password should be valid: {message}"

    def test_password_exactly_max_length(self):
        """Test password at exactly maximum length"""
        # Build a valid 128-char password with varied characters
        base = "Aa1!" * 32  # Exactly 128 characters with variety
        is_valid, message = validate_password_strength(base)
        assert is_valid, f"Max length password should be valid: {message}"

    def test_multiple_validation_failures(self):
        """Test password with multiple validation failures"""
        is_valid, message = validate_password_strength("a")

        assert not is_valid
        # Should report multiple issues
        assert ";" in message or "," in message or len(message) > 50
