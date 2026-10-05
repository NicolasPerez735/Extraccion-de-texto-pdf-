from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.controllers.health import router as health_router
from app.core.exceptions import DomainError

app = FastAPI(
    title="PDF Extraction",
    version="0.1.0",
)

app.include_router(health_router)


@app.exception_handler(DomainError)
async def handle_domain_error(_: Request, error: DomainError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(error)})


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response
