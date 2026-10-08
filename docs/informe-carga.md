# Informe técnico — TP de carga, estrés y optimización de `POST /extract`

Microservicio de extracción de texto y conversión de PDF a Markdown (repo
`Extraccion-de-texto-pdf-`, imagen `extraccion-texto:1.1.1`). Este informe explica la
arquitectura, el cuello de botella, el proceso de investigación y las métricas antes y
después de optimizar.

> **Estado:** medido con Docker el 2026-10-07 (sección 5). Todos los números salen de
> pruebas reales que se citan con su fecha; los resultados crudos de k6 y vegeta se
> regeneran con `tests/stress/medir.sh`.

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
  siguiente. La concurrencia nunca pasa de 100 (unas 20 por réplica en promedio), así que
  con una cola holgada no se rechaza nada: el objetivo es throughput con 0 % de errores.
  Con la cola original de 20 sí se rechazaba (sección 5.3): el reparto no es parejo porque
  los PDFs cuestan distinto.
- **vegeta** (abierto): 50 req/s pase lo que pase. Si la capacidad es menor que 50/s, la
  cola crece sin límite y las requests vencen a los 30 s (le pasó a la referencia del
  profesor: 33 % de timeouts). Si la capacidad supera 50/s, no hay cola. La espera máxima
  (`EXTRACT_QUEUE_TIMEOUT_SECONDS=25`) corta antes del timeout del cliente (30 s).

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
| `5-replicas-backpressure` | `EXTRACT_MAX_QUEUE=20 EXTRACT_QUEUE_TIMEOUT_SECONDS=10 docker compose up -d` (valores por defecto hasta la 1.1.0) |
| `final-1.1.1` | `docker compose up --build -d` (valores por defecto de la 1.1.1: cola 100, espera 25 s) |

`medir.sh` apunta a `http://127.0.0.1:8080`: en Windows, `localhost` resuelve primero a
`::1` y el reenvío de puertos IPv6 de Docker Desktop quedó colgado después de un
`down`/`up` (le pasó a la segunda configuración).

## 5. Resultados

Medido el 2026-10-07 en la notebook del grupo: Intel Core i5-13420H (8 núcleos, 12 hilos),
15,7 GB de RAM, Windows 11 Home, Docker Desktop 29.6.2 con 12 CPUs y 7,6 GiB asignados,
enchufada. Cada réplica limitada a 1 CPU y 1 GB, el proxy a 1 CPU y 512 MB. Los 4 PDFs
generados (sección 4.1), `EXTRACT_WORKERS=1`. Entre una configuración y otra,
`docker compose down`.

Nombres de las configuraciones:

| Config. | Réplicas | Cola (`EXTRACT_MAX_QUEUE`) | Espera máx. (`EXTRACT_QUEUE_TIMEOUT_SECONDS`) |
|---|---|---|---|
| **A** antes | 1 | sin límite | sin límite |
| **B** | 5 | sin límite | sin límite |
| **C** | 5 | 20 | 10 s (valores de la 1.1.0) |
| **D** | 5 | 40 | 10 s |
| **E / final** | 5 | **100** | **25 s** (valores de la 1.1.1) |

### 5.1 k6 spike (100 VUs, 40 s)

| Configuración | Requests | req/s | Errores | p50 | p90 | p95 | Máx |
|---|---|---|---|---|---|---|---|
| Referencia del profesor | 1.037 | 25,35 | 0,00 % | 1,88 s | 7,83 s | 8,80 s | 13,94 s |
| A. 1 réplica, sin backpressure | 373 | 8,21 | 0,00 % | 10,93 s | 13,26 s | 13,55 s | 13,95 s |
| B. 5 réplicas, sin backpressure | 1.387 | 34,36 | 0,00 % | 2,22 s | 3,99 s | 4,95 s | 7,71 s |
| C. 5 réplicas, backpressure 20 / 10 s | 1.392 | 34,66 | **3,59 %** (50 × `503`) | 1,89 s | 4,82 s | 6,03 s | 8,75 s |
| D. 5 réplicas, backpressure 40 / 10 s | 1.383 | 34,55 | 0,00 % | 1,93 s | 4,23 s | 5,13 s | 7,79 s |
| E. 5 réplicas, backpressure 100 / 25 s | 1.397 | 34,9 \* | 0,00 % | 2,00 s | 4,06 s | 5,29 s | 7,44 s |
| **Final 1.1.1** (`docker compose up --build`) | **1.352** | **33,76** | **0,00 %** | **1,90 s** | **5,32 s** | **6,47 s** | **8,31 s** |

\* E tuvo 1 iteración interrumpida (ver 5.3, "requests perdidas"): k6 informó 21,88 req/s
porque esperó 30 s más a esa request. 34,9 es la cantidad de requests completadas en los
40 s del escenario, comparable con las demás filas.

### 5.2 vegeta (50 req/s, 30 s, timeout 30 s)

| Configuración | Throughput efectivo | Éxito | Timeouts (código 0) | 503 | p50 | p95 |
|---|---|---|---|---|---|---|
| Referencia del profesor | 16,65 req/s | 998 / 1.500 (66,53 %) | 501 (33,40 %) | — | 14,89 s | — |
| A. 1 réplica, sin backpressure | 2,72 req/s | 159 / 1.500 (10,60 %) | 31 | — (además 1.065 × `502` y 245 × `404`) | 7,24 s | 19,84 s |
| B. 5 réplicas, sin backpressure | 33,40 req/s | 1.494 / 1.500 (99,60 %) | 6 | — | 8,54 s | 19,03 s |
| C. 5 réplicas, backpressure 20 / 10 s | 30,49 req/s | 1.165 / 1.500 (77,67 %) | 5 | 330 | 2,95 s | 13,08 s |
| D. 5 réplicas, backpressure 40 / 10 s | 31,08 req/s | 1.218 / 1.500 (81,20 %) | 5 | 277 | 4,97 s | 13,99 s |
| E. 5 réplicas, backpressure 100 / 25 s | 32,55 req/s | 1.482 / 1.500 (98,80 %) | 4 | 14 | 8,58 s | 19,67 s |
| **Final 1.1.1** | **33,24 req/s** | **1.464 / 1.500 (97,60 %)** | **5** | **31** | **7,58 s** | **19,21 s** |

E se repitió y dio lo mismo (98,87 % de éxito, 14 × `503`, p50 9,28 s).

### 5.3 Análisis

**Contra el profesor, con la configuración final (1.1.1):**

| Métrica | Profesor | Nosotros | |
|---|---|---|---|
| k6 req/s | 25,35 | **33,76** | +33 % |
| k6 errores | 0,00 % | **0,00 %** | igual |
| k6 p95 | 8,80 s | **6,47 s** | −26 % |
| vegeta éxito | 66,53 % | **97,60 %** | +31 puntos |
| vegeta p50 | 14,89 s | **7,58 s** | −49 % |
| vegeta throughput efectivo | 16,65 req/s | **33,24 req/s** | ×2 |

La comparación es entre máquinas distintas: la referencia se midió en la del profesor. Lo
que no depende de la máquina es la forma de las curvas: con nuestra configuración ninguna
request de k6 falla y vegeta casi no tiene timeouts.

**Cuánto aporta cada réplica.** De 1 a 5 réplicas el throughput de k6 pasa de 8,2 a
34,4 req/s (×4,2 con ×5 réplicas). No escala del todo lineal porque la máquina tiene 8
núcleos físicos para 5 réplicas, el proxy, Docker Desktop y los propios k6 y vegeta. Con
1 réplica, la latencia de k6 es casi toda cola: p50 de 10,9 s cuando convertir un PDF tarda
entre 10 y 180 ms.

**Antes (A): sin backpressure, una réplica se cae.** Con vegeta a 50 req/s y capacidad de
~8 req/s, la cola crece sin límite y cada request retiene su PDF en memoria (hasta 9 MB).
La réplica superó su 1 GB: Docker registró un evento `oom`, el contenedor se reinició y
mientras tanto Traefik respondió `502` (1.065) y `404` (245, sin réplicas sanas). Solo el
10,6 % tuvo éxito. Es exactamente el caso que el backpressure tiene que evitar.

**El backpressure inicial era demasiado agresivo (C).** Con 5 réplicas la capacidad es de
~34 req/s. Contra 50 req/s durante 30 s se juntan unas 480 requests de más, que esperan
como mucho ~20 s: **menos que los 30 s del cliente de vegeta**. La espera máxima de 10 s
rechazó con `503` requests que habrían llegado a tiempo: 77,7 % de éxito contra 99,6 % sin
backpressure (B). Y en k6 la cola de 20 rechazó el 3,6 %, porque 100 VUs no se reparten
exactamente 20 por réplica (los PDFs cuestan distinto).

**Ajuste (antes → después):**

1. **D:** cola de 20 a 40. k6 pasó a 0 % de errores; vegeta apenas mejoró (81,2 %), porque
   el límite que mandaba era la espera de 10 s.
2. **E:** cola de 100 y espera de 25 s (por debajo de los 30 s del cliente menos el tiempo
   de conversión). k6 sigue en 0 %; vegeta sube a 98,8 % con solo 14 rechazos. Se adoptó
   como valor por defecto en la imagen **1.1.1** (`docker-compose.yml`, `.env.example` y
   `app/core/config.py`, con su test).

El costo del ajuste es latencia en vegeta: p50 de 2,9 s (C) a 7,6 s (final), porque ahora
se atiende lo que antes se rechazaba. Es lo correcto para este escenario: una request
rechazada a los 10 s es trabajo perdido para el cliente, y una atendida a los 20 s llega
antes de su timeout. La protección se mantiene: si la sobrecarga dura más que el timeout
del cliente, la espera de 25 s y la cola de 100 cortan con `503` rápido antes de que la
memoria se agote (el caso A).

**Backpressure contra sin backpressure con 5 réplicas (B contra final).** A 50 req/s
durante 30 s los dos andan bien (99,6 % y 97,6 %): la ráfaga no alcanza para llenar 1 GB por
réplica. La diferencia aparece con más carga o más duración: sin límite, la cola y la memoria
crecen sin techo (lo que tumbó a A); con límite, el servicio sigue sano y avisa con `503` y
`Retry-After`.

**Latencia total contra extracción.** Sin carga, convertir cada PDF tarda entre 10 y 180 ms
(`X-Extraction-Time-Ms`). Bajo carga la latencia sube a segundos: es espera en cola, no
conversión más lenta. Por eso escalar con réplicas (A → B) es lo que más mueve los números,
y el backpressure decide qué hacer con la cola.

**Corridas descartadas, con su motivo.** La primera corrida de B dio 20,09 req/s y 83,6 %
en vegeta, con conexiones rechazadas por `127.0.0.1:8080` y 1 iteración de k6 interrumpida;
se hizo justo después de que el reenvío de puertos de Docker Desktop se colgara. Repetida en
limpio dio los valores de la tabla. Los resultados crudos de las dos están en
`tests/stress/resultados/` (no se versiona).

**Requests perdidas antes del servicio.** En 3 de las 8 corridas una o dos requests de k6
quedaron sin respuesta (iteraciones interrumpidas). En la repetición de E se contó: el
servidor registró 2.847 requests de `/extract`, y entre k6 y vegeta se mandaron 2.852. Las 5
que faltan son justo las 2 interrumpidas de k6 y los 3 timeouts de vegeta: **nunca llegaron
al servicio**. Se pierden en el reenvío de puertos de Docker Desktop en Windows (ver 6). No
cambian los errores (k6 no las cuenta como fallidas) pero bajan el req/s que informa k6,
porque espera 30 s más.

## 6. Limitaciones y deuda declarada

- Los PDFs de prueba son generados; con la carpeta oficial los tiempos absolutos cambian.
- **Docker Desktop en Windows pierde algunas conexiones bajo carga** (5 de 2.852 en una
  corrida; sección 5.3) y el reenvío de puertos IPv6 se colgó una vez después de un
  `down`/`up`. No es del servicio: esas requests no le llegan. En Linux, o midiendo desde un
  contenedor en la misma red, no debería pasar; no se pudo probar en esta entrega.
- Las mediciones son de una sola máquina y una corrida por configuración (dos en B y E):
  sirven para comparar configuraciones, no como valores absolutos.
- El tiempo de `X-Extraction-Time-Ms` en `/extract` incluye la espera en la cola de la
  réplica, no solo la conversión.
- El Markdown es simple (encabezado por página y texto plano): no detecta títulos, listas
  ni tablas. Una conversión más fiel (por ejemplo `pymupdf4llm`) cuesta bastante más CPU.
- `/extraer` (el endpoint del orquestador) sigue con pypdf, como fija el contrato; pasarlo a
  PyMuPDF sería una versión nueva del contrato.
