# PDF Extraction (`extraccion-texto`)

Microservicio de extracción de texto de documentos PDF del proyecto
`microservicios-pdf`. Implementa la sección `extraccion-texto` del contrato
compartido `microservicios-pdf v1.0.0`.

## Responsabilidad

Hace:

- Recibir un PDF validado en Base64 junto con su nombre.
- Extraer el texto de todas las páginas con `pypdf`.
- Contar las páginas.
- Calcular el checksum SHA-256 del archivo.
- Propagar `X-Correlation-ID` y registrarlo en cada línea de log.

No hace:

- Persistir información ni usar MongoDB o Redis.
- Validar el tamaño máximo del archivo (lo hace `validacion-pdf`).
- OCR: un PDF escaneado devuelve texto vacío.

## Endpoints

| Método | Ruta | Descripción |
| --- | --- | --- |
| `POST` | `/extraer` | Extrae texto, páginas y checksum de un PDF en Base64. |
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

## Logs

Van a `stdout`, sin archivos, y cada línea incluye el `correlation_id`:

```text
2026-10-06 19:42:24,176 INFO extraccion_texto correlation_id=demo-1 method=POST path=/extraer status=200 duracion_ms=4.3
2026-10-06 19:42:24,180 WARNING extraccion_texto correlation_id=demo-2 code=PDF_INVALID status=422 message=El archivo no es un PDF válido.
```

Los avisos internos de pypdf se limitan a nivel `ERROR` porque no llevan
`correlation_id`, y el access log de uvicorn está desactivado en la imagen.

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
| `LOG_LEVEL` | `INFO` | Nivel de logging. |

El contrato no define variables para este servicio.

## Docker

```powershell
docker build -t extraccion-texto:1.0.0 .
docker run --rm -p 8000:8000 extraccion-texto:1.0.0
```

La imagen corre como `appuser` y tiene un `HEALTHCHECK` contra `GET /health`.

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

Queda fuera a propósito: la imagen Docker (se verifica con su healthcheck).

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
