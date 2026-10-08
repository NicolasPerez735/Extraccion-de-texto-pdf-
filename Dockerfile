# Base Debian 13 (python:3.11-slim): la uv:python3.11-bookworm-slim (Debian 12) traía
# vulnerabilidades Critical en openssl, gnutls, perl y glibc según Grype. Se queda en
# Python 3.11 porque pypdf extrae ~8 % más rápido que con 3.12 (medido con k6).
FROM python:3.11-slim


# setuptools y wheel vienen preinstalados en el Python de la imagen base (no en el venv
# de la app, que no los usa) y Grype marca dos vulnerabilidades High en lo que traen.
RUN python -m pip uninstall --yes --quiet setuptools wheel

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
# uv se monta solo durante este RUN (--mount=from=...) y no queda en la imagen final:
# Grype marcaba High en librerías de Rust compiladas dentro del binario (quinn-proto,
# rustls-webpki).
RUN --mount=from=ghcr.io/astral-sh/uv:0.11.15,source=/uv,target=/bin/uv \
    uv sync --frozen --no-dev --no-install-project

COPY logging.json ./
COPY app ./app
RUN --mount=from=ghcr.io/astral-sh/uv:0.11.15,source=/uv,target=/bin/uv \
    uv sync --frozen --no-dev

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD /app/.venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

# --no-access-log: el acceso lo registra la app con el correlation_id.
# Forma exec: uvicorn es el PID 1 y recibe el SIGTERM de docker stop. Con
# --timeout-graceful-shutdown deja de aceptar conexiones y espera hasta 30 s a que
# terminen las requests en curso antes de salir (contrato 1.2.0, 12-Factor IX).
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--timeout-graceful-shutdown", "30"]
