from uuid import uuid4

from fastapi import FastAPI, Request
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
    request: Request, _: RequestValidationError
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(
            code="INVALID_REQUEST",
            message="La solicitud no cumple el contrato esperado.",
            details={},
            correlation_id=request.state.correlation_id,
        )
    )
    return JSONResponse(status_code=422, content=body.model_dump())


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response
