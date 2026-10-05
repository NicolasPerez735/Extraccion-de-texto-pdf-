"""PDF extraction use case."""

from app.core.exceptions import UnsupportedFileTypeError
from app.services.pdf_text_extractor import PdfTextExtractor


class ExtractionService:
    """Validates an upload and delegates PDF parsing to an extractor."""

    def __init__(self, extractor: PdfTextExtractor) -> None:
        self._extractor = extractor

    async def extract(self, content: bytes, content_type: str | None) -> str:
        if content_type != "application/pdf":
            raise UnsupportedFileTypeError("El archivo debe ser un PDF válido.")

        return self._extractor.extract(content)
