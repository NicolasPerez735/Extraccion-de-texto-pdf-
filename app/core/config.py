from functools import lru_cache
from typing import Literal

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.consul_config import leer_config_de_consul


class ConexionConsul(BaseSettings):
    """Lo único que llega por el entorno cuando hay Consul: cómo conectarse."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    consul_enabled: bool = False
    consul_http_addr: str = "http://consul:8500"
    consul_http_token_file: str | None = None


class Settings(ConexionConsul):
    """Runtime configuration loaded from environment variables."""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Procesos que convierten PDF a Markdown en cada réplica (POST /extract).
    extract_workers: int = Field(default=1, ge=1)
    # Backpressure: requests que pueden esperar un worker y cuánto tiempo.
    extract_max_queue: int = Field(default=100, ge=0)
    extract_queue_timeout_seconds: float = Field(default=25, gt=0)
    consul_service_address: str | None = None
    consul_service_port: int = 8000


def cargar_settings(transport: httpx.BaseTransport | None = None) -> Settings:
    """Contrato 1.6.0: con CONSUL_ENABLED, la configuración sale del KV de Consul
    (config/extraccion/) y tiene prioridad sobre el entorno."""
    conexion = ConexionConsul()
    if not conexion.consul_enabled:
        return Settings()
    if not conexion.consul_http_token_file:
        raise ValueError("CONSUL_HTTP_TOKEN_FILE es obligatorio")
    valores = leer_config_de_consul(
        conexion.consul_http_addr,
        conexion.consul_http_token_file,
        "extraccion",
        transport,
    )
    return Settings(**valores)


@lru_cache
def get_settings() -> Settings:
    return cargar_settings()
