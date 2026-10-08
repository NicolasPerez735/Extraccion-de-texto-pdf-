from app.core.exceptions import PdfInvalidError


def validar_firma_pdf(contenido: bytes) -> None:
    """Vacío o sin la firma %PDF: no es un PDF (contrato: 422 PDF_INVALID)."""
    if not contenido.startswith(b"%PDF"):
        raise PdfInvalidError("El archivo no es un PDF válido.")
