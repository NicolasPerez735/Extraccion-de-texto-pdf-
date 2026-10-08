import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.controllers.extraction import router as extraction_router
from app.controllers.health import router as health_router
from app.core.composition import crear_convertidor
from app.core.config import get_settings
from app.core.exceptions import DomainError, ServiceOverloadedError
from app.core.logs import configurar_logs, correlation_id_actual
from app.schemas.errors import ErrorDetail, ErrorResponse

# pypdf avisa por logging sin correlation_id: logging.json lo deja en ERROR; el error
# que importa ya se registra con su correlation_id al responder PDF_CORRUPTED.
configurar_logs(get_settings().log_level)
logger = logging.getLogger("extraccion_texto")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.convertidor = crear_convertidor(get_settings())
    logger.info("servicio iniciado")
    yield
    # uvicorn llega acá ante SIGTERM, después de cerrar el puerto y terminar las
    # requests en curso (12-Factor IX). Cierra el pool de workers de /extract.
    logger.info("apagado iniciado")
    app.state.convertidor.cerrar()
    logger.info("apagado completo")


app = FastAPI(
    title="PDF Extraction",
    version="1.1.2",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(extraction_router)


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict,
    exc_info: BaseException | None = None,
) -> JSONResponse:
    """Formato común de errores del contrato. El header se agrega acá porque el
    handler de Exception corre fuera del middleware de correlation ID."""
    correlation_id = request.state.correlation_id
    # ERROR solo para fallas no esperadas; un 503 por saturación es recuperable
    # (WARNING, contrato 1.2.0).
    logger.log(
        logging.ERROR if exc_info is not None else logging.WARNING,
        "code=%s status=%s message=%s",
        code,
        status_code,
        message,
        exc_info=exc_info,
    )
    body = ErrorResponse(
        error=ErrorDetail(
            code=code,
            message=message,
            details=details,
            correlation_id=correlation_id,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(),
        headers={"X-Correlation-ID": correlation_id},
    )


@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, error: DomainError) -> JSONResponse:
    # Todos los errores de dominio del contrato para este servicio
    # (PDF_INVALID, PDF_CORRUPTED) son 422.
    return error_response(request, 422, error.code, str(error), {})


@app.exception_handler(ServiceOverloadedError)
async def handle_service_overloaded(
    request: Request, error: ServiceOverloadedError
) -> JSONResponse:
    respuesta = error_response(
        request,
        503,
        "DEPENDENCY_UNAVAILABLE",
        "El servicio está saturado, reintentar en un momento.",
        {"reason": error.motivo},
    )
    respuesta.headers["Retry-After"] = "1"
    return respuesta


@app.exception_handler(RequestValidationError)
async def handle_request_validation(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    return error_response(
        request,
        400,
        "VALIDATION_ERROR",
        "La solicitud no cumple el contrato esperado.",
        {"errors": jsonable_encoder(error.errors())},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    return error_response(
        request, 500, "INTERNAL_ERROR", "Error interno del servidor.", {}, error
    )


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    request.state.correlation_id = correlation_id
    token = correlation_id_actual.set(correlation_id)
    inicio = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        logger.info(
            "method=%s path=%s status=%s duracion_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - inicio) * 1000,
        )
        return response
    finally:
        correlation_id_actual.reset(token)
