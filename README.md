# PDF Extraction (`extraccion-texto`)

Microservicio de extracción de texto de documentos PDF del proyecto
`microservicios-pdf`. Implementa la sección `extraccion-texto` del contrato
compartido `microservicios-pdf` (versión 1.3.0, en el repo `integracion`), y el endpoint
`POST /extract` del TP de carga y estrés (ver [TP de carga](#tp-de-carga-post-extract)).

## Responsabilidad

Hace:

- Recibir un PDF validado en Base64 junto con su nombre.
- Extraer el texto de todas las páginas con `pypdf`.
- Contar las páginas.
- Calcular el checksum SHA-256 del archivo.
- Propagar `X-Correlation-ID` y registrarlo en cada línea de log.
- TP de carga: convertir un PDF binario a Markdown con PyMuPDF (`POST /extract`).

No hace:

- Persistir información ni usar MongoDB o Redis.
- Validar el tamaño máximo del archivo (lo hace `validacion-pdf`).
- OCR: un PDF escaneado devuelve texto vacío.

## Endpoints

| Método | Ruta | Descripción |
| --- | --- | --- |
| `POST` | `/extraer` | Extrae texto, páginas y checksum de un PDF en Base64. |
| `POST` | `/extract` | TP de carga: PDF binario en el body → `{"content": <Markdown>, "page_count": N}`. |
| `GET` | `/health` | Healthcheck del servicio. |

La documentación interactiva queda disponible en `http://127.0.0.1:8000/docs`.

### Request

```json
{
  "archivo_base64": "JVBERi0xLjQK...",
  "nombre": "contrato.pdf"
}
```

Ambos campos son obligatorios. Se aceptan espacios y saltos de línea dentro
del Base64.

### Response exitosa

HTTP `200`:

```json
{
  "nombre": "contrato.pdf",
  "texto": "Contenido extraído del PDF",
  "checksum": "a7f5...",
  "tamano_bytes": 245760,
  "paginas": 3
}
```

- `checksum`: SHA-256 en hexadecimal de los bytes del archivo.
- `texto`: el texto de cada página con contenido, separado por saltos de línea.
  Un PDF sin texto (por ejemplo, escaneado) responde `200` con `"texto": ""`.

El header `X-Extraction-Time-Ms` informa cuánto tardó la extracción (decodificar,
leer con pypdf y calcular el checksum), separado del tiempo total de la request.

### Errores

Formato común del contrato:

```json
{
  "error": {
    "code": "PDF_CORRUPTED",
    "message": "El archivo PDF está corrupto.",
    "details": {},
    "correlation_id": "8f6f7c3e-12d5-4f57-9c6c-123456789abc"
  }
}
```

| Código | HTTP | Cuándo |
| --- | ---: | --- |
| `VALIDATION_ERROR` | `400` | Falta `archivo_base64` o `nombre`, `nombre` vacío o body inválido. |
| `PDF_INVALID` | `422` | Base64 inválido, archivo vacío o contenido sin la firma `%PDF`. |
| `PDF_CORRUPTED` | `422` | pypdf no puede abrir el archivo, recorrer sus páginas o extraer el texto. |
| `INTERNAL_ERROR` | `500` | Error no previsto. |

### Ejemplo

```powershell
$body = @{
  archivo_base64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes(".\contrato.pdf"))
  nombre = "contrato.pdf"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/extraer `
  -ContentType "application/json" -Headers @{ "X-Correlation-ID" = "local-test" } `
  -Body $body
```

## Arquitectura

```text
app/
├── main.py                    # ensamblado: routers, middleware, errores, logs
├── controllers/
│   ├── extraction.py          # POST /extraer
│   └── health.py              # GET /health
├── schemas/                   # request, response y error del contrato
├── services/
│   ├── extraction.py          # caso de uso: Base64, checksum, delega en el extractor
│   └── text_extractor.py      # puerto TextExtractor (Protocol)
├── models/
│   └── extraction.py          # TextoExtraido, PdfExtraction (dataclasses)
└── core/
    ├── composition.py         # único lugar donde se arma el servicio
    ├── pdf_text_extractor.py  # adaptador de pypdf
    ├── logs.py                # carga logging.json y agrega el correlation_id
    ├── config.py
    └── exceptions.py          # PdfInvalidError, PdfCorruptedError
```

Dirección de dependencias: `controller → service → TextExtractor (puerto)`,
con el adaptador de pypdf en `core/`. El service no importa FastAPI ni pypdf, y
recibe el extractor por constructor, sin valor por defecto.

**Rendimiento.** `POST /extraer` es un endpoint sincrónico a propósito: FastAPI
lo ejecuta en su threadpool, así pypdf (sincrónico y con uso intensivo de CPU)
no bloquea el event loop y `/health` sigue respondiendo bajo carga. Por el GIL,
el paralelismo real se obtiene con réplicas detrás de Traefik.

## Logs (12-Factor XI)

Van a `stdout`, sin archivos. La configuración está en [`logging.json`](logging.json),
en la raíz del repo (formato `dictConfig`), y el nivel sale de `LOG_LEVEL`. Cada línea
lleva fecha, nivel, logger y `correlation_id` (`-` fuera de una request):

```text
INFO extraccion_texto correlation_id=- servicio iniciado
INFO app.services.extraction correlation_id=en-curso texto extraido paginas=1500 tamano_bytes=354327 caracteres=5526148 checksum=367aea83...
INFO extraccion_texto correlation_id=en-curso method=POST path=/extraer status=200 duracion_ms=17833.1
WARNING extraccion_texto correlation_id=demo-2 code=PDF_INVALID status=422 message=El archivo no es un PDF válido.
```

| Nivel | Qué registra este servicio |
| --- | --- |
| `INFO` | Cada request (`method`, `path`, `status`, `duracion_ms`), el texto extraído (`paginas`, `tamano_bytes`, `caracteres`, `checksum`), inicio y apagado. |
| `WARNING` | Rechazos del contrato (`PDF_INVALID`, `PDF_CORRUPTED`, `VALIDATION_ERROR`) con su `code`. |
| `ERROR` | Error no previsto (`INTERNAL_ERROR`), con traceback. |

**No se registran** el Base64, el texto extraído ni el nombre del archivo (puede tener
datos personales): el documento se identifica por su `checksum`. Hay un test que lo
verifica. El `correlation_id` viaja en un `ContextVar` y lo agrega el formato, así que
llega también al threadpool donde corre pypdf. Los avisos internos de pypdf quedan en
`ERROR`, y el access log de uvicorn está desactivado porque lo registra la app.

## Finalización segura (12-Factor IX)

La imagen corre uvicorn como PID 1 con `--timeout-graceful-shutdown 30`. Ante `SIGTERM`
(`docker stop`) deja de aceptar conexiones, termina las extracciones en curso, ejecuta el
cierre del `lifespan` (`apagado iniciado` / `apagado completo`) y sale con código 0. Para
que Docker no mande `SIGKILL` antes, detener con `docker stop -t 40` (en el compose de
integración, `stop_grace_period: 40s`).

Prueba hecha con la imagen `1.0.3` (2026-10-07): extracción de un PDF de 1500 páginas
(18 s) y `docker stop -t 40` a los 4 s.

| Qué se miró | Resultado |
| --- | --- |
| Request en curso | `200` con el texto completo |
| Request nueva durante el apagado | rechazada (puerto ya cerrado) |
| Logs | `Shutting down` → `Waiting for connections to close` → la extracción termina → `apagado iniciado` → `apagado completo` |
| `docker inspect --format '{{.State.ExitCode}}'` | `0` |

## Instalación y ejecución

Requiere Python 3.11 y [uv](https://docs.astral.sh/uv/).

```powershell
uv sync
uv run uvicorn app.main:app --reload
```

## Configuración

Copiar `.env.example` como `.env`. No se versionan secretos.

| Variable | Predeterminado | Descripción |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` o `ERROR`. Otro valor impide arrancar. |
| `EXTRACT_WORKERS` | `1` | Procesos que convierten a Markdown en cada réplica (`/extract`). |
| `EXTRACT_MAX_QUEUE` | `100` | Requests de `/extract` que pueden esperar un worker; más → `503`. |
| `EXTRACT_QUEUE_TIMEOUT_SECONDS` | `25` | Espera máxima por un worker; más → `503`. |
| `PUERTO` | `8080` | Solo `docker-compose.yml`: puerto del host donde publica el proxy. |

Las tres `EXTRACT_*` son opcionales y solo afectan a `/extract` (contrato 1.3.0).

## Docker

```powershell
docker build -t extraccion-texto:1.1.2 .
docker run --rm -p 8000:8000 extraccion-texto:1.1.2
```

La versión del servicio es la de `pyproject.toml` (1.1.2): es la que muestra Swagger en
`/docs` y el tag de la imagen. `tests/integration/test_openapi.py` verifica que
`FastAPI(version=...)` en `app/main.py` coincida con `pyproject.toml`; en una versión
nueva se cambian los dos.

La imagen corre como `appuser` y tiene un `HEALTHCHECK` contra `GET /health`.

## TP de carga (`POST /extract`)

Trabajo práctico de carga, estrés y optimización. El informe técnico (arquitectura, cuello
de botella, proceso de investigación y métricas antes y después) está en
[docs/informe-carga.md](docs/informe-carga.md).

```bash
uv run tests/stress/generar_pdfs.py               # o copiar la carpeta oficial en tests/stress/pdfs/
docker compose up --build                         # 5 réplicas + Traefik en http://localhost:8080
k6 run tests/stress/spike.js                      # spike: 100 VUs, 40 s
./tests/stress/run_vegeta.sh                      # carga fija: 50 req/s, 30 s, timeout 30 s
./tests/stress/medir.sh <etiqueta>                # las dos, con resultados en tests/stress/resultados/
```

Ejemplo con curl:

```bash
curl -X POST http://localhost:8080/extract -H "Content-Type: application/pdf"      --data-binary @tests/stress/pdfs/01-liviano.pdf
```

- PyMuPDF convierte en un pool de procesos, separado del event loop de FastAPI.
- Backpressure: con la cola llena o la espera vencida responde enseguida
  `503 DEPENDENCY_UNAVAILABLE` con `details.reason` y `Retry-After: 1`.
- Cada contenedor del `docker-compose.yml` tiene límite de CPU y memoria (1 CPU y 1 GB por
  réplica; 1 CPU y 512 MB el proxy).

## Tests y calidad

```powershell
uv run pytest
uv run ruff check .
uv run black --check .
```

La suite es hermética: no necesita red, base de datos ni `.env`.

- **Unitarios del servicio:** campos del contrato, checksum, bytes que llegan
  al extractor, Base64 inválido, archivo vacío, contenido que no es PDF, Base64
  con saltos de línea. Usan un extractor de prueba inyectado.
- **Unitarios del adaptador de pypdf:** varias páginas, PDF truncado y PDF con
  el árbol de páginas roto, con PDFs reales generados en `tests/conftest.py`.
- **Integración HTTP:** respuesta del contrato, cada código de error, PDF sin
  texto, `X-Correlation-ID`, `X-Extraction-Time-Ms` y logs. El error no previsto
  se prueba inyectando un servicio que falla (`app.dependency_overrides`).
- **Logs:** `LOG_LEVEL` inválido, formato con `correlation_id`, evento de extracción,
  ausencia de datos sensibles, inicio y apagado en el `lifespan`.

Queda fuera a propósito: la imagen Docker (se verifica con su healthcheck) y el
apagado con `SIGTERM`, que depende del proceso de uvicorn y se probó a mano (ver
"Finalización segura").

## Decisiones y deuda técnica

- **PDF sin texto → 200 con texto vacío.** El contrato lo nombra entre los
  casos a cubrir pero no le asigna código; es un PDF válido y se puede guardar.
- **Sin límite de tamaño.** El contrato asigna esa validación a
  `validacion-pdf`; el orquestador siempre valida antes de extraer.
- **Errores de pypdf → `PDF_CORRUPTED`.** Se captura `PyPdfError` (la base de
  los errores de pypdf). Una excepción de otro tipo responde
  `INTERNAL_ERROR`.
- **Historial de TDD.** El primer ciclo tuvo commit rojo (`5731e43`), pero
  `5f25c14 test(...)` incluyó código de producción y `0191768 feat(...)` trajo
  código y tests juntos. Desde la adaptación al contrato (rama
  `fix/contrato-extraccion`) cada cambio de comportamiento sigue rojo → verde.
