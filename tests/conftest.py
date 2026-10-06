import base64

import pytest
from fastapi.testclient import TestClient

from app.core.composition import get_extraction_service
from app.main import app


def build_pdf(*page_texts: str) -> bytes:
    """Arma un PDF mínimo con una página por texto; un texto vacío da una
    página sin contenido."""
    objects: dict[int, bytes] = {
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    page_numbers = []
    for index, text in enumerate(page_texts):
        page_number, content_number = 4 + 2 * index, 5 + 2 * index
        stream = f"BT /F1 18 Tf 20 150 Td ({text}) Tj ET".encode() if text else b""
        objects[page_number] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents %d 0 R >>"
            % content_number
        )
        objects[content_number] = b"<< /Length %d >>\nstream\n%s\nendstream" % (
            len(stream),
            stream,
        )
        page_numbers.append(page_number)
    kids = " ".join(f"{number} 0 R" for number in page_numbers).encode()
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_numbers))

    document = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number in range(1, len(objects) + 1):
        offsets.append(len(document))
        document += f"{number} 0 obj\n".encode() + objects[number] + b"\nendobj\n"
    xref_offset = len(document)
    document += f"xref\n0 {len(objects) + 1}\n".encode()
    document += b"0000000000 65535 f \n"
    document += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    document += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode()
    return bytes(document)


def encode(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def make_pdf():
    return build_pdf


@pytest.fixture
def pdf_bytes() -> bytes:
    return build_pdf("Texto de prueba")


@pytest.fixture
def pdf_request(pdf_bytes: bytes) -> dict[str, str]:
    return {"archivo_base64": encode(pdf_bytes), "nombre": "contrato.pdf"}


class ServicioQueFalla:
    """Doble de test: simula un error no previsto dentro del servicio."""

    def extraer(self, archivo_base64: str, nombre: str):
        raise RuntimeError("falla inesperada")


@pytest.fixture
def failing_client():
    app.dependency_overrides[get_extraction_service] = ServicioQueFalla
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
