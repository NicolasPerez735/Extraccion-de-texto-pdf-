from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache

from fastapi import Request

from app.core.config import Settings
from app.core.pdf_text_extractor import PdfTextExtractor
from app.core.pool_lector import PoolLectorPaginas
from app.core.pymupdf_paginas import leer_paginas
from app.services.conversion import ConversionService
from app.services.extraction import ExtractionService


@lru_cache
def get_extraction_service() -> ExtractionService:
    """Único lugar donde se eligen las implementaciones concretas. Los tests lo
    sustituyen con app.dependency_overrides."""
    return ExtractionService(PdfTextExtractor())


def crear_lector(settings: Settings) -> PoolLectorPaginas:
    """El lifespan lo crea al iniciar y lo cierra al apagar (12-Factor IX)."""
    return PoolLectorPaginas(
        leer_paginas,
        ProcessPoolExecutor(max_workers=settings.extract_workers),
        en_paralelo=settings.extract_workers,
        cola_maxima=settings.extract_max_queue,
        espera_maxima_segundos=settings.extract_queue_timeout_seconds,
    )


def get_conversion_service(request: Request) -> ConversionService:
    return ConversionService(request.app.state.lector)
