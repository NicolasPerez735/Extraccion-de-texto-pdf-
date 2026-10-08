"""Application and domain exception types."""


class DomainError(Exception):
    """Base exception for expected domain errors."""

    code = "DOMAIN_ERROR"


class PdfInvalidError(DomainError):
    """Raised when the content is not a PDF (Base64 inválido, vacío o sin %PDF)."""

    code = "PDF_INVALID"


class PdfCorruptedError(DomainError):
    """Raised when pypdf or MuPDF cannot read the PDF or extract its text."""

    code = "PDF_CORRUPTED"


class ServiceOverloadedError(Exception):
    """Backpressure de /extract: la cola de la réplica está llena o la espera venció.
    Se responde 503 enseguida para que el cliente reintente (o vaya a otra réplica)
    en vez de esperar hasta su timeout."""

    def __init__(self, motivo: str) -> None:
        super().__init__(f"Servicio saturado: {motivo}")
        self.motivo = motivo
