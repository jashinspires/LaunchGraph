"""
Normalizer service configuration.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from launchgraph_core.config import settings as core_settings


class NormalizerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

    PORT: int = core_settings.NORMALIZER_PORT
    HOST: str = "0.0.0.0"
    SERVICE_NAME: str = "normalizer"
    POLL_INTERVAL_SECONDS: float = core_settings.WORKER_POLL_INTERVAL_SECONDS
    BATCH_SIZE: int = core_settings.WORKER_BATCH_SIZE


normalizer_settings = NormalizerSettings()
