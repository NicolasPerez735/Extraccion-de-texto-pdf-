from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache

from fastapi import Request

from app.core.config import Settings
from app.core.pdf_text_extractor import PdfTextExtractor
from app.core.pool_markdown_converter import PoolMarkdownConverter
from app.core.pymupdf_markdown import pdf_a_markdown
from app.services.conversion import ConversionService
from app.services.extraction import ExtractionService


@lru_cache
def get_extraction_service() -> ExtractionService:
    """Único lugar donde se eligen las implementaciones concretas. Los tests lo
    sustituyen con app.dependency_overrides."""
    return ExtractionService(PdfTextExtractor())


def crear_convertidor(settings: Settings) -> PoolMarkdownConverter:
    """El lifespan lo crea al iniciar y lo cierra al apagar (12-Factor IX)."""
    executor = ProcessPoolExecutor(max_workers=settings.extract_workers)
    return PoolMarkdownConverter(pdf_a_markdown, executor)


def get_conversion_service(request: Request) -> ConversionService:
    return ConversionService(request.app.state.convertidor)
