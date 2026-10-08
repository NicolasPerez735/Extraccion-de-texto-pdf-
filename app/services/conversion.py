"""Caso de uso del TP de carga: PDF binario a Markdown."""

import logging

from app.core.exceptions import PdfInvalidError
from app.models.extraction import DocumentoMarkdown
from app.services.markdown_converter import MarkdownConverter

logger = logging.getLogger(__name__)


class ConversionService:
    """Valida que el contenido sea un PDF y delega la conversión en el conversor."""

    def __init__(self, converter: MarkdownConverter) -> None:
        self._converter = converter

    async def convertir(self, contenido: bytes) -> DocumentoMarkdown:
        if not contenido.startswith(b"%PDF"):
            raise PdfInvalidError("El archivo no es un PDF válido.")
        documento = await self._converter.convertir(contenido)
        # Sin el texto (contrato 1.2.0): solo cantidades.
        logger.info(
            "markdown generado paginas=%d tamano_bytes=%d caracteres=%d",
            documento.page_count,
            len(contenido),
            len(documento.content),
        )
        return documento
