import pytest

from app.core.exceptions import FileTooLargeError, UnsupportedFileTypeError
from app.services.extraction import ExtractionService


class StubExtractor:
    def __init__(self, text: str = "Texto extraído") -> None:
        self.content: bytes | None = None
        self._text = text

    def extract(self, content: bytes) -> str:
        self.content = content
        return self._text


@pytest.mark.anyio
async def test_service_delegates_pdf_content_to_extractor() -> None:
    extractor = StubExtractor()
    service = ExtractionService(extractor)

    result = await service.extract(b"pdf-content", "application/pdf")

    assert result == "Texto extraído"
    assert extractor.content == b"pdf-content"


@pytest.mark.anyio
async def test_service_rejects_unsupported_content_type() -> None:
    service = ExtractionService(StubExtractor())

    with pytest.raises(UnsupportedFileTypeError):
        await service.extract(b"plain-text", "text/plain")


@pytest.mark.anyio
async def test_service_rejects_content_over_maximum_size() -> None:
    service = ExtractionService(StubExtractor())

    with pytest.raises(FileTooLargeError, match="tamaño máximo"):
        await service.extract(b"x" * (5 * 1024 * 1024 + 1), "application/pdf")
