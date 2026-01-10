"""
Backend Configuration
Pydantic Settings for environment variables

Enhanced with:
- DEP-002: Configuration validation for production environments
- Security checks for sensitive settings
- Environment-aware validation rules
"""
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List, Optional
from dataclasses import dataclass, field
import os
import sys
import logging
import secrets

logger = logging.getLogger(__name__)

# Default insecure values that must be changed in production
DEFAULT_INSECURE_VALUES = [
    "your-super-secret-key-change-in-production",
    "change-me-in-production",
    "CHANGE_ME_IN_PRODUCTION",
    "secret",
    "password",
    "changeme",
    "default"
]


@dataclass
class ConfigValidationResult:
    """Result of configuration validation"""
    environment: str
    is_valid: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    @property
    def has_critical_errors(self) -> bool:
        return len(self.errors) > 0


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # Environment detection
    ENVIRONMENT: str = Field(default="development", description="Runtime environment")

    # Database - Using SQLite for temporary deployment (user requested)
    DATABASE_URL: str = "sqlite:///../database/kpi_platform.db"
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "kpi_platform"
    DB_USER: str = "kpi_user"
    DB_PASSWORD: str = "password"

    # JWT
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins string to list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # Application
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # File Upload
    MAX_UPLOAD_SIZE: int = 10485760  # 10MB
    UPLOAD_DIR: str = "./uploads"

    # Reports
    REPORT_OUTPUT_DIR: str = "./reports"

    # Database Connection Pool Configuration
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600

    # Email Configuration
    SENDGRID_API_KEY: str = ""  # Set via environment variable
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""  # Set via environment variable
    SMTP_PASSWORD: str = ""  # Set via environment variable
    REPORT_FROM_EMAIL: str = "reports@kpi-platform.com"
    REPORT_EMAIL_ENABLED: bool = True
    REPORT_EMAIL_TIME: str = "06:00"  # Daily report time (HH:MM format)

    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENVIRONMENT.lower() in ("production", "prod")

    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.ENVIRONMENT.lower() in ("development", "dev", "local")


def validate_production_config(raise_on_critical: bool = False) -> ConfigValidationResult:
    """
    Validate critical configuration at startup (DEP-002)

    Checks for security issues and misconfigurations that could
    cause problems in production environments.

    Args:
        raise_on_critical: If True, raises ValueError on critical errors

    Returns:
        ConfigValidationResult with validation status

    Raises:
        ValueError: If raise_on_critical is True and critical errors found
    """
    result = ConfigValidationResult(
        environment=settings.ENVIRONMENT,
        is_valid=True
    )

    is_production = settings.is_production

    # Check SECRET_KEY security
    if settings.SECRET_KEY in DEFAULT_INSECURE_VALUES:
        if is_production:
            result.errors.append(
                "CRITICAL: SECRET_KEY must be changed in production! "
                "Generate a secure key with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
            result.is_valid = False
        else:
            result.warnings.append(
                "WARNING: Using default SECRET_KEY. Change before deploying to production."
            )

    # Check SECRET_KEY length (minimum 32 characters recommended)
    if len(settings.SECRET_KEY) < 32:
        if is_production:
            result.errors.append(
                "CRITICAL: SECRET_KEY should be at least 32 characters for security. "
                "Current length: {} characters".format(len(settings.SECRET_KEY))
            )
            result.is_valid = False
        else:
            result.warnings.append(
                f"WARNING: SECRET_KEY is only {len(settings.SECRET_KEY)} characters. "
                "Recommended minimum is 32 characters."
            )

    # Check DEBUG mode in production
    if is_production and settings.DEBUG:
        result.errors.append(
            "CRITICAL: DEBUG mode is enabled in production! "
            "Set DEBUG=False for security."
        )
        result.is_valid = False

    # Check database password security
    if settings.DB_PASSWORD in DEFAULT_INSECURE_VALUES:
        if is_production:
            result.errors.append(
                "CRITICAL: Default database password detected in production!"
            )
            result.is_valid = False
        else:
            result.warnings.append(
                "WARNING: Using default database password. Change before production."
            )

    # Check CORS origins for production
    if is_production:
        localhost_origins = [
            o for o in settings.cors_origins_list
            if "localhost" in o or "127.0.0.1" in o
        ]
        if localhost_origins:
            result.warnings.append(
                f"WARNING: Localhost CORS origins configured in production: {localhost_origins}. "
                "Consider removing for security."
            )

        # Check for wildcard CORS
        if "*" in settings.CORS_ORIGINS:
            result.errors.append(
                "CRITICAL: Wildcard (*) CORS origin in production is a security risk!"
            )
            result.is_valid = False

    # Check email configuration if enabled
    if settings.REPORT_EMAIL_ENABLED:
        if not settings.SENDGRID_API_KEY and not settings.SMTP_USER:
            result.warnings.append(
                "WARNING: Email reporting is enabled but no email credentials configured. "
                "Set SENDGRID_API_KEY or SMTP_USER/SMTP_PASSWORD."
            )

    # Check database URL security (no passwords in URLs in production)
    if is_production and "@" in settings.DATABASE_URL:
        # Check for plain text password in URL
        try:
            # Extract password section if present
            url_parts = settings.DATABASE_URL.split("@")[0]
            if ":" in url_parts and "//" in url_parts:
                password_section = url_parts.split(":")[-1]
                if password_section in DEFAULT_INSECURE_VALUES:
                    result.errors.append(
                        "CRITICAL: Default database password in DATABASE_URL!"
                    )
                    result.is_valid = False
        except Exception:
            pass  # URL parsing failed, skip this check

    # Check upload directory exists and is writable
    if settings.UPLOAD_DIR:
        upload_path = os.path.abspath(settings.UPLOAD_DIR)
        if not os.path.exists(upload_path):
            result.warnings.append(
                f"WARNING: Upload directory does not exist: {upload_path}"
            )
        elif not os.access(upload_path, os.W_OK):
            result.warnings.append(
                f"WARNING: Upload directory is not writable: {upload_path}"
            )

    # Check report output directory
    if settings.REPORT_OUTPUT_DIR:
        report_path = os.path.abspath(settings.REPORT_OUTPUT_DIR)
        if not os.path.exists(report_path):
            result.warnings.append(
                f"WARNING: Report output directory does not exist: {report_path}"
            )
        elif not os.access(report_path, os.W_OK):
            result.warnings.append(
                f"WARNING: Report output directory is not writable: {report_path}"
            )

    # Log validation results
    if result.errors:
        for error in result.errors:
            logger.error(f"[CONFIG] {error}")
    if result.warnings:
        for warning in result.warnings:
            logger.warning(f"[CONFIG] {warning}")

    # Optionally raise on critical errors
    if raise_on_critical and result.has_critical_errors:
        raise ValueError(
            f"Critical configuration errors detected - cannot start in {settings.ENVIRONMENT} mode. "
            f"Errors: {'; '.join(result.errors)}"
        )

    return result


def generate_secure_secret_key(length: int = 64) -> str:
    """
    Generate a cryptographically secure secret key

    Args:
        length: Length of the URL-safe base64 string

    Returns:
        Secure random string suitable for SECRET_KEY
    """
    return secrets.token_urlsafe(length)


# Global settings instance
settings = Settings()

# Validate configuration on module load (non-blocking)
# In production, use validate_production_config(raise_on_critical=True) at app startup
_startup_validation = validate_production_config(raise_on_critical=False)
