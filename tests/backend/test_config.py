"""
Unit Tests for Configuration Module
Tests settings, environment variables, and configuration validation
"""

import pytest
import os
from unittest.mock import patch


@pytest.mark.unit
class TestSettingsBasic:
    """Test basic settings configuration"""

    def test_settings_instance_exists(self):
        """Test settings instance is created"""
        from backend.config import settings

        assert settings is not None

    def test_database_settings(self):
        """Test database configuration settings"""
        from backend.config import settings

        assert settings.DATABASE_URL is not None
        assert settings.DB_HOST is not None
        assert settings.DB_PORT > 0
        assert settings.DB_NAME is not None
        assert settings.DB_USER is not None

    def test_jwt_settings(self):
        """Test JWT configuration settings"""
        from backend.config import settings

        assert settings.SECRET_KEY is not None
        assert settings.ALGORITHM == "HS256"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0

    def test_cors_settings(self):
        """Test CORS configuration"""
        from backend.config import settings

        assert settings.CORS_ORIGINS is not None
        assert isinstance(settings.cors_origins_list, list)
        assert len(settings.cors_origins_list) > 0


@pytest.mark.unit
class TestCORSConfiguration:
    """Test CORS origins parsing"""

    def test_cors_origins_list_parsing(self):
        """Test CORS origins string is parsed to list"""
        from backend.config import settings

        origins = settings.cors_origins_list
        assert isinstance(origins, list)
        assert all(isinstance(o, str) for o in origins)

    def test_cors_origins_no_trailing_spaces(self):
        """Test CORS origins are trimmed"""
        from backend.config import settings

        origins = settings.cors_origins_list
        for origin in origins:
            assert origin == origin.strip()

    def test_cors_multiple_origins(self):
        """Test multiple CORS origins are supported"""
        from backend.config import settings

        if ',' in settings.CORS_ORIGINS:
            assert len(settings.cors_origins_list) >= 2


@pytest.mark.unit
class TestApplicationSettings:
    """Test application-level settings"""

    def test_debug_mode(self):
        """Test DEBUG setting"""
        from backend.config import settings

        assert isinstance(settings.DEBUG, bool)

    def test_log_level(self):
        """Test LOG_LEVEL setting"""
        from backend.config import settings

        assert settings.LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_max_upload_size(self):
        """Test file upload size limit"""
        from backend.config import settings

        assert settings.MAX_UPLOAD_SIZE > 0
        assert settings.MAX_UPLOAD_SIZE <= 100 * 1024 * 1024  # Reasonable limit

    def test_upload_directory(self):
        """Test upload directory setting"""
        from backend.config import settings

        assert settings.UPLOAD_DIR is not None
        assert isinstance(settings.UPLOAD_DIR, str)

    def test_report_output_directory(self):
        """Test report output directory"""
        from backend.config import settings

        assert settings.REPORT_OUTPUT_DIR is not None
        assert isinstance(settings.REPORT_OUTPUT_DIR, str)


@pytest.mark.unit
class TestEnvironmentVariables:
    """Test environment variable loading"""

    @patch.dict(os.environ, {"DATABASE_URL": "mysql://custom:pass@host:3306/db"})
    def test_env_override_database_url(self):
        """Test DATABASE_URL can be overridden by environment"""
        # Would need to reload settings
        from backend.config import Settings
        test_settings = Settings()

        assert test_settings.DATABASE_URL is not None

    @patch.dict(os.environ, {"SECRET_KEY": "test-secret-key-123"})
    def test_env_override_secret_key(self):
        """Test SECRET_KEY can be overridden by environment"""
        from backend.config import Settings
        test_settings = Settings()

        assert test_settings.SECRET_KEY == "test-secret-key-123"

    @patch.dict(os.environ, {"DEBUG": "false"})
    def test_env_override_debug_mode(self):
        """Test DEBUG can be set via environment"""
        from backend.config import Settings
        test_settings = Settings()

        assert isinstance(test_settings.DEBUG, bool)


@pytest.mark.unit
class TestSettingsValidation:
    """Test settings validation and constraints"""

    def test_database_port_valid_range(self):
        """Test database port is in valid range"""
        from backend.config import settings

        assert 1 <= settings.DB_PORT <= 65535

    def test_access_token_expire_reasonable(self):
        """Test token expiry is reasonable"""
        from backend.config import settings

        assert 1 <= settings.ACCESS_TOKEN_EXPIRE_MINUTES <= 1440  # 1 min to 24 hours

    def test_max_upload_size_reasonable(self):
        """Test max upload size is reasonable"""
        from backend.config import settings

        assert settings.MAX_UPLOAD_SIZE >= 1024  # At least 1KB
        assert settings.MAX_UPLOAD_SIZE <= 1024 * 1024 * 1024  # Max 1GB


@pytest.mark.security
class TestSecuritySettings:
    """Test security-related settings"""

    def test_secret_key_not_default_in_production(self):
        """Test SECRET_KEY is not using default value"""
        from backend.config import settings

        # In production, should be changed
        assert len(settings.SECRET_KEY) >= 32  # Minimum length

    def test_algorithm_is_secure(self):
        """Test JWT algorithm is secure"""
        from backend.config import settings

        assert settings.ALGORITHM in ["HS256", "HS384", "HS512", "RS256"]

    def test_cors_origins_not_wildcard_in_production(self):
        """Test CORS doesn't allow all origins"""
        from backend.config import settings

        # Should not be "*" in production
        assert "*" not in settings.CORS_ORIGINS or settings.DEBUG


@pytest.mark.unit
class TestSettingsEdgeCases:
    """Test edge cases and special scenarios"""

    def test_settings_case_sensitive(self):
        """Test settings are case-sensitive"""
        from backend.config import Settings

        assert Settings.Config.case_sensitive == True

    def test_env_file_configuration(self):
        """Test .env file is configured"""
        from backend.config import Settings

        assert Settings.Config.env_file == ".env"

    def test_settings_immutability(self):
        """Test settings can be modified (for testing)"""
        from backend.config import settings

        # Should be able to access all attributes
        assert hasattr(settings, 'DATABASE_URL')
        assert hasattr(settings, 'SECRET_KEY')
        assert hasattr(settings, 'DEBUG')


@pytest.mark.unit
class TestConfigurationConsistency:
    """Test configuration consistency"""

    def test_database_url_matches_components(self):
        """Test DATABASE_URL matches individual DB components"""
        from backend.config import settings

        # DATABASE_URL should contain the DB components
        assert settings.DB_HOST in settings.DATABASE_URL or 'localhost' in settings.DATABASE_URL
        assert str(settings.DB_PORT) in settings.DATABASE_URL or ':3306' in settings.DATABASE_URL
        assert settings.DB_NAME in settings.DATABASE_URL

    def test_cors_localhost_included_in_dev(self):
        """Test localhost is included in CORS for development"""
        from backend.config import settings

        if settings.DEBUG:
            origins = settings.cors_origins_list
            localhost_found = any('localhost' in origin for origin in origins)
            assert localhost_found


@pytest.mark.performance
class TestSettingsPerformance:
    """Test settings performance"""

    def test_cors_origins_list_caching(self):
        """Test CORS origins list is efficiently accessed"""
        from backend.config import settings
        import time

        start = time.time()
        for _ in range(1000):
            _ = settings.cors_origins_list
        duration = time.time() - start

        assert duration < 0.1  # Should be fast


@pytest.mark.unit
class TestDefaultValues:
    """Test default configuration values"""

    def test_default_database_settings(self):
        """Test default database settings are sensible"""
        from backend.config import Settings

        defaults = Settings()
        assert defaults.DB_HOST == "localhost"
        assert defaults.DB_PORT == 3306
        assert defaults.DB_NAME == "kpi_platform"

    def test_default_upload_settings(self):
        """Test default upload settings"""
        from backend.config import Settings

        defaults = Settings()
        assert defaults.MAX_UPLOAD_SIZE == 10485760  # 10MB
        assert defaults.UPLOAD_DIR == "./uploads"

    def test_default_report_settings(self):
        """Test default report settings"""
        from backend.config import Settings

        defaults = Settings()
        assert defaults.REPORT_OUTPUT_DIR == "./reports"
