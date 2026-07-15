"""
AMASCI Configuration Module
============================
Centralized configuration using Pydantic BaseSettings.
Supports Development, Testing, and Production environments.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = "AMASCI"
    app_version: str = "1.0.0"
    app_env: Literal["development", "testing", "production"] = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # --- Security ---
    secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # --- PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "amasci_user"
    postgres_password: str = "amasci_password"
    postgres_db: str = "amasci_db"
    database_url: str = "postgresql+asyncpg://amasci_user:amasci_password@localhost:5432/amasci_db"

    # --- Neo4j ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neo4j_password"
    neo4j_database: str = "neo4j"

    # --- File Storage ---
    upload_dir: str = "./data/uploads"
    model_dir: str = "./data/models"
    log_dir: str = "./data/logs"
    raw_data_dir: str = "./data/raw"
    max_upload_size_mb: int = 500
    auto_initialize: bool = True

    # --- ML Configuration ---
    ml_model_version: str = "latest"
    lightgbm_n_estimators: int = 500
    lightgbm_learning_rate: float = 0.05
    lightgbm_max_depth: int = 7

    # --- LLM/OpenAI Configuration ---
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model_name: str = "gpt-4o"

    # --- TPKE Configuration ---
    tpke_confidence_threshold: float = 0.6
    tpke_frequency_threshold: int = 3
    tpke_decay_rate: float = 0.1
    tpke_window_size_days: int = 90

    # --- Logging ---
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: str = "./data/logs/amasci.log"
    log_rotation: str = "daily"
    log_retention_days: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def sync_database_url(self) -> str:
        """Synchronous database URL for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "+psycopg2")

    @property
    def upload_path(self) -> Path:
        """Resolved upload directory path."""
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def model_path(self) -> Path:
        """Resolved model directory path."""
        path = Path(self.model_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def raw_data_path(self) -> Path:
        """Resolved raw data directory path."""
        path = Path(self.raw_data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def log_path(self) -> Path:
        """Resolved log directory path."""
        path = Path(self.log_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


class DevelopmentSettings(Settings):
    """Development-specific overrides."""
    debug: bool = True
    log_level: str = "DEBUG"


class TestingSettings(Settings):
    """Testing-specific overrides."""
    app_env: Literal["development", "testing", "production"] = "testing"
    debug: bool = True
    database_url: str = "postgresql+asyncpg://amasci_user:amasci_password@localhost:5432/amasci_test_db"


class ProductionSettings(Settings):
    """Production-specific overrides."""
    app_env: Literal["development", "testing", "production"] = "production"
    debug: bool = False
    log_level: str = "WARNING"
    workers: int = 8


@lru_cache()
def get_settings() -> Settings:
    """Factory function to get environment-appropriate settings."""
    import os
    env = os.getenv("APP_ENV", "development")
    settings_map = {
        "development": DevelopmentSettings,
        "testing": TestingSettings,
        "production": ProductionSettings,
    }
    settings_class = settings_map.get(env, DevelopmentSettings)
    return settings_class()
