"""Entidades del dominio de extracción (Python puro)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TextoExtraido:
    texto: str
    paginas: int


@dataclass(frozen=True)
class PdfExtraction:
    nombre: str
    texto: str
    checksum: str
    tamano_bytes: int
    paginas: int
