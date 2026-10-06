"""PDF text extraction adapter."""

from io import BytesIO

import pypdf

from app.core.exceptions import InvalidPdfError
from app.models.extraction import TextoExtraido


class PdfTextExtractor:
    """Converts PDF bytes into plain text."""

    def extract(self, content: bytes) -> TextoExtraido:
        try:
            reader = pypdf.PdfReader(BytesIO(content))
        except (pypdf.errors.PdfReadError, pypdf.errors.EmptyFileError) as error:
            raise InvalidPdfError("El archivo PDF no es válido.") from error

        text = "\n".join(
            page_text for page in reader.pages if (page_text := page.extract_text())
        )
        return TextoExtraido(texto=text.strip(), paginas=len(reader.pages))
