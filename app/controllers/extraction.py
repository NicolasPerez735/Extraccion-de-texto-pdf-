from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.composition import get_extraction_service
from app.schemas.extraction import ExtractionRequest, ExtractionResponse
from app.services.extraction import ExtractionService

router = APIRouter(tags=["extraction"])

ExtractionServiceDep = Annotated[ExtractionService, Depends(get_extraction_service)]


@router.post("/extraer", response_model=ExtractionResponse)
def extraer(
    payload: ExtractionRequest, service: ExtractionServiceDep
) -> ExtractionResponse:
    # Sincrónico a propósito: FastAPI lo corre en el threadpool, así pypdf
    # (sincrónico y pesado) no bloquea el event loop.
    resultado = service.extraer(payload.archivo_base64, payload.nombre)
    return ExtractionResponse(
        nombre=resultado.nombre,
        texto=resultado.texto,
        checksum=resultado.checksum,
        tamano_bytes=resultado.tamano_bytes,
        paginas=resultado.paginas,
    )
