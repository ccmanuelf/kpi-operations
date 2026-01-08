"""
Backend Configuration
Pydantic Settings for environment variables
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings from environment variables"""

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


# Global settings instance
settings = Settings()
