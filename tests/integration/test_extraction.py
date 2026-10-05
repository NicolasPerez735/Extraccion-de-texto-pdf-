from fastapi.testclient import TestClient


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
