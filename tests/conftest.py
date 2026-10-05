from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def pdf_bytes() -> bytes:
    stream = b"BT /F1 18 Tf 20 150 Td (Texto de prueba) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
    ]
    document = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(document))
        document += f"{number} 0 obj\n".encode()
        document += obj + b"\nendobj\n"
    xref_offset = len(document)
    document += f"xref\n0 {len(objects) + 1}\n".encode()
    document += b"0000000000 65535 f \n"
    document += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    document += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode()
    return bytes(document)


@pytest.fixture
def pdf_upload(pdf_bytes: bytes) -> dict[str, tuple[str, BytesIO, str]]:
    return {
        "file": ("documento.pdf", BytesIO(pdf_bytes), "application/pdf"),
    }
