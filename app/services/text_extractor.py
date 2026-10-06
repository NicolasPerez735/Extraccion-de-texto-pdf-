from typing import Protocol

from app.models.extraction import TextoExtraido


class TextExtractor(Protocol):
    def extract(self, content: bytes) -> TextoExtraido:
        """Extrae el texto y cuenta las páginas del contenido binario."""
