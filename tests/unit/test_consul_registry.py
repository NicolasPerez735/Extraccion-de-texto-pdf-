import asyncio
import json
from pathlib import Path

import httpx

from app.core.config import Settings
from app.core.consul_registry import ConsulRegistry


def settings(tmp_path: Path) -> Settings:
    token = tmp_path / "consul.token"
    token.write_text("test-token", encoding="utf-8")
    return Settings(
        _env_file=None,
        consul_enabled=True,
        consul_http_addr="http://consul:8500",
        consul_http_token_file=str(token),
        consul_service_address="extraccion",
        consul_service_port=8000,
    )


def test_register_and_deregister_extraccion(tmp_path: Path):
    requests = []

    async def responder(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200)

    registry = ConsulRegistry(
        settings=settings(tmp_path),
        instance_id="extraccion-instance-a",
        transport=httpx.MockTransport(responder),
    )

    asyncio.run(registry.register())
    asyncio.run(registry.deregister())

    payload = json.loads(requests[0].content)
    assert requests[0].headers["X-Consul-Token"] == "test-token"
    assert payload["ID"] == "extraccion-instance-a"
    assert payload["Name"] == "extraccion"
    assert payload["Address"] == "extraccion"
    assert payload["Port"] == 8000
    assert payload["Checks"][0]["HTTP"] == "http://extraccion:8000/health"
    # Servicio interno (contrato: solo el orquestador es público): sin etiquetas de
    # Traefik, así Consul Catalog no lo publica.
    assert not [tag for tag in payload["Tags"] if tag.startswith("traefik")]
    assert str(requests[1].url).endswith(
        "/v1/agent/service/deregister/extraccion-instance-a"
    )
