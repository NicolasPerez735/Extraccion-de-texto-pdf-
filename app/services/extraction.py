"""Caso de uso de extracción de texto de un PDF."""

import base64
import binascii
import hashlib
import logging

from app.core.exceptions import PdfInvalidError
from app.models.extraction import PdfExtraction
from app.services.firma_pdf import validar_firma_pdf
from app.services.lector_paginas import LectorPaginas

logger = logging.getLogger(__name__)


def _decodificar_pdf(archivo_base64: str) -> bytes:
    try:
        contenido = base64.b64decode("".join(archivo_base64.split()), validate=True)
    except (ValueError, binascii.Error) as error:
        raise PdfInvalidError("El archivo no es un PDF válido.") from error
    validar_firma_pdf(contenido)
    return contenido


class ExtractionService:
    """Decodifica el PDF, delega la lectura de las páginas y calcula el checksum."""

    def __init__(self, lector: LectorPaginas) -> None:
        self._lector = lector

    async def extraer(self, archivo_base64: str, nombre: str) -> PdfExtraction:
        contenido = _decodificar_pdf(archivo_base64)
        paginas = await self._lector.leer(contenido)
        extraccion = PdfExtraction(
            nombre=nombre,
            texto="\n".join(texto for texto in paginas if texto),
            checksum=hashlib.sha256(contenido).hexdigest(),
            tamano_bytes=len(contenido),
            paginas=len(paginas),
        )
        # Sin nombre ni texto (contrato 1.2.0): el documento se identifica por checksum.
        logger.info(
            "texto extraido paginas=%d tamano_bytes=%d caracteres=%d checksum=%s",
            extraccion.paginas,
            extraccion.tamano_bytes,
            len(extraccion.texto),
            extraccion.checksum,
        )
        return extraccion
