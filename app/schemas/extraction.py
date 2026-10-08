"""Contrato HTTP de extracción (microservicios-pdf v1.0.0)."""

from pydantic import BaseModel, Field


class ExtractionRequest(BaseModel):
    archivo_base64: str
    nombre: str = Field(..., min_length=1, max_length=255)


class ExtractionResponse(BaseModel):
    nombre: str
    texto: str
    checksum: str
    tamano_bytes: int
    paginas: int


class MarkdownResponse(BaseModel):
    """Respuesta de POST /extract (TP de carga)."""

    content: str
    page_count: int
