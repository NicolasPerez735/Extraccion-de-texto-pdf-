# Metodología UTN — Desarrollo de Software

Este archivo fija cómo se construye código en este proyecto. No es una guía de estilo
opcional: cada punto acá corresponde a un criterio de evaluación real de la cátedra, y el
proyecto se corrige leyendo el código y el historial de git.

## Antes de escribir código

Preguntar (o inferir del contexto) tres cosas, en este orden:

1. **¿Qué capa toca este cambio?** Presentación, negocio o datos. Si toca más de una, el
   cambio se parte en pasos, uno por capa.
2. **¿Existe ya un test que falle para esto?** Si no, ese es el primer paso.
3. **¿Esto se pidió?** Si nadie lo pidió, no se escribe. YAGNI se evalúa buscando código
   muerto, y el corrector lo encuentra con `grep`.

Si el pedido es ambiguo respecto de la capa o del alcance, preguntar antes de codificar.
Escribir de más en el lugar equivocado cuesta más que una pregunta.

## Stack fijo

| Elemento | Herramienta | Nota |
|---|---|---|
| Lenguaje | Python 3.10+ | |
| Framework | FastAPI | |
| Paquetes | **uv** | Nunca `pip install` ni `requirements.txt` |
| Base de datos | MongoDB (no relacional) | vía Motor (async) |
| Tests | pytest | |
| Gestión | GitHub Project | Issues vinculadas a commits |

Al agregar una dependencia: `uv add <paquete>`, y verificar que `uv.lock` quede versionado.

## Arquitectura: tres capas + Repository

La estructura de carpetas es por **roles tecnológicos**, no por features:

```
app/
├── main.py           # ensamblado: routers, middleware, handler de excepciones
├── controllers/      # CAPA 1 — HTTP: rutas, status codes, HTTPException
├── schemas/          # CAPA 1 — DTOs Pydantic (contrato de la API)
├── services/         # CAPA 2 — reglas de negocio
├── models/           # CAPA 2 — entidades del dominio (Python puro)
└── core/             # CAPA 3 + transversal
    ├── repository.py        # puerto abstracto (ABC)
    ├── <x>_repository.py    # adaptadores concretos
    ├── database.py          # conexión
    ├── config.py            # settings (transversal)
    └── exceptions.py        # excepciones de dominio (transversal)
```

**Reglas de dependencia, en orden de importancia:**

- El flujo va `controller → service → repository → BD`. Nunca al revés, nunca salteando.
- El controller **no** importa Motor, pymongo ni el repositorio concreto.
- El service **no** importa `fastapi`. Si necesita recibir un archivo, recibe `bytes` y
  metadatos, no `UploadFile`. Un service que importa FastAPI ya no se puede reutilizar ni
  testear fuera de HTTP.
- Los modelos del dominio son Python plano: sin Pydantic, sin decoradores de ORM.
- Los schemas Pydantic viven en capa 1 y son distintos de las entidades. Esa duplicación
  aparente es intencional: desacopla el contrato público del modelo interno.

**Patrón Repository, siempre:**

```python
class Repository(ABC, Generic[T]):
    @abstractmethod
    async def add(self, entity: T) -> T: ...
    # solo métodos que alguien llama de verdad
```

Con dos implementaciones mínimas: la real (Mongo) y una en memoria para tests. El service
recibe la abstracción por constructor:

```python
class BaseService(Generic[T]):
    def __init__(self, repository: Repository[T]) -> None:  # obligatorio, sin default
        self._repository = repository
```

Sin valor por defecto. Un default en memoria hace que un olvido de cableado produzca
almacenamiento no persistente en silencio.

## TDD: el orden importa más que el resultado

La cátedra evalúa el **proceso**, y el proceso se lee en el historial de git. Una suite
excelente escrita después de la implementación no cuenta como TDD.

**Ciclo obligatorio, un commit por fase:**

```
1. ROJO      test(x): test de <comportamiento>          ← el test falla
2. VERDE     feat(x): implementar <comportamiento>      ← lo mínimo para que pase
3. REFACTOR  refactor(x): <mejora>                      ← solo si hace falta
```

El commit rojo es la evidencia. Si no existe, no hay forma de demostrar test-first.

**Al implementar una feature nueva:** proponer primero el test, esperar confirmación, y
recién después escribir la implementación. No adelantar código "porque ya sé cómo va".

**Una slice vertical por ciclo.** No escribir los diez tests y después las diez
implementaciones — eso es slicing horizontal invertido y se detecta igual.

**Los tests unitarios deben ser:**

- **Rápidos** — fracciones de segundo. Sin red, sin BD real.
- **Atómicos** — un comportamiento por test.
- **Inocuos** — no alteran estado externo.
- **Independientes** — el orden de ejecución no cambia el resultado.

**Herméticos:** la suite corre sin `.env`, sin Mongo levantado y sin configuración manual.
Si `pytest` falla en una copia limpia del repo, los tests no son independientes. Proveer los
settings desde `conftest.py` (`monkeypatch.setenv`) y sustituir el repositorio real con
`app.dependency_overrides`.

**Sin mocks de internals.** El doble de test es el `InMemoryRepository`, inyectado por el
mismo mecanismo que usa producción. Eso es inversión de dependencias real; parchear atributos
privados acopla el test a la implementación.

**Seams declarados.** Documentar en el README qué se testea (HTTP + servicio) y qué queda
fuera a propósito (el adaptador de BD, si es delgado). Una decisión declarada es defendible;
un hueco sin explicar parece olvido.

## Principios, con su verificación

Cada principio se chequea con una pregunta concreta, no con buena intención.

**DRY** — ¿Hay lógica escrita dos veces? Centralizar lo repetido en una clase base o un
helper. Antes de cerrar, `grep` de las firmas de método por archivo: definiciones duplicadas
son el hallazgo más fácil de encontrar para un corrector.

**KISS** — ¿La solución más simple resuelve el caso? Nada de recursividad, `try/except` o
capas de indirección donde alcanza una línea. Clases sin métodos usadas como namespace son
complejidad estructural sin beneficio: usar variables de módulo.

**YAGNI** — ¿Alguien pidió esto? Antes de entregar, buscar símbolos sin llamadores:
excepciones que nunca se lanzan, decoradores que nunca se aplican, métodos de la interfaz que
nadie invoca. Todo eso se borra.

**SRP** — ¿La clase tiene una sola razón para cambiar? Un service que valida, parsea y
persiste tiene tres. La validación de formato pertenece al service, no al controller: el
controller no conoce reglas de dominio.

**OCP** — ¿Se puede agregar un caso nuevo sin editar código existente? Se logra con clases
abstractas y polimorfismo. Un diccionario central de mapeo que hay que editar en cada
agregado es una fisura conocida: aceptable si se prefiere DRY, pero hay que poder explicarlo.

**LSP** — ¿Las implementaciones son intercambiables de verdad? Se demuestra corriendo la
misma suite con dos repositorios distintos. Ninguna subclase endurece precondiciones ni
devuelve algo que rompa el contrato del padre.

**ISP** — ¿Alguna implementación tiene métodos con `pass` o `NotImplementedError`? Si sí, la
interfaz es demasiado grande. Ese es el test práctico, no el conteo de métodos.

**DIP** — ¿El type hint apunta a la abstracción? `repository: Repository[T]`, nunca
`MongoRepository`. El cableado concreto vive en un solo lugar (`main.py` o un módulo de
composición), no repartido en los controllers.

**Ley de Demeter** — Contar los puntos. `service.get_by_id(x)` está bien;
`service._repository.collection.find_one(...)` es una violación.

**Composición sobre herencia** — Heredar lo que define *qué es* algo; componer lo que define
*qué usa*. `PdfService(BaseService)` es correcto. `BaseService(MongoRepository)` no lo sería.

## 12-Factor App

Los tres factores evaluados:

- **Código base** — un repo, una app. Sin `.pyc`, sin `.venv`, sin `.env` versionados.
- **Dependencias** — declaradas en `pyproject.toml` y fijadas en `uv.lock`. Ambos en git.
- **Configuración** — todo por variables de entorno con `pydantic-settings`. El `.env` va en
  `.gitignore` y se versiona un **`.env.example`** con todas las claves y sin valores reales.
  Sin ese archivo, nadie puede levantar el proyecto.

Nunca hardcodear URLs de conexión, puertos ni credenciales.

## Docker

El `docker-compose.yml` debe permitir levantar el proyecto completo desde un clon limpio.

**Persistencia:** todo servicio con estado lleva volumen nombrado.

```yaml
services:
  mongodb:
    image: mongo:7.0
    volumes:
      - mongo_data:/data/db

volumes:
  mongo_data:
```

Sin volumen, los datos viven en la capa escribible del contenedor y desaparecen con
`docker rm`.

**Si la base corre en un stack aparte** (compartida entre varios servicios), documentarlo en
el README: dónde está el compose, qué red externa usa, cómo crearla, qué variables necesita.
Una decisión de infraestructura sin documentar es indistinguible de un olvido.

**Dockerfile:** usuario sin privilegios antes del `CMD`.

```dockerfile
RUN useradd --create-home appuser
USER appuser
```

Correr como root viola el principio de mínimo privilegio: si el contenedor se compromete, el
atacante ya tiene root adentro.

## Conventional Commits

`tipo(scope): descripción en imperativo`

| Tipo | Cuándo |
|---|---|
| `feat` | funcionalidad nueva |
| `fix` | corrección de un bug |
| `test` | tests (incluye el commit rojo) |
| `refactor` | mejora interna sin cambio de comportamiento |
| `docs` | documentación |
| `chore` | mantenimiento, dependencias |
| `perf` | rendimiento |

Un commit, un propósito. **El commit de tests no toca código de producción** — si lo toca,
demuestra que los tests se escribieron contra una implementación que ya existía.

`BREAKING CHANGE:` en el cuerpo cuando haya incompatibilidad hacia atrás.

## Verificación antes de entregar

```bash
uv run pytest tests/ -v                    # suite en verde
mv .env .env.bak && uv run pytest ; mv .env.bak .env   # hermética
uv run ruff check app/ tests/
uv run black --check app/ tests/
uv run pytest --cov=app --cov-report=term-missing
git ls-files | grep -E "\.(env|pyc)$"      # debe salir vacío
```

Y una revisión manual de cinco puntos:

1. ¿Hay métodos o lógica duplicada? (`grep` de firmas por archivo)
2. ¿Hay símbolos sin llamadores? (excepciones, decoradores, métodos de interfaz)
3. ¿Algún import de `fastapi` en `services/`? ¿Algún import de Motor en `controllers/`?
4. ¿El README alcanza para que alguien clone y levante el proyecto?
5. ¿El historial muestra commits rojos antes de los verdes?

## Deuda técnica: declararla, no esconderla

Cuando algo no se puede arreglar a tiempo o se decide no arreglarlo, anotarlo en el README
con el motivo. Un trade-off explicado suma; el mismo hueco sin explicación se lee como
descuido.

Ejemplo: *"El adaptador Mongo queda fuera de los tests automatizados por ser un wrapper
delgado sobre Motor; se cubriría con un test de integración contra un contenedor."*

Lo mismo aplica al hablar del proyecto: reconocer con precisión qué se hizo y qué no vale más
que sostener que se cumplió algo que el código contradice.

## Flujo de git

Cada cambio va en una rama propia, nunca directo a `main`:

    git switch -c fix/<descripcion-corta>

**Un commit, un propósito.** Antes de commitear, mostrar el diff y proponer el
mensaje; esperar confirmación. Si un cambio toca varias cosas sin relación entre
sí, se parte en commits separados aunque hayan salido en la misma sesión.

**Preparar los archivos de forma explícita.** Nunca `git add .` ni `git add -A`:
listar los archivos que corresponden a ese commit y solo esos. Un `git add .`
arrastra archivos sin relación y produce commits con carga de más.

    git add app/core/mongo_repository.py
    git commit -m "refactor(repository): eliminar métodos duplicados"
    git push -u origin fix/<descripcion-corta>

**Push después de cada commit**, no al final de todo. Si la rama es nueva, el
primer push lleva `-u origin <rama>`; los siguientes son `git push` a secas.

**Antes de cada commit, la suite tiene que estar verde.** Si un cambio rompe
tests, se arregla antes de commitear — no se commitea roto "para no perder el
trabajo".

**Los mensajes de commit no llevan metadatos de herramientas** — nada de
`Co-Authored-By` de asistentes ni enlaces de sesión. Solo título y cuerpo
explicativo.

**Nunca** `git push --force`, `git reset --hard` ni reescritura de historial sin
pedirlo explícitamente. El historial es evidencia evaluada.
