# PDF Extraction

Base del microservicio de extracción de texto de documentos PDF, organizada en
capas y preparada para incorporar el contrato compartido
`microservicios-pdf v1.0.0`.

## Responsabilidad

El servicio extrae texto de documentos PDF mediante `pypdf`. OCR,
interpretación semántica, persistencia, colas y autenticación quedan fuera del
alcance actual.

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

## Endpoints actuales

- `GET /health` devuelve el estado técnico del servicio.
- `POST /extract` recibe un archivo multipart en el campo `file` y devuelve
  `{ "text": "..." }`.
- Las respuestas incluyen `X-Correlation-ID`; si el cliente no lo envía, el
  servicio genera uno.
- Solo se aceptan archivos con `Content-Type: application/pdf`.
- El tamaño máximo predeterminado es 5 MiB.
- Los errores devuelven `code`, `detail` y `correlation_id`.

La forma definitiva del contrato compartido `microservicios-pdf v1.0.0`
determinará si deben agregarse campos o reglas adicionales.

### Ejemplo

```powershell
curl.exe -X POST http://127.0.0.1:8000/extract `
  -H "X-Correlation-ID: local-test" `
  -F "file=@documento.pdf;type=application/pdf"
```

Respuesta exitosa:

```json
{"text":"Texto extraído del documento"}
```

Errores:

```json
{
  "code": "UNSUPPORTED_FILE_TYPE",
  "detail": "El archivo debe ser un PDF válido.",
  "correlation_id": "local-test"
}
```

## Instalación y ejecución

Requiere Python 3.11 y [uv](https://docs.astral.sh/uv/).

```powershell
uv sync
uv run uvicorn app.main:app --reload
```

La documentación interactiva queda disponible en `http://127.0.0.1:8000/docs`.

## Docker

La imagen se construye sin incluir `Contexto/`, secretos ni caches locales:

```powershell
docker build -t pdf-extraction .
docker run --rm -p 8000:8000 pdf-extraction
```

El contenedor ejecuta la aplicación como `appuser` y expone un healthcheck
contra `GET /health`. La persistencia y MongoDB no forman parte de esta versión.

## Calidad

```powershell
uv run pytest
uv run ruff check .
uv run black --check .
```

## Configuración

Copia `.env.example` como `.env`. No se versionan secretos. Las variables se
cargan mediante Pydantic Settings.

| Variable | Predeterminado | Descripción |
| --- | --- | --- |
| `SERVICE_NAME` | `pdf-extraction` | Nombre del servicio. |
| `ENVIRONMENT` | `development` | Entorno de ejecución. |
| `LOG_LEVEL` | `INFO` | Nivel de logging. |
| `MAX_PDF_SIZE_MB` | `5` | Tamaño máximo aceptado para un PDF. |

## Alcance y deuda técnica

Esta versión no persiste resultados y no incluye OCR, autenticación, colas ni
integraciones externas. El contrato compartido puede requerir ampliar los
schemas antes de considerar estable la API pública.
