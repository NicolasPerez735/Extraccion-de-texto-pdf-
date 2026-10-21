import asyncio

import pytest

from app.core.exceptions import PdfInvalidError
from app.models.extraction import DocumentoMarkdown
from app.services.conversion import ConversionService

PDF_CONTENT = b"%PDF-1.4\ncontenido\n%%EOF"


class StubLector:
    def __init__(self, paginas: list[str] | None = None) -> None:
        self.contenido: bytes | None = None
        self._paginas = paginas if paginas is not None else ["Texto"]

    async def leer(self, contenido: bytes) -> list[str]:
        self.contenido = contenido
        return self._paginas


def test_convertir_returns_the_markdown_of_the_pages() -> None:
    service = ConversionService(StubLector())

    documento = asyncio.run(service.convertir(PDF_CONTENT))

    assert documento == DocumentoMarkdown(content="## Página 1\n\nTexto", page_count=1)


def test_convertir_writes_one_heading_per_page() -> None:
    service = ConversionService(StubLector(["Hola", "Chau"]))

    documento = asyncio.run(service.convertir(PDF_CONTENT))

    assert documento == DocumentoMarkdown(
        content="## Página 1\n\nHola\n\n## Página 2\n\nChau", page_count=2
    )


def test_convertir_keeps_the_heading_of_a_page_without_text() -> None:
    service = ConversionService(StubLector(["Hola", ""]))

    documento = asyncio.run(service.convertir(PDF_CONTENT))

    assert documento.content == "## Página 1\n\nHola\n\n## Página 2"


def test_convertir_passes_the_bytes_to_the_reader() -> None:
    lector = StubLector()

    asyncio.run(ConversionService(lector).convertir(PDF_CONTENT))

    assert lector.contenido == PDF_CONTENT


@pytest.mark.parametrize("contenido", [b"", b"no soy un pdf"])
def test_convertir_rejects_content_that_is_not_a_pdf(contenido) -> None:
    lector = StubLector()

    with pytest.raises(PdfInvalidError):
        asyncio.run(ConversionService(lector).convertir(contenido))

    assert lector.contenido is None
