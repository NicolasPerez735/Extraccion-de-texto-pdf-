from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Correlation-ID"]


def test_extracts_text_from_a_pdf(
    client: TestClient,
    pdf_upload: dict[str, tuple[str, object, str]],
) -> None:
    response = client.post("/extract", files=pdf_upload)

    assert response.status_code == 200
    assert response.json()["text"] == "Texto de prueba"


def test_rejects_a_non_pdf_upload(client: TestClient) -> None:
    response = client.post(
        "/extract",
        files={"file": ("documento.txt", b"texto plano", "text/plain")},
    )

    assert response.status_code == 400


def test_rejects_an_empty_pdf(client: TestClient) -> None:
    response = client.post(
        "/extract",
        files={"file": ("vacio.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400


def test_rejects_a_corrupted_pdf(client: TestClient) -> None:
    response = client.post(
        "/extract",
        files={"file": ("corrupto.pdf", b"no es un pdf", "application/pdf")},
    )

    assert response.status_code == 400


def test_error_response_contains_code_and_correlation_id(client: TestClient) -> None:
    response = client.post(
        "/extract",
        files={"file": ("documento.txt", b"texto plano", "text/plain")},
        headers={"X-Correlation-ID": "error-correlation-id"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "code": "UNSUPPORTED_FILE_TYPE",
        "detail": "El archivo debe ser un PDF válido.",
        "correlation_id": "error-correlation-id",
    }


def test_rejects_a_request_without_file(client: TestClient) -> None:
    response = client.post("/extract")

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_REQUEST"
    assert response.headers["X-Correlation-ID"]


def test_rejects_a_pdf_over_the_configured_limit(client: TestClient) -> None:
    response = client.post(
        "/extract",
        files={
            "file": (
                "grande.pdf",
                b"x" * (5 * 1024 * 1024 + 1),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"


def test_returns_the_provided_correlation_id(
    client: TestClient,
    pdf_upload: dict[str, tuple[str, object, str]],
) -> None:
    response = client.post(
        "/extract",
        files=pdf_upload,
        headers={"X-Correlation-ID": "test-correlation-id"},
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "test-correlation-id"


def test_generates_a_correlation_id_when_missing(
    client: TestClient,
    pdf_upload: dict[str, tuple[str, object, str]],
) -> None:
    response = client.post("/extract", files=pdf_upload)

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"]
