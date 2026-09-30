from fastapi import FastAPI

from app.controllers.health import router as health_router

app = FastAPI(
    title="PDF Extraction",
    version="0.1.0",
)

app.include_router(health_router)
