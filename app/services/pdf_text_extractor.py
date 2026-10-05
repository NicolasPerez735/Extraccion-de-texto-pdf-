"""PDF text extraction adapter."""

from io import BytesIO

import pypdf

from app.core.exceptions import InvalidPdfError


class PdfTextExtractor:
    """Converts PDF bytes into plain text."""

    def extract(self, content: bytes) -> str:
        try:
            reader = pypdf.PdfReader(BytesIO(content))
        except (pypdf.errors.PdfReadError, pypdf.errors.EmptyFileError) as error:
            raise InvalidPdfError("El archivo PDF no es válido.") from error

        text = "\n".join(
            page_text for page in reader.pages if (page_text := page.extract_text())
        )
        return text.strip()
