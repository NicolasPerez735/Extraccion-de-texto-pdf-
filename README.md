# PDF Extraction

Base del microservicio de extracción de texto de documentos PDF, organizada en
capas y preparada para incorporar el contrato compartido
`microservicios-pdf v1.0.0`.

## Responsabilidad

El servicio extraerá texto de documentos PDF cuando el contrato compartido y la
librería de extracción sean confirmados. OCR, interpretación semántica,
persistencia, colas y autenticación quedan fuera del alcance actual.

## Estructura

```text
pdf-extraction/
├── app/
│   ├── main.py
│   ├── controllers/
│   ├── schemas/
│   ├── services/
│   ├── models/
│   └── core/
├── tests/
│   ├── unit/
│   └── integration/
├── pyproject.toml
├── .env.example
└── README.md
```

La dirección de dependencias prevista es:
`controllers -> services -> core/repositories`, con los schemas HTTP separados
de los modelos de dominio.

## Estado actual

Esta entrega crea únicamente la estructura y los límites de las capas. Incluye
`GET /health` como endpoint técnico. Los campos de extracción, códigos de
error, `X-Correlation-ID` y el endpoint `POST /extract` quedan pendientes de
confirmación contra `microservicios-pdf v1.0.0`, que no está incluido en el
clon actual.

## Instalación y ejecución

Requiere Python 3.11 y [uv](https://docs.astral.sh/uv/).

```powershell
uv sync
uv run uvicorn app.main:app --reload
```

La documentación interactiva queda disponible en `http://127.0.0.1:8000/docs`.

## Calidad

```powershell
uv run pytest
uv run ruff check .
uv run black --check .
```

## Configuración

Copia `.env.example` como `.env`. No se versionan secretos. Las variables se
cargan mediante Pydantic Settings.
