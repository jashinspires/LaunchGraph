"""
Decisioner service configuration.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from launchgraph_core.config import settings as core_settings


class DecisionerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

    PORT: int = core_settings.DECISIONER_PORT
    HOST: str = "0.0.0.0"
    SERVICE_NAME: str = "decisioner"
    POLL_INTERVAL_SECONDS: float = core_settings.WORKER_POLL_INTERVAL_SECONDS
    BATCH_SIZE: int = core_settings.WORKER_BATCH_SIZE

    # Model & Consensus Settings
    MODEL_NAME: str = "claude-opus-5"
    K_SAMPLES: int = 3
    MAX_EVIDENCE_TOKENS: int = 12000
    ANTHROPIC_API_KEY: Optional[str] = None
    JUDGMENT_BACKEND: str = "deterministic"  # "deterministic" or "claude"


decisioner_settings = DecisionerSettings()

