import hashlib
import logging

from fastapi.testclient import TestClient

from app.main import app


def _mensajes(caplog) -> list[str]:
    return [record.getMessage() for record in caplog.records]


def test_extraccion_registra_paginas_y_checksum(client, pdf_request, pdf_bytes, caplog):
    caplog.set_level(logging.INFO)

    client.post("/extraer", json=pdf_request, headers={"X-Correlation-ID": "cid-1"})

    checksum = hashlib.sha256(pdf_bytes).hexdigest()
    eventos = [
        record
        for record in caplog.records
        if f"checksum={checksum}" in record.getMessage()
    ]
    assert len(eventos) == 1
    assert eventos[0].levelno == logging.INFO
    assert "paginas=1" in eventos[0].getMessage()
    assert eventos[0].correlation_id == "cid-1"


def test_los_logs_no_incluyen_datos_sensibles(client, pdf_request, caplog):
    caplog.set_level(logging.DEBUG)

    client.post("/extraer", json=pdf_request)

    todo = "\n".join(_mensajes(caplog))
    assert "contrato.pdf" not in todo
    assert "Texto de prueba" not in todo
    assert pdf_request["archivo_base64"] not in todo


def test_el_acceso_se_registra_con_el_correlation_id_del_request(client, caplog):
    caplog.set_level(logging.INFO)

    client.get("/health", headers={"X-Correlation-ID": "cid-2"})

    accesos = [r for r in caplog.records if "path=/health" in r.getMessage()]
    assert len(accesos) == 1
    assert accesos[0].correlation_id == "cid-2"
    assert "correlation_id=" not in accesos[0].getMessage()


def test_registra_inicio_y_apagado_ordenados(caplog):
    caplog.set_level(logging.INFO)

    with TestClient(app):
        pass

    mensajes = _mensajes(caplog)
    assert "servicio iniciado" in mensajes
    assert mensajes.index("apagado iniciado") < mensajes.index("apagado completo")
