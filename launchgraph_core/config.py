"""
Configuration and environment settings for LaunchGraph services.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide settings managed through environment variables.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    ENV: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database Configuration
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/launchgraph"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False

    # Security & Cryptography
    SECRET_KEY: str = "insecure-development-secret-key-change-in-production-min-32-chars"
    KMS_KEY_ID: Optional[str] = None
    DATA_RETENTION_DAYS: int = 30

    # Service Ports
    INGESTER_PORT: int = 8001
    NORMALIZER_PORT: int = 8002
    DECISIONER_PORT: int = 8003
    GENERATOR_PORT: int = 8004
    DASHBOARD_PORT: int = 8005
    A2A_PORT: int = 8006

    # Webhook Verification Defaults
    GITHUB_WEBHOOK_SECRET: Optional[str] = "test-github-secret"
    SLACK_SIGNING_SECRET: Optional[str] = "test-slack-secret"
    JIRA_WEBHOOK_SECRET: Optional[str] = "test-jira-secret"

    # Worker Settings
    WORKER_POLL_INTERVAL_SECONDS: float = 2.0
    WORKER_BATCH_SIZE: int = 25


settings = Settings()
