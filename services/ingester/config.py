"""
Ingestion service configuration.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from launchgraph_core.config import settings as core_settings


class IngesterSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

    PORT: int = core_settings.INGESTER_PORT
    HOST: str = "0.0.0.0"
    SERVICE_NAME: str = "ingester"


ingester_settings = IngesterSettings()
