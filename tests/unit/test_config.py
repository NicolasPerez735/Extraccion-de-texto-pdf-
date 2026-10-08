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
    settings = Settings(_env_file=None)

    assert settings.extract_workers == 1
    assert settings.extract_max_queue == 20
    assert settings.extract_queue_timeout_seconds == 10
