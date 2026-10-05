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
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]"
        b"/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj\n"
        b"4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        + f"5 0 obj<</Length {len(stream)}>>stream\n".encode()
        + stream
        + b"\nendstream endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
    )


@pytest.fixture
def pdf_upload(pdf_bytes: bytes) -> dict[str, tuple[str, BytesIO, str]]:
    return {
        "file": ("documento.pdf", BytesIO(pdf_bytes), "application/pdf"),
    }
