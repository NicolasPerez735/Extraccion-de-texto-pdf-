import base64
import hashlib
import logging

import pytest
from fastapi.testclient import TestClient


def encode(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")


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


def test_corrupted_pdf_returns_pdf_corrupted(client: TestClient) -> None:
    response = client.post(
        "/extraer",
        json={
            "archivo_base64": encode(b"%PDF-1.4\ncontenido roto"),
            "nombre": "roto.pdf",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "PDF_CORRUPTED"


def test_pdf_without_text_returns_empty_text(client: TestClient, make_pdf) -> None:
    # Decisión del grupo: un PDF sin texto (por ejemplo, escaneado) es válido;
    # el contrato no tiene un código de error para este caso.
    response = client.post(
        "/extraer",
        json={"archivo_base64": encode(make_pdf("")), "nombre": "escaneo.pdf"},
    )

    assert response.status_code == 200
    assert response.json()["texto"] == ""
    assert response.json()["paginas"] == 1


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"nombre": "contrato.pdf"}, id="sin-archivo"),
        pytest.param({"archivo_base64": "JVBERi0="}, id="sin-nombre"),
        pytest.param({"archivo_base64": "JVBERi0=", "nombre": ""}, id="nombre-vacio"),
    ],
)
def test_invalid_request_returns_validation_error(
    client: TestClient, body: dict[str, str]
) -> None:
    response = client.post(
        "/extraer", json=body, headers={"X-Correlation-ID": "request-invalido"}
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["correlation_id"] == "request-invalido"


def test_unexpected_error_returns_internal_error(
    failing_client: TestClient, pdf_request: dict[str, str]
) -> None:
    response = failing_client.post(
        "/extraer", json=pdf_request, headers={"X-Correlation-ID": "falla-500"}
    )

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "Error interno del servidor.",
            "details": {},
            "correlation_id": "falla-500",
        }
    }
    assert response.headers["X-Correlation-ID"] == "falla-500"


def test_extraer_reports_the_extraction_time(
    client: TestClient, pdf_request: dict[str, str]
) -> None:
    response = client.post("/extraer", json=pdf_request)

    assert float(response.headers["X-Extraction-Time-Ms"]) >= 0


def test_request_log_includes_correlation_id(
    client: TestClient, pdf_request: dict[str, str], caplog
) -> None:
    caplog.set_level(logging.INFO, logger="extraccion_texto")

    client.post("/extraer", json=pdf_request, headers={"X-Correlation-ID": "log-123"})

    assert "correlation_id=log-123" in caplog.text
    assert "path=/extraer" in caplog.text


def test_error_log_includes_code_and_correlation_id(client: TestClient, caplog) -> None:
    caplog.set_level(logging.INFO, logger="extraccion_texto")

    client.post(
        "/extraer",
        json={"archivo_base64": "no-es-base64", "nombre": "contrato.pdf"},
        headers={"X-Correlation-ID": "log-error"},
    )

    assert "correlation_id=log-error code=PDF_INVALID" in caplog.text
