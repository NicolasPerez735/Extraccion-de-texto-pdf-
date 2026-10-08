from typing import Protocol

from app.models.extraction import DocumentoMarkdown


class MarkdownConverter(Protocol):
    async def convertir(self, contenido: bytes) -> DocumentoMarkdown:
        """Convierte el PDF en Markdown y cuenta sus páginas."""
