"""PDF extraction use case."""

from app.core.config import get_settings
from app.core.exceptions import FileTooLargeError, UnsupportedFileTypeError
from app.services.text_extractor import TextExtractor


class ExtractionService:
    """Validates an upload and delegates PDF parsing to an extractor."""

    def __init__(self, extractor: TextExtractor) -> None:
        self._extractor = extractor

    async def extract(self, content: bytes, content_type: str | None) -> str:
        if content_type != "application/pdf":
            raise UnsupportedFileTypeError("El archivo debe ser un PDF válido.")

        settings = get_settings()
        maximum_size = settings.max_pdf_size_mb * 1024 * 1024
        if len(content) > maximum_size:
            raise FileTooLargeError(
                f"El archivo excede el tamaño máximo de "
                f"{settings.max_pdf_size_mb}MB."
            )

        return self._extractor.extract(content)
