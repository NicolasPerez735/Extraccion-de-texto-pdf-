from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.controllers.extraction import router as extraction_router
from app.controllers.health import router as health_router
from app.core.exceptions import DomainError
from app.schemas.errors import ErrorDetail, ErrorResponse

app = FastAPI(
    title="PDF Extraction",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(extraction_router)


def error_response(
    request: Request, status_code: int, code: str, message: str, details: dict
) -> JSONResponse:
    """Formato común de errores del contrato. El header se agrega acá porque el
    handler de Exception corre fuera del middleware de correlation ID."""
    correlation_id = request.state.correlation_id
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
async def handle_unexpected_error(request: Request, _: Exception) -> JSONResponse:
    return error_response(
        request, 500, "INTERNAL_ERROR", "Error interno del servidor.", {}
    )


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response
