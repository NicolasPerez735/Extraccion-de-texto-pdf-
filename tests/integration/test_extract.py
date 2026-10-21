"""POST /extract (TP de carga): PDF binario en el body → Markdown y páginas."""

import pytest
from fastapi.testclient import TestClient

from app.core.composition import get_conversion_service
from app.main import app
from app.services.conversion import ConversionService

PDF_HEADERS = {"Content-Type": "application/pdf"}


@pytest.fixture
def extract_client(lector):
    service = ConversionService(lector)
    app.dependency_overrides[get_conversion_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_extract_responds_503_quickly_when_the_service_is_saturated(
    lector_saturado, make_pdf
) -> None:
    service = ConversionService(lector_saturado)
    app.dependency_overrides[get_conversion_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/extract", content=make_pdf("Hola"), headers=PDF_HEADERS
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    error = response.json()["error"]
    assert error["code"] == "DEPENDENCY_UNAVAILABLE"
    assert error["details"] == {"reason": "cola_llena"}


def test_extract_returns_the_markdown_and_the_page_count(
    extract_client, make_pdf
) -> None:
    response = extract_client.post(
        "/extract", content=make_pdf("Hola", "Chau"), headers=PDF_HEADERS
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "content": "## Página 1\n\nHola\n\n## Página 2\n\nChau",
        "page_count": 2,
    }


def test_extract_keeps_the_heading_of_a_page_without_text(
    extract_client, make_pdf
) -> None:
    response = extract_client.post(
        "/extract", content=make_pdf("Hola", ""), headers=PDF_HEADERS
    )

    assert response.json()["content"] == "## Página 1\n\nHola\n\n## Página 2"


def test_extract_reports_the_extraction_time(extract_client, make_pdf) -> None:
    response = extract_client.post(
        "/extract", content=make_pdf("Hola"), headers=PDF_HEADERS
    )

    assert float(response.headers["X-Extraction-Time-Ms"]) >= 0


def test_extract_returns_the_provided_correlation_id(extract_client, make_pdf) -> None:
    response = extract_client.post(
        "/extract",
        content=make_pdf("Hola"),
        headers={**PDF_HEADERS, "X-Correlation-ID": "abc-123"},
    )

    assert response.headers["X-Correlation-ID"] == "abc-123"


@pytest.mark.parametrize("body", [b"", b"no soy un pdf"])
def test_extract_rejects_a_body_that_is_not_a_pdf(extract_client, body) -> None:
    response = extract_client.post("/extract", content=body, headers=PDF_HEADERS)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PDF_INVALID"


def test_extract_rejects_a_corrupted_pdf(extract_client) -> None:
    response = extract_client.post(
        "/extract", content=b"%PDF-1.4\nbasura", headers=PDF_HEADERS
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PDF_CORRUPTED"
