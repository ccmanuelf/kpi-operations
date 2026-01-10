"""
Password Policy Enforcement (SEC-002)
Strong password validation with configurable requirements

Requirements:
- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 digit
- At least 1 special character
"""
import re
from typing import Tuple, List, Optional
from dataclasses import dataclass


@dataclass
class PasswordPolicyConfig:
    """Password policy configuration"""

    # Length requirements
    min_length: int = 8
    max_length: int = 128

    # Character requirements
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digit: bool = True
    require_special: bool = True

    # Special characters allowed
    special_characters: str = "!@#$%^&*()_+-=[]{}|;':\",./<>?"

    # Password history (prevent reuse)
    prevent_reuse_count: int = 5

    # Common password check
    check_common_passwords: bool = True


# Default configuration
DEFAULT_POLICY = PasswordPolicyConfig()

# List of common weak passwords to reject
COMMON_PASSWORDS = {
    "password", "password123", "123456", "12345678", "qwerty",
    "abc123", "monkey", "1234567", "letmein", "trustno1",
    "dragon", "baseball", "iloveyou", "master", "sunshine",
    "ashley", "bailey", "shadow", "123123", "654321",
    "superman", "qazwsx", "michael", "football", "password1",
    "password12", "passw0rd", "admin123", "root123", "welcome1",
    "welcome123", "changeme", "changeme123", "test123", "guest123"
}


def validate_password_strength(
    password: str,
    config: Optional[PasswordPolicyConfig] = None
) -> Tuple[bool, str]:
    """
    Validate password against security policy

    Args:
        password: Password string to validate
        config: Optional custom policy configuration

    Returns:
        Tuple of (is_valid: bool, message: str)
        - is_valid: True if password meets all requirements
        - message: Success message or detailed error description

    Examples:
        >>> validate_password_strength("weak")
        (False, "Password must be at least 8 characters long")

        >>> validate_password_strength("StrongP@ss123")
        (True, "Password meets all security requirements")
    """
    if config is None:
        config = DEFAULT_POLICY

    errors: List[str] = []

    # Check minimum length
    if len(password) < config.min_length:
        errors.append(f"Password must be at least {config.min_length} characters long")

    # Check maximum length
    if len(password) > config.max_length:
        errors.append(f"Password must not exceed {config.max_length} characters")

    # Check for uppercase letter
    if config.require_uppercase and not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least 1 uppercase letter (A-Z)")

    # Check for lowercase letter
    if config.require_lowercase and not re.search(r'[a-z]', password):
        errors.append("Password must contain at least 1 lowercase letter (a-z)")

    # Check for digit
    if config.require_digit and not re.search(r'[0-9]', password):
        errors.append("Password must contain at least 1 digit (0-9)")

    # Check for special character
    if config.require_special:
        special_pattern = f'[{re.escape(config.special_characters)}]'
        if not re.search(special_pattern, password):
            errors.append(
                f"Password must contain at least 1 special character ({config.special_characters[:10]}...)"
            )

    # Check against common passwords
    if config.check_common_passwords and password.lower() in COMMON_PASSWORDS:
        errors.append("Password is too common and easily guessable")

    # Check for repeated characters (e.g., "aaaaaa")
    if re.search(r'(.)\1{3,}', password):
        errors.append("Password cannot contain more than 3 consecutive identical characters")

    # Check for sequential characters (e.g., "123456" or "abcdef")
    if _has_sequential_chars(password, 4):
        errors.append("Password cannot contain sequential characters (e.g., 1234, abcd)")

    # Return result
    if errors:
        return False, "; ".join(errors)

    return True, "Password meets all security requirements"


def _has_sequential_chars(password: str, min_sequential: int = 4) -> bool:
    """
    Check if password contains sequential characters

    Args:
        password: Password to check
        min_sequential: Minimum length of sequence to detect

    Returns:
        True if sequential characters found
    """
    password_lower = password.lower()

    # Check for numeric sequences
    for i in range(len(password_lower) - min_sequential + 1):
        if password_lower[i:i + min_sequential].isdigit():
            substring = password_lower[i:i + min_sequential]
            is_ascending = all(
                int(substring[j]) + 1 == int(substring[j + 1])
                for j in range(len(substring) - 1)
            )
            is_descending = all(
                int(substring[j]) - 1 == int(substring[j + 1])
                for j in range(len(substring) - 1)
            )
            if is_ascending or is_descending:
                return True

    # Check for alphabetic sequences
    for i in range(len(password_lower) - min_sequential + 1):
        substring = password_lower[i:i + min_sequential]
        if substring.isalpha():
            is_ascending = all(
                ord(substring[j]) + 1 == ord(substring[j + 1])
                for j in range(len(substring) - 1)
            )
            is_descending = all(
                ord(substring[j]) - 1 == ord(substring[j + 1])
                for j in range(len(substring) - 1)
            )
            if is_ascending or is_descending:
                return True

    return False


def get_password_strength_score(password: str) -> Tuple[int, str]:
    """
    Calculate password strength score (0-100)

    Args:
        password: Password to evaluate

    Returns:
        Tuple of (score: int, strength_label: str)
        - score: 0-100 strength score
        - strength_label: "Weak", "Fair", "Good", "Strong", "Very Strong"

    Examples:
        >>> get_password_strength_score("weak")
        (15, "Weak")

        >>> get_password_strength_score("MyStr0ng@P@ssw0rd!")
        (95, "Very Strong")
    """
    score = 0

    # Length scoring (up to 25 points)
    length = len(password)
    if length >= 8:
        score += 10
    if length >= 12:
        score += 10
    if length >= 16:
        score += 5

    # Character variety scoring (up to 40 points)
    if re.search(r'[a-z]', password):
        score += 10
    if re.search(r'[A-Z]', password):
        score += 10
    if re.search(r'[0-9]', password):
        score += 10
    if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;\':",./<>?]', password):
        score += 10

    # Complexity scoring (up to 35 points)
    # Mixed case
    if re.search(r'[a-z]', password) and re.search(r'[A-Z]', password):
        score += 10

    # Numbers and letters
    if re.search(r'[0-9]', password) and re.search(r'[a-zA-Z]', password):
        score += 10

    # Special characters with alphanumeric
    if re.search(r'[!@#$%^&*()_+\-=\[\]{}|;\':",./<>?]', password):
        if re.search(r'[a-zA-Z0-9]', password):
            score += 10

    # Unique characters bonus
    unique_chars = len(set(password))
    if unique_chars >= length * 0.7:  # 70% unique characters
        score += 5

    # Penalty for common patterns
    if password.lower() in COMMON_PASSWORDS:
        score = max(0, score - 50)

    # Determine strength label
    if score < 30:
        label = "Weak"
    elif score < 50:
        label = "Fair"
    elif score < 70:
        label = "Good"
    elif score < 90:
        label = "Strong"
    else:
        label = "Very Strong"

    return min(100, score), label


def generate_password_requirements_message() -> str:
    """
    Generate human-readable password requirements message

    Returns:
        Formatted string with all password requirements
    """
    return """Password Requirements:
- At least 8 characters long
- At least 1 uppercase letter (A-Z)
- At least 1 lowercase letter (a-z)
- At least 1 number (0-9)
- At least 1 special character (!@#$%^&*...)
- Cannot be a commonly used password
- Cannot contain more than 3 identical characters in a row
- Cannot contain sequential characters (1234, abcd)"""


# FastAPI Pydantic validator for use with models
def password_validator(password: str) -> str:
    """
    Pydantic validator for password field

    Args:
        password: Password to validate

    Returns:
        Valid password string

    Raises:
        ValueError: If password doesn't meet requirements

    Usage in Pydantic model:
        from pydantic import field_validator
        from auth.password_policy import password_validator

        class UserCreate(BaseModel):
            password: str

            @field_validator('password')
            @classmethod
            def validate_password(cls, v):
                return password_validator(v)
    """
    is_valid, message = validate_password_strength(password)
    if not is_valid:
        raise ValueError(message)
    return password


# Export all public functions
__all__ = [
    "PasswordPolicyConfig",
    "DEFAULT_POLICY",
    "COMMON_PASSWORDS",
    "validate_password_strength",
    "get_password_strength_score",
    "generate_password_requirements_message",
    "password_validator"
]
