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


@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, error: DomainError) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(
            code=error.code,
            message=str(error),
            details={},
            correlation_id=request.state.correlation_id,
        )
    )
    return JSONResponse(status_code=422, content=body.model_dump())


@app.exception_handler(RequestValidationError)
async def handle_request_validation(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message="La solicitud no cumple el contrato esperado.",
            details={"errors": jsonable_encoder(error.errors())},
            correlation_id=request.state.correlation_id,
        )
    )
    return JSONResponse(status_code=400, content=body.model_dump())


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, _: Exception) -> JSONResponse:
    # Corre fuera del middleware de correlation ID: el header se agrega acá.
    correlation_id = request.state.correlation_id
    body = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_ERROR",
            message="Error interno del servidor.",
            details={},
            correlation_id=correlation_id,
        )
    )
    return JSONResponse(
        status_code=500,
        content=body.model_dump(),
        headers={"X-Correlation-ID": correlation_id},
    )


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response
