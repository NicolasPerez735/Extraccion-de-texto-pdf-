import asyncio

import pytest

from app.core.exceptions import PdfInvalidError
from app.models.extraction import DocumentoMarkdown
from app.services.conversion import ConversionService

PDF_CONTENT = b"%PDF-1.4\ncontenido\n%%EOF"


class StubConverter:
    def __init__(self) -> None:
        self.contenido: bytes | None = None

    async def convertir(self, contenido: bytes) -> DocumentoMarkdown:
        self.contenido = contenido
        return DocumentoMarkdown(content="## Página 1\n\nTexto", page_count=1)


def test_convertir_returns_the_converter_document() -> None:
    service = ConversionService(StubConverter())

    documento = asyncio.run(service.convertir(PDF_CONTENT))

    assert documento == DocumentoMarkdown(content="## Página 1\n\nTexto", page_count=1)


def test_convertir_passes_the_bytes_to_the_converter() -> None:
    converter = StubConverter()

    asyncio.run(ConversionService(converter).convertir(PDF_CONTENT))

    assert converter.contenido == PDF_CONTENT


@pytest.mark.parametrize("contenido", [b"", b"no soy un pdf"])
def test_convertir_rejects_content_that_is_not_a_pdf(contenido) -> None:
    converter = StubConverter()

    with pytest.raises(PdfInvalidError):
        asyncio.run(ConversionService(converter).convertir(contenido))

    assert converter.contenido is None
