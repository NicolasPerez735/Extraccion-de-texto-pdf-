"""Caso de uso de extracción de texto de un PDF."""

import base64
import binascii
import hashlib

from app.core.exceptions import PdfInvalidError
from app.models.extraction import PdfExtraction
from app.services.text_extractor import TextExtractor


def _decodificar_pdf(archivo_base64: str) -> bytes:
    try:
        contenido = base64.b64decode("".join(archivo_base64.split()), validate=True)
    except (ValueError, binascii.Error) as error:
        raise PdfInvalidError("El archivo no es un PDF válido.") from error
    if not contenido.startswith(b"%PDF"):
        raise PdfInvalidError("El archivo no es un PDF válido.")
    return contenido


class ExtractionService:
    """Decodifica el PDF, delega la lectura en el extractor y calcula el checksum."""

    def __init__(self, extractor: TextExtractor) -> None:
        self._extractor = extractor

    def extraer(self, archivo_base64: str, nombre: str) -> PdfExtraction:
        contenido = _decodificar_pdf(archivo_base64)
        resultado = self._extractor.extract(contenido)
        return PdfExtraction(
            nombre=nombre,
            texto=resultado.texto,
            checksum=hashlib.sha256(contenido).hexdigest(),
            tamano_bytes=len(contenido),
            paginas=resultado.paginas,
        )
