from fastapi import APIRouter, Depends, File, UploadFile

from app.schemas.extraction import ExtractionResponse
from app.schemas.health import HealthResponse
from app.services.extraction import ExtractionService
from app.services.pdf_text_extractor import PdfTextExtractor

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


def get_extraction_service() -> ExtractionService:
    return ExtractionService(PdfTextExtractor())


@router.post(
    "/extract",
    response_model=ExtractionResponse,
    responses={400: {"description": "Invalid PDF or unsupported file type"}},
    tags=["extraction"],
)
async def extract(
    file: UploadFile = File(...),
    service: ExtractionService = Depends(get_extraction_service),
) -> ExtractionResponse:
    content = await file.read()
    text = await service.extract(content, file.content_type)
    return ExtractionResponse(text=text)
