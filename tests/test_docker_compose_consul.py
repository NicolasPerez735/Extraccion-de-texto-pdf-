from pathlib import Path

COMPOSE = Path(__file__).resolve().parents[1] / "docker-compose.yml"


def test_el_compose_del_tp_levanta_sin_la_infraestructura_de_consul():
    # El TP de carga se corrige con `docker compose up --build` desde un clon limpio:
    # no puede depender del token de Consul generado en ../dockers. El registro en
    # Consul de extraccion se hace en el compose de integracion (el oficial).
    text = COMPOSE.read_text(encoding="utf-8")
    assert "consul_microservices_token" not in text
    assert "../dockers/" not in text
    assert "CONSUL_ENABLED" not in text
    # Ni la red externa redutn: desde un clon limpio no existe, y el proxy del TP tiene
    # que compartir la red con las réplicas para poder repartirles las requests.
    assert "redutn" not in text
