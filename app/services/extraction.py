"""Caso de uso de extracción de texto de un PDF."""

import base64
import hashlib

from app.models.extraction import PdfExtraction
from app.services.text_extractor import TextExtractor


class ExtractionService:
    """Decodifica el PDF, delega la lectura en el extractor y calcula el checksum."""

    def __init__(self, extractor: TextExtractor) -> None:
        self._extractor = extractor

    def extraer(self, archivo_base64: str, nombre: str) -> PdfExtraction:
        contenido = base64.b64decode(archivo_base64)
        resultado = self._extractor.extract(contenido)
        return PdfExtraction(
            nombre=nombre,
            texto=resultado.texto,
            checksum=hashlib.sha256(contenido).hexdigest(),
            tamano_bytes=len(contenido),
            paginas=resultado.paginas,
        )
