import base64
import hashlib

from app.models.extraction import TextoExtraido
from app.services.extraction import ExtractionService

PDF_CONTENT = b"%PDF-1.4\ncontenido\n%%EOF"


class StubExtractor:
    def __init__(self, texto: str = "Texto extraído", paginas: int = 3) -> None:
        self.content: bytes | None = None
        self._resultado = TextoExtraido(texto=texto, paginas=paginas)

    def extract(self, content: bytes) -> TextoExtraido:
        self.content = content
        return self._resultado


def encode(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")


def test_extraer_returns_the_contract_fields() -> None:
    service = ExtractionService(StubExtractor())

    result = service.extraer(encode(PDF_CONTENT), "contrato.pdf")

    assert result.nombre == "contrato.pdf"
    assert result.texto == "Texto extraído"
    assert result.checksum == hashlib.sha256(PDF_CONTENT).hexdigest()
    assert result.tamano_bytes == len(PDF_CONTENT)
    assert result.paginas == 3


def test_extraer_passes_the_decoded_bytes_to_the_extractor() -> None:
    extractor = StubExtractor()
    service = ExtractionService(extractor)

    service.extraer(encode(PDF_CONTENT), "contrato.pdf")

    assert extractor.content == PDF_CONTENT
