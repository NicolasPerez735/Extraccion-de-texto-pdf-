from app.core.config import Settings


def test_los_limites_de_extract_se_leen_del_entorno(monkeypatch) -> None:
    monkeypatch.setenv("EXTRACT_WORKERS", "2")
    monkeypatch.setenv("EXTRACT_MAX_QUEUE", "8")
    monkeypatch.setenv("EXTRACT_QUEUE_TIMEOUT_SECONDS", "2.5")

    settings = Settings(_env_file=None)

    assert settings.extract_workers == 2
    assert settings.extract_max_queue == 8
    assert settings.extract_queue_timeout_seconds == 2.5


def test_los_limites_de_extract_tienen_valores_por_defecto() -> None:
    # Medido en el TP (docs/informe-carga.md, 5.3): con espera máxima de 10 s vegeta
    # perdía el 19 % por 503 aunque esas requests llegaban dentro de los 30 s del
    # cliente. La espera máxima queda por debajo de ese timeout y la cola alcanza para
    # la ráfaga de 50 req/s durante 30 s repartida en 5 réplicas.
    settings = Settings(_env_file=None)

    assert settings.extract_workers == 1
    assert settings.extract_max_queue == 100
    assert settings.extract_queue_timeout_seconds == 25
