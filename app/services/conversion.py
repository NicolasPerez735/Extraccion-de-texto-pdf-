"""Caso de uso del TP de carga: PDF binario a Markdown."""

import logging

from app.models.extraction import DocumentoMarkdown
from app.services.firma_pdf import validar_firma_pdf
from app.services.lector_paginas import LectorPaginas

logger = logging.getLogger(__name__)


def _a_markdown(paginas: list[str]) -> str:
    """Un encabezado por página seguido de su texto."""
    secciones = [
        f"## Página {numero}\n\n{texto}" if texto else f"## Página {numero}"
        for numero, texto in enumerate(paginas, start=1)
    ]
    return "\n\n".join(secciones)


class ConversionService:
    """Valida que el contenido sea un PDF, lee sus páginas y arma el Markdown."""

    def __init__(self, lector: LectorPaginas) -> None:
        self._lector = lector

    async def convertir(self, contenido: bytes) -> DocumentoMarkdown:
        validar_firma_pdf(contenido)
        paginas = await self._lector.leer(contenido)
        documento = DocumentoMarkdown(
            content=_a_markdown(paginas), page_count=len(paginas)
        )
        # Sin el texto (contrato 1.2.0): solo cantidades.
        logger.info(
            "markdown generado paginas=%d tamano_bytes=%d caracteres=%d",
            documento.page_count,
            len(contenido),
            len(documento.content),
        )
        return documento
