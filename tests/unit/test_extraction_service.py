import asyncio
import base64
import hashlib

import pytest

from app.core.exceptions import PdfInvalidError
from app.services.extraction import ExtractionService

PDF_CONTENT = b"%PDF-1.4\ncontenido\n%%EOF"


class StubLector:
    def __init__(self, paginas: list[str] | None = None) -> None:
        self.contenido: bytes | None = None
        self._paginas = paginas if paginas is not None else ["Texto extraído"] * 3

    async def leer(self, contenido: bytes) -> list[str]:
        self.contenido = contenido
        return self._paginas


def encode(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")


def extraer(service: ExtractionService, archivo_base64: str):
    return asyncio.run(service.extraer(archivo_base64, "contrato.pdf"))


def test_extraer_returns_the_contract_fields() -> None:
    service = ExtractionService(StubLector(["Texto extraído"]))

    result = extraer(service, encode(PDF_CONTENT))

    assert result.nombre == "contrato.pdf"
    assert result.texto == "Texto extraído"
    assert result.checksum == hashlib.sha256(PDF_CONTENT).hexdigest()
    assert result.tamano_bytes == len(PDF_CONTENT)
    assert result.paginas == 1


def test_extraer_joins_the_pages_with_text_and_counts_them_all() -> None:
    service = ExtractionService(StubLector(["Hola", "", "Chau"]))

    result = extraer(service, encode(PDF_CONTENT))

    assert result.texto == "Hola\nChau"
    assert result.paginas == 3


def test_extraer_passes_the_decoded_bytes_to_the_reader() -> None:
    lector = StubLector()

    extraer(ExtractionService(lector), encode(PDF_CONTENT))

    assert lector.contenido == PDF_CONTENT


@pytest.mark.parametrize(
    "archivo_base64",
    [
        pytest.param("no-es-base64", id="base64-invalido"),
        pytest.param("", id="archivo-vacio"),
        pytest.param(encode(b"texto plano"), id="no-es-pdf"),
    ],
)
def test_extraer_rejects_content_that_is_not_a_pdf(archivo_base64: str) -> None:
    lector = StubLector()

    with pytest.raises(PdfInvalidError):
        extraer(ExtractionService(lector), archivo_base64)

    assert lector.contenido is None


def test_extraer_accepts_base64_with_line_breaks() -> None:
    lector = StubLector()
    wrapped = base64.encodebytes(PDF_CONTENT).decode("ascii")

    extraer(ExtractionService(lector), wrapped)

    assert lector.contenido == PDF_CONTENT
