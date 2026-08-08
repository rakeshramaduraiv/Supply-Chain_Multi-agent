"""
AMASCI Configuration Module
============================
Centralised Pydantic settings. Single source of truth for every parameter.
All five TPKE values are frozen here and propagated to every .env.* file.
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
    cors_origins: str = (
        "http://localhost:3000,http://localhost:3001,http://localhost:3002,"
        "http://localhost:5173,http://localhost:5174,"
        "http://127.0.0.1:3000,http://127.0.0.1:3001"
    )

    # --- PostgreSQL ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "amasci_user"
    postgres_password: str = "amasci_password"
    postgres_db: str = "amasci_db"
    database_url: str = (
        "postgresql+asyncpg://amasci_user:amasci_password@localhost:5432/amasci_db"
    )

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
    processed_dir: str = "./data/uploads"   # processed_master.parquet lives here
    max_upload_size_mb: int = 500
    auto_initialize: bool = True

    # --- ML Configuration ---
    ml_model_version: str = "latest"
    lightgbm_n_estimators: int = 500
    lightgbm_learning_rate: float = 0.05
    lightgbm_max_depth: int = 7

    # --- LLM/OpenAI ---
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model_name: str = "gpt-4o"

    # --- TPKE — FROZEN (spec §1.3, CLAUDE.md §6) ---
    # These five values must be identical in config.py, all .env.* files, and CLAUDE.md.
    # A mismatch is a build failure.
    tpke_confidence_threshold: float = 0.70   # θ_add: min P(B|A) to create edge
    tpke_top_k: int = 3                        # K:     top-K patterns per source node
    tpke_decay_rate: float = 0.05              # δ:     edge weight decay per cycle
    tpke_removal_threshold: float = 0.10       # θ_rem: delete edge below this weight
    tpke_window_size_days: int = 30            # W:     sliding detection window (days)
    # Internal use only — not part of the frozen spec surface
    tpke_frequency_threshold: int = 3
    tpke_lag_days: int = 7

    # --- Logging ---
    log_level: str = "INFO"
    log_format: str = "json"
    log_file: str = "./data/logs/amasci.log"
    log_rotation: str = "daily"
    log_retention_days: int = 30

    # ------------------------------------------------------------------ #
    # Derived paths                                                        #
    # ------------------------------------------------------------------ #

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg2")

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def model_path(self) -> Path:
        return Path(self.model_dir)

    @property
    def model_registry_path(self) -> Path:
        """Path to registry.json inside the model directory."""
        return Path(self.model_dir) / "registry.json"

    @property
    def raw_data_path(self) -> Path:
        return Path(self.raw_data_dir)

    @property
    def processed_master_path(self) -> Path:
        return Path(self.processed_dir) / "processed_master.parquet"

    @property
    def log_path(self) -> Path:
        return Path(self.log_dir)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    # ------------------------------------------------------------------ #
    # Directory bootstrap                                                  #
    # ------------------------------------------------------------------ #

    def ensure_dirs(self) -> None:
        """Create all configured directories idempotently. Safe to call many times."""
        for d in (
            self.upload_path,
            self.model_path,
            self.raw_data_path,
            self.log_path,
            Path(self.processed_dir),
        ):
            d.mkdir(parents=True, exist_ok=True)


class DevelopmentSettings(Settings):
    debug: bool = True
    log_level: str = "DEBUG"


class TestingSettings(Settings):
    app_env: Literal["development", "testing", "production"] = "testing"
    debug: bool = True
    database_url: str = (
        "postgresql+asyncpg://amasci_user:amasci_password@localhost:5432/amasci_test_db"
    )


class ProductionSettings(Settings):
    app_env: Literal["development", "testing", "production"] = "production"
    debug: bool = False
    log_level: str = "WARNING"
    workers: int = 8


@lru_cache()
def get_settings() -> Settings:
    import os
    env = os.getenv("APP_ENV", "development")
    cls = {"development": DevelopmentSettings,
           "testing": TestingSettings,
           "production": ProductionSettings}.get(env, DevelopmentSettings)
    return cls()
