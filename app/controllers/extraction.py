from fastapi import APIRouter, Depends, File, UploadFile

from app.core.composition import get_extraction_service
from app.schemas.errors import ErrorResponse
from app.schemas.extraction import ExtractionResponse
from app.services.extraction import ExtractionService

router = APIRouter(tags=["extraction"])


@router.post(
    "/extract",
    response_model=ExtractionResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def extract(
    file: UploadFile = File(...),
    service: ExtractionService = Depends(get_extraction_service),
) -> ExtractionResponse:
    content = await file.read()
    text = await service.extract(content, file.content_type)
    return ExtractionResponse(text=text)
