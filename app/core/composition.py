from functools import lru_cache

from app.core.pdf_text_extractor import PdfTextExtractor
from app.services.extraction import ExtractionService


@lru_cache
def get_extraction_service() -> ExtractionService:
    """Único lugar donde se eligen las implementaciones concretas. Los tests lo
    sustituyen con app.dependency_overrides."""
    return ExtractionService(PdfTextExtractor())
