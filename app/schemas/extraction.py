"""Contrato HTTP de extracción (microservicios-pdf v1.0.0)."""

from pydantic import BaseModel


class ExtractionRequest(BaseModel):
    archivo_base64: str
    nombre: str


class ExtractionResponse(BaseModel):
    nombre: str
    texto: str
    checksum: str
    tamano_bytes: int
    paginas: int
