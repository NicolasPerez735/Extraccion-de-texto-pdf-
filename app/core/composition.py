from concurrent.futures import ProcessPoolExecutor

from fastapi import Request

from app.core.config import Settings
from app.core.pool_lector import PoolLectorPaginas
from app.core.pymupdf_paginas import leer_paginas
from app.services.conversion import ConversionService
from app.services.extraction import ExtractionService


def crear_lector(settings: Settings) -> PoolLectorPaginas:
    """Único lugar donde se eligen las implementaciones concretas. El lifespan lo
    crea al iniciar y lo cierra al apagar (12-Factor IX); los tests sustituyen los
    servicios con app.dependency_overrides."""
    return PoolLectorPaginas(
        leer_paginas,
        ProcessPoolExecutor(max_workers=settings.extract_workers),
        en_paralelo=settings.extract_workers,
        cola_maxima=settings.extract_max_queue,
        espera_maxima_segundos=settings.extract_queue_timeout_seconds,
    )


def get_extraction_service(request: Request) -> ExtractionService:
    return ExtractionService(request.app.state.lector)


def get_conversion_service(request: Request) -> ConversionService:
    return ConversionService(request.app.state.lector)
