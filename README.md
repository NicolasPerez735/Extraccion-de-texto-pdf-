# PDF Extraction (`extraccion-texto`)

Microservicio de extracción de texto de documentos PDF del proyecto
`microservicios-pdf`. Implementa la sección `extraccion-texto` del contrato
compartido `microservicios-pdf` (versión 1.4.0, en el repo `integracion`), y el endpoint
`POST /extract` del TP de carga y estrés (ver [TP de carga](#tp-de-carga-post-extract)).

## Responsabilidad

Hace:

- Recibir un PDF validado en Base64 junto con su nombre.
- Extraer el texto de todas las páginas con PyMuPDF (MuPDF, en C), en un pool de
  procesos con backpressure.
- Contar las páginas.
- Calcular el checksum SHA-256 del archivo.
- Propagar `X-Correlation-ID` y registrarlo en cada línea de log.
- TP de carga: convertir un PDF binario a Markdown con el mismo lector y el mismo pool
  (`POST /extract`).

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
- Desde la versión 1.2.0 el texto sale de PyMuPDF y no de pypdf: puede cortar líneas o
  separar palabras distinto (contrato 1.4.0). El checksum no cambia, porque se calcula
  sobre los bytes del archivo.

El header `X-Extraction-Time-Ms` informa cuánto tardó la extracción (esperar un worker
del pool, leer con PyMuPDF y calcular el checksum), separado del tiempo total de la
request.

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
| `PDF_CORRUPTED` | `422` | MuPDF no puede abrir el archivo o no encuentra ninguna página. |
| `DEPENDENCY_UNAVAILABLE` | `503` | Backpressure: cola llena o espera vencida. `details.reason` es `cola_llena` o `espera_agotada`, con `Retry-After: 1`. |
| `INTERNAL_ERROR` | `500` | Error no previsto. |

El `503` por backpressure es igual en `/extraer` y en `/extract` (el pool es uno solo).
El orquestador no lo reintenta: reintentar contra un servicio saturado lo satura más.

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
│   ├── extraction.py          # POST /extraer y POST /extract (adaptadores HTTP)
│   └── health.py              # GET /health
├── schemas/                   # request, response y error del contrato
├── services/
│   ├── extraction.py          # /extraer: Base64, texto plano y checksum
│   ├── conversion.py          # /extract: Markdown con un encabezado por página
│   ├── firma_pdf.py           # firma %PDF (la validan los dos casos de uso)
│   └── lector_paginas.py      # puerto LectorPaginas (Protocol)
├── models/
│   └── extraction.py          # PdfExtraction, DocumentoMarkdown (dataclasses)
└── core/
    ├── composition.py         # único lugar donde se arman el pool y los servicios
    ├── pymupdf_paginas.py     # leer_paginas: el texto de cada página con PyMuPDF
    ├── pool_lector.py         # PoolLectorPaginas: pool de procesos + backpressure
    ├── logs.py                # carga logging.json y agrega el correlation_id
    ├── config.py
    └── exceptions.py          # PdfInvalidError, PdfCorruptedError, ServiceOverloadedError
```

Dirección de dependencias: `controller → service → LectorPaginas (puerto)`, con el
pool y PyMuPDF en `core/`. Los services no importan FastAPI ni PyMuPDF, y reciben el
lector por constructor, sin valor por defecto.

**Dos endpoints, una sola extracción.** `/extraer` (contrato del orquestador: JSON con
Base64 → texto, checksum y páginas) y `/extract` (enunciado del TP: PDF binario →
Markdown) tienen consumidores y formatos distintos, así que siguen siendo dos rutas.
Lo que hacen por dentro es lo mismo y está una sola vez: `leer_paginas` devuelve el
texto de cada página y el mismo `PoolLectorPaginas` lo corre con el mismo backpressure.
Cada caso de uso solo arma su respuesta (texto unido por saltos de línea, o Markdown).

**Rendimiento.** Los dos endpoints son `async` y la lectura corre en un pool de procesos
(`EXTRACT_WORKERS`), fuera del event loop: `/health` sigue respondiendo bajo carga y,
como cada worker es un proceso, el GIL no limita. El paralelismo entre máquinas se
obtiene con réplicas detrás de Traefik.

## Logs (12-Factor XI)

Van a `stdout`, sin archivos. La configuración está en [`logging.json`](logging.json),
en la raíz del repo (formato `dictConfig`), y el nivel sale de `LOG_LEVEL`. Cada línea
lleva fecha, nivel, logger y `correlation_id` (`-` fuera de una request):

```text
INFO extraccion_texto correlation_id=- servicio iniciado
INFO app.services.extraction correlation_id=en-curso texto extraido paginas=1500 tamano_bytes=354327 caracteres=5526148 checksum=367aea83...
INFO extraccion_texto correlation_id=en-curso method=POST path=/extraer status=200 duracion_ms=17833.1
WARNING extraccion_texto correlation_id=demo-2 code=PDF_INVALID status=422 message=El archivo no es un PDF válido.
WARNING extraccion_texto correlation_id=demo-3 code=DEPENDENCY_UNAVAILABLE status=503 message=El servicio está saturado, reintentar en un momento. reason=cola_llena
```

| Nivel | Qué registra este servicio |
| --- | --- |
| `INFO` | Cada request (`method`, `path`, `status`, `duracion_ms`), el texto extraído (`paginas`, `tamano_bytes`, `caracteres`, `checksum`), inicio y apagado. |
| `WARNING` | Rechazos del contrato (`PDF_INVALID`, `PDF_CORRUPTED`, `VALIDATION_ERROR`) con su `code`, y el `503` por saturación con `reason=cola_llena` o `reason=espera_agotada`. |
| `ERROR` | Error no previsto (`INTERNAL_ERROR`), con traceback. |

**No se registran** el Base64, el texto extraído ni el nombre del archivo (puede tener
datos personales): el documento se identifica por su `checksum`. Hay un test que lo
verifica. El `correlation_id` viaja en un `ContextVar` y lo agrega el formato. Los
avisos que MuPDF escribe a `stderr` están desactivados (no llevan `correlation_id`; el
error se registra al responder `PDF_CORRUPTED`), y el access log de uvicorn está
desactivado porque lo registra la app.

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
| `EXTRACT_WORKERS` | `1` | Procesos que leen PDFs en cada réplica. |
| `EXTRACT_MAX_QUEUE` | `100` | Requests que pueden esperar un worker; más → `503`. |
| `EXTRACT_QUEUE_TIMEOUT_SECONDS` | `25` | Espera máxima por un worker; más → `503`. |
| `PUERTO` | `8080` | Solo `docker-compose.yml`: puerto del host donde publica el proxy. |

Las tres `EXTRACT_*` son opcionales y, desde el contrato 1.4.0, rigen para `/extraer` y
`/extract` (comparten el pool).

## Docker

```powershell
docker build -t extraccion-texto:1.2.1 .
docker run --rm -p 8000:8000 extraccion-texto:1.2.1
```

La versión del servicio es la de `pyproject.toml` (1.2.1): es la que muestra Swagger en
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

- **Unitarios de los servicios:** campos del contrato, checksum, texto unido de las
  páginas con contenido, Markdown por página, bytes que llegan al lector, Base64
  inválido, archivo vacío, contenido que no es PDF, Base64 con saltos de línea. Usan un
  lector de prueba inyectado.
- **Unitarios de `leer_paginas`:** varias páginas, página vacía, PDF truncado, PDF con
  el árbol de páginas roto (0 páginas) y ejecución en otro proceso, con PDFs reales
  generados en `tests/conftest.py`.
- **Unitarios del pool:** cola llena, espera vencida y atención del que espera.
- **Integración HTTP:** respuesta del contrato, cada código de error (incluido el `503`
  por backpressure en los dos endpoints), PDF sin texto, `X-Correlation-ID`,
  `X-Extraction-Time-Ms` y logs. El lector real corre en un pool de threads; el error no
  previsto y la saturación se prueban inyectando dobles (`app.dependency_overrides`).
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
- **Errores de MuPDF → `PDF_CORRUPTED`.** Se captura `RuntimeError` (la base de
  `FileDataError`) y también un documento de 0 páginas: con el árbol de páginas roto
  MuPDF abre el archivo sin fallar, donde pypdf sí fallaba. Una excepción de otro tipo
  responde `INTERNAL_ERROR`.
- **pypdf → PyMuPDF en `/extraer` (1.2.0).** PyMuPDF gasta entre 5 y 10 veces menos CPU
  (ver `docs/informe-carga.md`, sección 3.3). El texto puede diferir en saltos de línea
  o espacios; lo declara el contrato 1.4.0.
- **Licencia de PyMuPDF.** Es AGPL: sirve para un trabajo académico, pero un uso
  comercial cerrado necesitaría la licencia comercial de Artifex o volver a pypdf.
- **El primer request después de arrancar es más lento:** el pool crea su proceso
  worker recién cuando lo necesita.
- **Historial de TDD.** El primer ciclo tuvo commit rojo (`5731e43`), pero
  `5f25c14 test(...)` incluyó código de producción y `0191768 feat(...)` trajo
  código y tests juntos. Desde la adaptación al contrato (rama
  `fix/contrato-extraccion`) cada cambio de comportamiento sigue rojo → verde.
