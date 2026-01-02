"""
Backend Configuration
Pydantic Settings for environment variables
"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """Application settings from environment variables"""

    # Database - Using SQLite for temporary deployment (user requested)
    DATABASE_URL: str = "sqlite:///./database/kpi_platform.db"
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

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
