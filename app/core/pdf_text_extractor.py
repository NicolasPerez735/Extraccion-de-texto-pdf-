"""Adaptador de extracción de texto con pypdf."""

from io import BytesIO

import pypdf

from app.core.exceptions import PdfCorruptedError
from app.models.extraction import TextoExtraido


class PdfTextExtractor:
    """Convierte los bytes de un PDF en texto plano y cuenta sus páginas."""

    def extract(self, content: bytes) -> TextoExtraido:
        # pypdf puede fallar al abrir, al recorrer las páginas o al extraer el
        # texto: todo eso es un PDF que no se puede procesar.
        try:
            reader = pypdf.PdfReader(BytesIO(content))
            textos = [page.extract_text() for page in reader.pages]
        except pypdf.errors.PyPdfError as error:
            raise PdfCorruptedError("El archivo PDF está corrupto.") from error

        texto = "\n".join(t for t in textos if t)
        return TextoExtraido(texto=texto.strip(), paginas=len(textos))
