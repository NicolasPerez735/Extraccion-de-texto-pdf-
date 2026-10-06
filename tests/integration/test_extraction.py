import hashlib

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Correlation-ID"]


def test_extraer_returns_the_contract_document(
    client: TestClient, pdf_bytes: bytes, pdf_request: dict[str, str]
) -> None:
    response = client.post("/extraer", json=pdf_request)

    assert response.status_code == 200
    assert response.json() == {
        "nombre": "contrato.pdf",
        "texto": "Texto de prueba",
        "checksum": hashlib.sha256(pdf_bytes).hexdigest(),
        "tamano_bytes": len(pdf_bytes),
        "paginas": 1,
    }


def test_returns_the_provided_correlation_id(
    client: TestClient, pdf_request: dict[str, str]
) -> None:
    response = client.post(
        "/extraer",
        json=pdf_request,
        headers={"X-Correlation-ID": "test-correlation-id"},
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "test-correlation-id"


def test_generates_a_correlation_id_when_missing(
    client: TestClient, pdf_request: dict[str, str]
) -> None:
    response = client.post("/extraer", json=pdf_request)

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"]


def test_invalid_pdf_returns_the_common_error_format(client: TestClient) -> None:
    response = client.post(
        "/extraer",
        json={"archivo_base64": "no-es-base64", "nombre": "contrato.pdf"},
        headers={"X-Correlation-ID": "error-correlation-id"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "PDF_INVALID"
    assert error["message"]
    assert error["details"] == {}
    assert error["correlation_id"] == "error-correlation-id"
    assert response.headers["X-Correlation-ID"] == "error-correlation-id"
