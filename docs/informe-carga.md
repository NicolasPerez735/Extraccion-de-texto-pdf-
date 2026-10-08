# Informe técnico — TP de carga, estrés y optimización de `POST /extract`

Microservicio de extracción de texto y conversión de PDF a Markdown (repo
`Extraccion-de-texto-pdf-`, imagen `extraccion-texto:1.1.0`). Este informe explica la
arquitectura, el cuello de botella, el proceso de investigación y las métricas antes y
después de optimizar.

> **Estado:** las mediciones de la sección 5 se completan con Docker en la notebook
> (`tests/stress/medir.sh`). Lo que figura como *pendiente* todavía no se midió; los demás
> números salen de pruebas reales que se citan con su fecha.

## 1. Qué se entrega

| Requisito del TP | Dónde |
|---|---|
| `POST /extract`, PDF binario en el body → `200 {"content", "page_count"}` en Markdown | `app/controllers/extraction.py` |
| Imagen Docker y `docker compose up --build` de un solo comando | `Dockerfile`, `docker-compose.yml` |
| Hasta 5 réplicas detrás de un proxy inverso con balanceo | `docker-compose.yml`: 5 réplicas y Traefik |
| Límite explícito de CPU y memoria por contenedor | 1 CPU y 1 GB por réplica; 1 CPU y 512 MB el proxy |
| Script k6 (spike) y script vegeta (carga fija) | `tests/stress/spike.js`, `tests/stress/run_vegeta.sh` |
| Carpeta de PDFs `tests/stress/pdfs` | ver 4.1 |

Formato del Markdown: un encabezado por página y su texto.

```markdown
## Página 1

Texto de la primera página

## Página 2

Texto de la segunda página
```

## 2. Arquitectura

```
k6 / vegeta ──► Traefik :8080 ──round robin──► extraccion ×5 (1 CPU, 1 GB c/u)
                                               │
                                               ├─ event loop (uvicorn + FastAPI)
                                               │    recibe, valida, encola o rechaza (503)
                                               └─ pool de procesos (EXTRACT_WORKERS)
                                                    PyMuPDF: PDF → Markdown
```

Capas (igual que el resto del servicio): el controller lee los bytes del body;
`ConversionService` valida la firma `%PDF` y delega en el puerto `MarkdownConverter`; el
adaptador `PoolMarkdownConverter` corre la conversión de PyMuPDF (`pdf_a_markdown`) en un
`ProcessPoolExecutor`. El controller no conoce PyMuPDF ni el pool; el service no importa
FastAPI.

### Decisiones de diseño

| Decisión | Por qué |
|---|---|
| **PyMuPDF** (MuPDF, en C) en lugar de pypdf | Mismo texto, entre 5 y 10 veces menos CPU (sección 3.3). La extracción es el cuello de botella. |
| **Pool de procesos** separado del runtime HTTP | La conversión usa CPU y no libera el GIL: en un thread bloquearía el event loop, que tiene que seguir aceptando, rechazando y respondiendo `/health`. Es el punto 4 de las pautas del TP. |
| **Body binario** (`application/pdf`) en lugar de multipart | Sin parseo de formularios ni dependencias extra (`python-multipart` se había quitado del proyecto por una vulnerabilidad). Un solo buffer en memoria. |
| **Backpressure**: cola acotada y espera máxima por réplica | Bajo saturación, una request que espera más que el timeout del cliente es trabajo perdido. Rechazar enseguida con `503` y `Retry-After` libera la CPU para las que sí van a llegar a tiempo (punto 2 de las pautas). |
| **5 réplicas con Traefik** | El reparto por request (round robin) usa las 5 por igual. Docker sin proxy reparte por conexión y deja réplicas ociosas (sección 3.2). |
| **1 worker por réplica** (`EXTRACT_WORKERS=1`) | Cada réplica tiene 1 CPU: más procesos de conversión compiten por la misma CPU. Se verifica en la sección 5. |
| Configuración por variables de entorno | 12-Factor III: `EXTRACT_WORKERS`, `EXTRACT_MAX_QUEUE`, `EXTRACT_QUEUE_TIMEOUT_SECONDS`, `LOG_LEVEL`, `PUERTO`. |

Respuestas de error, con el formato común del contrato `microservicios-pdf`:

| Caso | Respuesta |
|---|---|
| Body vacío o sin la firma `%PDF` | `422 PDF_INVALID` |
| MuPDF no puede abrirlo | `422 PDF_CORRUPTED` |
| Cola llena o espera vencida | `503 DEPENDENCY_UNAVAILABLE`, `details.reason` = `cola_llena` o `espera_agotada`, header `Retry-After: 1` |

## 3. Proceso de investigación

Lo que se fue midiendo durante el proyecto, en orden, y qué decisión salió de cada paso.

### 3.1 Línea base: el monolito y la primera versión del microservicio

- **Monolito** (PDFs de 10 páginas, 30 s): 1 VU → extracción 89 ms, 8,4 PDF/s; 5 VUs →
  extracción 92 ms pero la subida completa 385 ms, 9,7 PDF/s. La extracción no se hacía más
  lenta; las requests **esperaban en cola**. Diagnóstico: pypdf es sincrónico y usa CPU, y
  en un proceso de Python el GIL deja convertir un PDF a la vez. Techo: ~11 PDF/s por
  proceso.
- **Microservicio con pypdf, 1 réplica** (integración, 2026-10-07): techo de ~8,3 PDF/s. Se
  confirmó que el límite es un proceso, no el código HTTP.

### 3.2 Escalar con réplicas: el reparto importa

- **3 réplicas** sin proxy: ~41 PDF/s con 5 VUs, 120 ms promedio. Escalar horizontalmente
  funciona porque cada réplica es un proceso con su propio GIL.
- Con pocos clientes, **una réplica quedaba sin trabajo**: el DNS de Docker reparte por
  *conexión* y el cliente HTTP reutiliza conexiones (keep-alive). Con 1 VU las requests se
  repartían 120/0/0.
- Con **Traefik balanceando por request**: reparto 52/53/52 con 1 VU; con 5 VUs, 37,4 PDF/s
  y 133 ms contra 16,7 PDF/s y 297 ms sin él. Por eso el TP usa Traefik delante de las 5
  réplicas.
- *Circuit breaker* de Traefik: mismos tiempos con y sin él; con una réplica caída de tres
  no llega a activarse. Lo que sí ayudó fue un `dialTimeout` de 1 s para no esperar a una
  réplica recién detenida (máximo 11,2 s → 2,2 s).

### 3.3 Cambiar la librería: el cuello de botella es la CPU de la extracción

Con las réplicas al máximo que permite el TP (5), lo que queda es gastar menos CPU por PDF.
Se compararon pypdf y PyMuPDF sobre los 4 PDFs de prueba, en un solo proceso, mediana de 7
corridas (PC de desarrollo, Python 3.14; 2026-10-07). Las dos librerías extraen **exactamente
el mismo texto** (misma cantidad de caracteres):

| PDF | Páginas | pypdf | PyMuPDF | Mejora |
|---|---|---|---|---|
| `01-liviano.pdf` (4 KB) | 2 | 5,6 ms | 1,9 ms | ×2,9 |
| `02-texto-80-paginas.pdf` (0,1 MB) | 80 | 511,1 ms | 89,4 ms | ×5,7 |
| `03-capas-30-paginas.pdf` (0,5 MB, 300 figuras vectoriales por página) | 30 | 507,8 ms | 49,5 ms | ×10,3 |
| `04-imagenes-9mb.pdf` (9 MB, 3 imágenes) | 12 | 29,4 ms | 22,2 ms | ×1,3 |

Conclusión: el costo no depende del tamaño en bytes sino de cuánto contenido hay que
recorrer (texto y operadores gráficos). En los PDFs con mucho texto o con capas, PyMuPDF
gasta entre 5 y 10 veces menos CPU. Otra prueba anterior descartó cambiar de versión de
Python: pypdf con 3.12 fue ~8 % más lento que con 3.11, por eso la imagen queda en
`python:3.11-slim`.

### 3.4 Separar HTTP de la extracción y controlar la congestión

- El endpoint anterior (`/extraer`) corría pypdf en el *threadpool* de FastAPI: no bloquea
  el event loop, pero los threads compiten por el GIL. `/extract` usa un **pool de
  procesos**: el event loop queda libre para aceptar, rechazar y responder `/health`
  mientras la CPU convierte.
- **Backpressure** probado sin Docker (2026-10-07, 1 worker, cola 2): 40 requests
  simultáneas → 8 atendidas (`200`, p50 372 ms) y 32 rechazadas con `503 cola_llena` en
  322 ms como máximo, sin que ninguna esperara hasta un timeout.
- Arranque en frío: la primera request de cada réplica tarda ~1 s más (crea el proceso
  worker y carga MuPDF). En una prueba de 40 s con 5 réplicas son 5 requests; no se
  precalienta.

### 3.5 Modelo cerrado (k6) contra modelo abierto (vegeta)

- **k6 spike** (cerrado): 100 VUs, cada uno espera su respuesta antes de mandar la
  siguiente. La concurrencia nunca pasa de 100 (unas 20 por réplica), así que la cola por
  defecto (`EXTRACT_MAX_QUEUE=20`) alcanza para **no rechazar**: el objetivo es throughput
  con 0 % de errores.
- **vegeta** (abierto): 50 req/s pase lo que pase. Si la capacidad es menor que 50/s, la
  cola crece sin límite y las requests vencen a los 30 s (le pasó a la referencia del
  profesor: 33 % de timeouts). Si la capacidad supera 50/s, no hay cola. La espera máxima
  (`EXTRACT_QUEUE_TIMEOUT_SECONDS=10`) corta antes del timeout del cliente.

## 4. Cómo reproducirlo

### 4.1 PDFs de prueba

El TP pide la carpeta oficial `tests/stress/pdfs`. Mientras no la tengamos,
`tests/stress/generar_pdfs.py` genera 4 PDFs fijos (semilla constante) de tamaño y densidad
variable: 2 páginas livianas, 80 páginas de texto, 30 páginas con capas vectoriales y
9 MB con imágenes. **Si se copia la carpeta oficial en `tests/stress/pdfs/`, vegeta la usa
tal cual y k6 recibe los nombres con `-e PDFS=a.pdf,b.pdf,...`.**

```bash
uv run tests/stress/generar_pdfs.py
```

### 4.2 Levantar y medir

```bash
docker compose up --build -d                       # 5 réplicas + Traefik en :8080
./tests/stress/medir.sh 5-replicas-backpressure    # k6 spike + vegeta 50/s
docker compose down
```

Cada prueba por separado:

```bash
k6 run tests/stress/spike.js
./tests/stress/run_vegeta.sh
```

Configuraciones de la comparación (sección 5):

| Etiqueta | Cómo se levanta |
|---|---|
| `1-replica-sin-backpressure` | `EXTRACT_MAX_QUEUE=100000 EXTRACT_QUEUE_TIMEOUT_SECONDS=3600 docker compose up --build -d --scale extraccion=1` |
| `5-replicas-sin-backpressure` | `EXTRACT_MAX_QUEUE=100000 EXTRACT_QUEUE_TIMEOUT_SECONDS=3600 docker compose up -d` |
| `5-replicas-backpressure` | `docker compose up -d` (valores por defecto) |

## 5. Resultados

Máquina de medición: *pendiente (notebook: CPU, núcleos, RAM, Docker Desktop)*. Todas las
corridas con la notebook enchufada y con los mismos 4 PDFs.

### 5.1 k6 spike (100 VUs, 40 s)

| Configuración | Requests | req/s | Errores | p50 | p90 | p95 | Máx |
|---|---|---|---|---|---|---|---|
| Referencia del profesor | 1.037 | 25,35 | 0,00 % | 1,88 s | 7,83 s | 8,80 s | 13,94 s |
| 1 réplica, sin backpressure | *pendiente* | | | | | | |
| 5 réplicas, sin backpressure | *pendiente* | | | | | | |
| 5 réplicas, con backpressure | *pendiente* | | | | | | |

### 5.2 vegeta (50 req/s, 30 s, timeout 30 s)

| Configuración | Throughput efectivo | Éxito | Timeouts (código 0) | 503 | p50 |
|---|---|---|---|---|---|
| Referencia del profesor | 16,65 req/s | 998 / 1.500 (66,53 %) | 501 (33,40 %) | — | 14,89 s |
| 1 réplica, sin backpressure | *pendiente* | | | | |
| 5 réplicas, sin backpressure | *pendiente* | | | | |
| 5 réplicas, con backpressure | *pendiente* | | | | |

### 5.3 Análisis

*Pendiente, con los números de 5.1 y 5.2.* Preguntas que tiene que responder: cuánto aporta
cada réplica (¿escala lineal hasta 5?), si el backpressure mejora la tasa de éxito de vegeta
o solo cambia timeouts por `503`, y si la latencia total crece con la concurrencia mientras
`X-Extraction-Time-Ms` se mantiene (eso indica cola, no extracción lenta).

## 6. Limitaciones y deuda declarada

- Los PDFs de prueba son generados; con la carpeta oficial los tiempos absolutos cambian.
- El tiempo de `X-Extraction-Time-Ms` en `/extract` incluye la espera en la cola de la
  réplica, no solo la conversión.
- El Markdown es simple (encabezado por página y texto plano): no detecta títulos, listas
  ni tablas. Una conversión más fiel (por ejemplo `pymupdf4llm`) cuesta bastante más CPU.
- `/extraer` (el endpoint del orquestador) sigue con pypdf, como fija el contrato; pasarlo a
  PyMuPDF sería una versión nueva del contrato.
