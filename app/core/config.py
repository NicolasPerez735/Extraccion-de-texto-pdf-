from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Procesos que convierten PDF a Markdown en cada réplica (POST /extract).
    extract_workers: int = Field(default=1, ge=1)
    # Backpressure: requests que pueden esperar un worker y cuánto tiempo.
    extract_max_queue: int = Field(default=20, ge=0)
    extract_queue_timeout_seconds: float = Field(default=10, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
