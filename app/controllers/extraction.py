import time
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.core.composition import get_conversion_service, get_extraction_service
from app.schemas.extraction import (
    ExtractionRequest,
    ExtractionResponse,
    MarkdownResponse,
)
from app.services.conversion import ConversionService
from app.services.extraction import ExtractionService

router = APIRouter(tags=["extraction"])

ExtractionServiceDep = Annotated[ExtractionService, Depends(get_extraction_service)]
ConversionServiceDep = Annotated[ConversionService, Depends(get_conversion_service)]

# El body de /extract es el PDF binario: se declara a mano para que Swagger permita
# subirlo desde /docs.
PDF_BINARIO = {
    "requestBody": {
        "required": True,
        "content": {
            "application/pdf": {"schema": {"type": "string", "format": "binary"}}
        },
    }
}


@router.post("/extraer", response_model=ExtractionResponse)
def extraer(
    payload: ExtractionRequest, service: ExtractionServiceDep, response: Response
) -> ExtractionResponse:
    # Sincrónico a propósito: FastAPI lo corre en el threadpool, así pypdf
    # (sincrónico y pesado) no bloquea el event loop.
    inicio = time.perf_counter()
    resultado = service.extraer(payload.archivo_base64, payload.nombre)
    duracion_ms = (time.perf_counter() - inicio) * 1000
    response.headers["X-Extraction-Time-Ms"] = f"{duracion_ms:.1f}"
    return ExtractionResponse(
        nombre=resultado.nombre,
        texto=resultado.texto,
        checksum=resultado.checksum,
        tamano_bytes=resultado.tamano_bytes,
        paginas=resultado.paginas,
    )


@router.post("/extract", response_model=MarkdownResponse, openapi_extra=PDF_BINARIO)
async def extract(
    request: Request, service: ConversionServiceDep, response: Response
) -> MarkdownResponse:
    # Async: la conversión corre en el pool de workers y el event loop queda libre.
    contenido = await request.body()
    inicio = time.perf_counter()
    documento = await service.convertir(contenido)
    duracion_ms = (time.perf_counter() - inicio) * 1000
    response.headers["X-Extraction-Time-Ms"] = f"{duracion_ms:.1f}"
    return MarkdownResponse(content=documento.content, page_count=documento.page_count)
